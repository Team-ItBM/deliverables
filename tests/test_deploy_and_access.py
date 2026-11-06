"""배포 순서·이미지 재사용·기본 Docker 빌드·접속 IP(PR #16 리뷰 표 항목, 2026-11-05 사람 승인).

실제 S3·ECR에는 닿지 않는다. 가짜 aws·docker 명령과 로컬 HTTP 서버로 스크립트의 판단만 검사한다.
"""

import http.server
import importlib.util
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / ".github" / "workflows" / "deploy.yml"
SCRIPTS = ROOT / ".github" / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def steps():
    return yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]


def step_index(pattern):
    found = [i for i, s in enumerate(steps()) if re.search(pattern, s.get("run", "") + s.get("name", ""))]
    assert found, f"{pattern} 단계가 없다"
    return found[0]


# ---- 자산 순서


def test_no_delete_before_html_switch():
    """리뷰: `s3 sync --delete`가 이전 자산을 HTML 전환 전에 지웠다."""
    assert "--delete" not in DEPLOY.read_text(encoding="utf-8")


def test_new_assets_upload_before_html():
    run = steps()[step_index(r"s3 sync")]["run"]
    assert run.index('--exclude index.html') < run.index('--include index.html')


def test_order_upload_invalidate_verify_prune():
    order = [step_index(r"s3 sync"), step_index(r"create-invalidation"), step_index(r"verify_spa"), step_index(r"prune_spa")]
    assert order == sorted(order)


@pytest.fixture
def site(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<script src="/assets/a-1.js"></script><link href="/assets/a-1.css">', encoding="utf-8")
    (dist / "assets" / "a-1.js").write_text("js", encoding="utf-8")
    (dist / "assets" / "a-1.css").write_text("css", encoding="utf-8")
    served = tmp_path / "served"
    subprocess.run(["cp", "-R", str(dist), str(served)], check=True)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(served), **kwargs)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", dist, served
    server.shutdown()


def test_verify_passes_when_site_serves_build(site):
    url, dist, _ = site
    assert load_script("verify_spa").main([url, str(dist)], sleep=lambda _: None) == 0


def test_verify_fails_on_old_html(site):
    url, dist, served = site
    (served / "index.html").write_text("<p>이전 빌드</p>", encoding="utf-8")
    assert load_script("verify_spa").main([url, str(dist)], sleep=lambda _: None) == 1


def test_verify_fails_on_missing_asset(site):
    url, dist, served = site
    (served / "assets" / "a-1.js").unlink()
    assert load_script("verify_spa").main([url, str(dist)], sleep=lambda _: None) == 1


NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def _object(key, days):
    return {"Key": key, "LastModified": (NOW - timedelta(days=days)).isoformat()}


def test_prune_keeps_current_and_recent_files():
    prune = load_script("prune_spa")
    objects = [_object("index.html", 30), _object("assets/new.js", 30), _object("assets/old.js", 8),
               _object("assets/recent.js", 6), _object("assets/edge.js", 7)]
    assert prune.stale_keys(objects, {"index.html", "assets/new.js"}, NOW) == ["assets/old.js"]


def test_prune_retention_is_seven_days_and_marked_as_decision():
    prune = load_script("prune_spa")
    assert prune.RETENTION_DAYS == 7
    assert "not a measured value" in (SCRIPTS / "prune_spa.py").read_text(encoding="utf-8")


def test_prune_main_removes_only_stale(tmp_path):
    prune = load_script("prune_spa")
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    (tmp_path / "assets" / "new.js").write_text("x", encoding="utf-8")
    calls = []

    def run(*args):
        calls.append(args)
        if args[0] == "s3api":
            return json.dumps({"Contents": [_object("index.html", 30), _object("assets/new.js", 30), _object("assets/old.js", 30)]})
        return ""

    assert prune.main(["bucket", str(tmp_path)], run=run, now=NOW) == 0
    assert calls[1:] == [("s3", "rm", "s3://bucket/assets/old.js")]


# ---- 같은 커밋 재실행


def _run_ensure(tmp_path, aws_script):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    (bin_dir / "aws").write_text(f"#!/bin/bash\n{aws_script}\n", encoding="utf-8")
    (bin_dir / "docker").write_text(f'#!/bin/bash\necho "$@" >> "{log}"\n', encoding="utf-8")
    for tool in ("aws", "docker"):
        (bin_dir / tool).chmod(0o755)
    output = tmp_path / "out"
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", REPOSITORY="repo", TAG="sha", IMAGE="reg/repo:sha",
               GITHUB_OUTPUT=str(output))
    result = subprocess.run([str(SCRIPTS / "ensure_image.sh")], env=env, cwd=tmp_path, capture_output=True, text=True)
    return result, log, output


