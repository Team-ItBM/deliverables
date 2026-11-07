"""운영 진입점: `uvicorn travel.server.main:app`.

환경변수(2026-11-05 확정): DATABASE_URL, OPENAI_API_KEY, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT,
ORIGIN_VERIFY_SECRET(현재 서버는 검사하지 않고 ALB 규칙이 검사한다), PUBLIC_BASE_URL, LLM_MODE(live | replay), AWS_REGION.
선택: LLM_CONFIG(기본 config/llm.yaml), LLM_REPLAY_FILE(replay 모드의 문항 출력 JSON, 기본 config/replay/scenario_set_d01.json),
POOL_PATH, WEB_DIST(SPA 정적 파일), TRUSTED_PROXY_HOPS(믿는 프록시 구간 수, 기본 0, 운영 이미지 2),
DB_INIT_ON_START(1이면 시작 때 스키마를 만든다. 로컬 실행용).

replay 모드는 테스트·동료 로컬 실행·장애 대비용이며 실제 모델을 부르지 않는다(README에 밝힌다).
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .app import Settings, create_app
from .replay import ReplayClient
from .logging import log

ROOT = Path(__file__).resolve().parents[3]


def utc_now():
    return datetime.now(timezone.utc)


def no_redirect_session():
    """리다이렉트를 따라가지 않는 세션. 허용한 푸시 서비스가 돌려준 Location으로 서버가 요청을 보내지 않게 한다."""
    import requests

    class NoRedirectSession(requests.Session):
        def request(self, *args, **kwargs):
            kwargs["allow_redirects"] = False
            return super().request(*args, **kwargs)

    return NoRedirectSession()


class WebPushSender:
    """pywebpush로 보낸다. send(subscription, payload) -> HTTP 상태 코드. 실패는 상태 코드로만 알린다."""

    def __init__(self, private_key, subject, timeout_seconds=10):
        self.private_key = private_key
        self.subject = subject
        self.timeout_seconds = timeout_seconds

    def send(self, subscription, payload):
        import pywebpush
        from pywebpush import WebPushException

        try:
            response = pywebpush.webpush(subscription_info=subscription, data=json.dumps(payload, ensure_ascii=False),
                                         vapid_private_key=self.private_key, vapid_claims={"sub": self.subject}, ttl=3600,
                                         timeout=self.timeout_seconds, requests_session=no_redirect_session())
            return getattr(response, "status_code", 201)
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            return getattr(response, "status_code", 500) or 500


class DisabledPushSender:
    def send(self, subscription, payload):
        return 0


def build_settings(env, llm_config):
    job = llm_config.data.get("job") or {}
    retry = llm_config.data.get("retry") or {}
    concurrency = llm_config.data.get("concurrency") or {}
    return Settings(
        database_url=env["DATABASE_URL"],
        pool_path=env.get("POOL_PATH") or str(ROOT / llm_config.data["pool"]["path"]),
        retry_backoff_seconds=tuple(retry.get("backoff_seconds", (1, 2))),
        retry_jitter_seconds=float(retry.get("jitter_seconds", 0.5)),
        job_time_limit_seconds=int(job.get("time_limit_seconds", 300)),
        stall_limit_seconds=int(job.get("stall_limit_seconds", 600)),
        llm_timeout_seconds=llm_config.timeout_seconds,
        max_concurrent_generations=int(concurrency.get("max_generations", 4)),
        trusted_proxy_hops=int(env.get("TRUSTED_PROXY_HOPS", "0")),
        public_base_url=env.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/"),
        vapid_public_key=env.get("VAPID_PUBLIC_KEY", ""),
        model_id=llm_config.model,
        prompt_versions={stage: spec["version"] for stage, spec in llm_config.prompts.items()},
        schema_versions={stage: spec["schema_version"] for stage, spec in llm_config.prompts.items()},
        maintenance_interval_seconds=float(job.get("maintenance_interval_seconds", 30)),
        room_cap_usd=float(cost["room_cap_usd"]) if (cost := (llm_config.cost or {})).get("room_cap_usd") is not None else None,
    )


def build_app(env=None):
    from .llm_openai import CostGuard, LLMConfig, OpenAIClient

    env = dict(os.environ if env is None else env)
    llm_config = LLMConfig.load(env.get("LLM_CONFIG") or ROOT / "config" / "llm.yaml", root=ROOT)
    settings = build_settings(env, llm_config)
    if env.get("DB_INIT_ON_START") == "1":
        db.init_schema(settings.database_url)
    mode = env.get("LLM_MODE", "live")
    holder = {}
    if mode == "replay":
        llm_client = ReplayClient(env.get("LLM_REPLAY_FILE") or ROOT / "config" / "replay" / "scenario_set_d01.json")
    elif mode == "live":
        from .app import ScenarioPool

        pool_source = ScenarioPool(settings.pool_path)
        guard = CostGuard(lambda: getattr(holder.get("app"), "state", None) and holder["app"].state.db, utc_now,
                          daily_cap_usd=float((llm_config.cost or {}).get("daily_cap_usd", 5.0)))
        llm_client = OpenAIClient(llm_config, api_key=env["OPENAI_API_KEY"], lookup=pool_source.lookup, cost_guard=guard)
    else:
        raise ValueError(f"LLM_MODE는 live 또는 replay다: {mode}")
    if env.get("VAPID_PRIVATE_KEY") and env.get("VAPID_SUBJECT"):
        push_sender = WebPushSender(env["VAPID_PRIVATE_KEY"], env["VAPID_SUBJECT"],
                                    timeout_seconds=settings.push_timeout_seconds)
    else:
        push_sender = DisabledPushSender()
        log("push_disabled", reason="VAPID 키 없음")
    app = create_app(settings=settings, llm_client=llm_client, push_sender=push_sender, sleeper=asyncio.sleep,
                     clock=utc_now)
    holder["app"] = app
    web_dist = Path(env.get("WEB_DIST") or ROOT / "web" / "dist")
    if web_dist.is_dir():
        _mount_spa(app, web_dist)
    log("app_built", llm_mode=mode, model=llm_config.model, prompt_versions=settings.prompt_versions)
    return app


def _mount_spa(app, web_dist):
    """로컬·단일 컨테이너 실행용 SPA 서빙. 운영은 CloudFront + S3가 맡는다. /api/*는 건드리지 않는다."""
    from fastapi.responses import FileResponse
    from starlette.staticfiles import StaticFiles

    base = web_dist.resolve()
    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            from .app import error_response

            return error_response("not_found")
        candidate = web_dist / full_path
        if full_path and candidate.is_file():
            resolved = candidate.resolve()
            if resolved.is_relative_to(base):
                return FileResponse(str(resolved))
        return FileResponse(str(web_dist / "index.html"))


app = build_app() if os.environ.get("DATABASE_URL") else None