def test_rerun_reuses_existing_image(tmp_path):
    """리뷰: 같은 SHA 태그로 다시 push하면 ECR 불변 태그와 충돌한다."""
    result, log, output = _run_ensure(tmp_path, "echo sha256:abc")
    assert result.returncode == 0, result.stderr
    assert not log.exists(), "이미 있는 이미지를 다시 빌드했다"
    assert output.read_text(encoding="utf-8") == "image=reg/repo:sha\n"


def test_first_run_builds_image(tmp_path):
    result, log, output = _run_ensure(tmp_path, 'echo "An error occurred (ImageNotFoundException)" >&2; exit 254')
    assert result.returncode == 0, result.stderr
    assert "--push" in log.read_text(encoding="utf-8")
    assert "image=reg/repo:sha" in output.read_text(encoding="utf-8")


def test_other_ecr_errors_stop_deploy(tmp_path):
    result, log, _ = _run_ensure(tmp_path, 'echo "AccessDeniedException" >&2; exit 254')
    assert result.returncode != 0
    assert not log.exists()


def test_workflow_uses_ensure_image():
    build = steps()[step_index(r"ensure_image")]
    assert "docker buildx" not in build["run"]


# ---- 기본 Docker 빌드


def test_docker_context_has_every_file_the_web_build_imports():
    """리뷰: 웹 단계에 docs/PRIVACY.md가 없어 기본 빌드가 실패했다."""
    imports = set()
    for path in (ROOT / "web" / "src").rglob("*.ts*"):
        imports.update(re.findall(r'from "\.\./\.\./\.\./([^"?]+)', path.read_text(encoding="utf-8")))
    assert imports == {"docs/PRIVACY.md"}
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for name in imports:
        assert f"!{name}" in ignore
        assert f"cp /ctx/{name} /{name}" in dockerfile


def test_pr_check_runs_default_docker_build():
    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "pr-check.yml").read_text(encoding="utf-8"))["jobs"]
    assert any("docker build" in s.get("run", "") and "SKIP_WEB" not in s.get("run", "") for s in jobs["docker"]["steps"])


# ---- 접속 IP


def test_uvicorn_does_not_trust_forwarded_headers():
    """리뷰: `--forwarded-allow-ips *`는 사용자가 넣은 XFF 선두 값을 접속 IP로 기록했다."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd = next(line for line in dockerfile.splitlines() if line.startswith("CMD"))
    assert "--forwarded-allow-ips" not in cmd
    assert "--no-proxy-headers" in cmd
    assert "TRUSTED_PROXY_HOPS=2" in dockerfile


def _scope(xff=None, peer="10.0.1.5"):
    headers = [] if xff is None else [(b"x-forwarded-for", xff.encode())]
    return {"client": (peer, 1234), "headers": headers}


@pytest.mark.parametrize("xff, expected", [
    ("203.0.113.9, 130.176.1.1", "203.0.113.9"),                             # 정상 경로
    ("1.2.3.4, 203.0.113.9, 130.176.1.1", "203.0.113.9"),                    # 사용자가 앞에 위조 값을 넣음
    ("1.1.1.1, 2.2.2.2, 3.3.3.3, 203.0.113.9, 130.176.1.1", "203.0.113.9"),
    ("2001:db8::1, 130.176.1.1", "2001:db8::1"),                             # IPv6 사용자
    ("130.176.1.1", "10.0.1.5"),                                             # 구간이 모자람
    (None, "10.0.1.5"),
    ("", "10.0.1.5"),
    ("not-an-ip, 130.176.1.1", "10.0.1.5"),
])
def test_client_ip_with_two_trusted_hops(xff, expected):
    from travel.server.logging import client_ip

    assert client_ip(_scope(xff), 2) == expected


def test_client_ip_ignores_header_without_trusted_proxies():
    from travel.server.logging import client_ip

    assert client_ip(_scope("1.2.3.4, 5.6.7.8"), 0) == "10.0.1.5"


def test_access_log_records_viewer_address(srv, capfd):
    app = srv.open_app(trusted_proxy_hops=2)
    capfd.readouterr()
    resp = app.client.get("/api/health", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.9, 130.176.1.1"})
    assert resp.status_code == 200
    lines = [json.loads(line) for line in capfd.readouterr().out.splitlines() if line.startswith("{")]
    assert [e["ip"] for e in lines if e["event"] == "access"] == ["203.0.113.9"]
