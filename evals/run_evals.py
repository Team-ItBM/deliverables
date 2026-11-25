import argparse
import asyncio
import copy
import csv
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "evals" / "EVAL_DESIGN.md"
EVALSET_PATH = ROOT / "evals" / "evalset.jsonl"
JUDGE_PATH = ROOT / "evals" / "judge_prompt.md"
LLM_CONFIG_PATH = ROOT / "config" / "llm.yaml"
POOL_TABLE_PATH = ROOT / "docs" / "research" / "scenario_pool.md"
FIXTURES_DIR = ROOT / "tests" / "harness" / "fixtures" / "evals"
RESULTS_DIR = ROOT / "evals" / "results"
CALIBRATION_EVAL = ROOT / "docs" / "spikes" / "grounded_pact_eval.jsonl"
CALIBRATION_INPUTS = ROOT / "docs" / "spikes" / "grounded_pact_inputs.jsonl"

STAGES = ("scenarios", "pact")
CASE_KEYS = {"id", "stage", "category", "query", "expect", "graders", "expect_source", "note"}
REQUIRED_CASE_KEYS = {"id", "stage", "category", "query", "expect", "graders"}
EXPECT_KEYS = {"allowed_status", "duration_fit", "tool_contract", "forbidden_text", "public_text_regex",
               "criteria_ref", "judge_criteria"}
CHECK_KEYS = ("allowed_status", "duration_fit", "tool_contract", "forbidden_text", "public_text_regex")
OPTIONAL_PROFILE_KEYS = ("gender", "age_band", "mbti")
ROUTING_CATEGORIES = {"clarify", "invalid", "out_of_scope", "unresolved", "conditional"}
NO_JUDGE_STATUSES = {"invalid_input", "unsupported"}
PACT_CRITERIA = ("j1", "j2", "j3", "j4", "j5", "j6", "j7", "j8")
SCENARIO_ITEM_CRITERIA = ("s1", "s2", "s3", "s4", "s5")
SCENARIO_REQUEST_CRITERIA = ("s6", "s7")
SCENARIO_CRITERIA = SCENARIO_ITEM_CRITERIA + SCENARIO_REQUEST_CRITERIA
FORBIDDEN_ERROR_CRITERIA = ("j1", "j2", "j3")
INJECTION_PACT_CRITERIA = ("j1", "j3")
DURATION_MIN_DAYS = {"당일·숙박": 1, "숙박": 2, "숙박 마지막 날": 2, "2박 이상": 3}
METRIC_ORDER = (
    "scenario_format_first", "scenario_unusable", "scenario_status_match", "scenario_duration_violation",
    "scenario_tool_contract", "scenario_profile_exposure", "scenario_injection_violation", "scenario_adaptation_quality",
    "pact_format_first", "pact_unusable", "pact_routing_match", "pact_forbidden_errors", "pact_quality_pass",
    "pact_public_privacy", "pact_injection_violation", "scenario_latency_p95", "pact_latency_p95",
    "room_cost_estimate_mean", "room_cost_estimate_max", "eval_run_cost",
)
HISTORY_COLUMNS = (
    "run_id", "source_run_id", "mode", "commit", "change", "evalset_version", "judge_version", "targets_version",
    "scenario_prompt", "pact_prompt", "pool", "golden_tests", "baseline_eligible", "judge_validated", "incomplete",
    "scenario_format_first", "scenario_unusable", "scenario_status_match", "scenario_duration_violation",
    "scenario_tool_contract", "scenario_profile_exposure", "scenario_injection_violation", "scenario_adaptation_quality",
    "pact_format_first", "pact_unusable", "pact_routing_match", "pact_forbidden_errors", "pact_quality_pass",
    "pact_public_privacy", "pact_injection_violation", "scenario_latency_p95", "pact_latency_p95",
    "room_cost_estimate_mean", "room_cost_estimate_max", "eval_run_cost",
    "judge_label_run_id", "judge_labeled_cases", "judge_agreement_min", "judge_agreement_by_criterion",
    "judge_forbidden_recall", "judge_validation_passed",
)
VALIDATION_COLUMNS = (
    "created_at", "judge_version", "judge_pact_sha256", "judge_scenarios_sha256", "judge_run_id", "label_run_id",
    "labeled_cases", "compared_cases", "agreement_by_criterion", "forbidden_recall", "thresholds_status", "passed",
)

_PRODUCT = None


class EvalError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class BudgetExceeded(Exception):
    pass


class NoStoredOutput(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def product():
    global _PRODUCT
    if _PRODUCT is None:
        src = str(ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from travel import pact_v12, pool, scenarios
        from travel.server import app, jobs, llm, llm_openai

        _PRODUCT = SimpleNamespace(
            validate_pact_output=pact_v12.validate_pact_output,
            validate_scenario_output=scenarios.validate_scenario_output,
            load_pool=pool.load_pool,
            build_scenario_index=pool.build_scenario_index,
            lookup_template=pool.lookup_template,
            placeholder_profiles=jobs.placeholder_profiles,
            scenario_request=app.Settings.__dataclass_fields__["scenario_request"].default,
            LLMCallError=llm.LLMCallError,
            LLMResult=llm.LLMResult,
            LLMConfig=llm_openai.LLMConfig,
            OpenAIClient=llm_openai.OpenAIClient,
        )
    return _PRODUCT


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def between(text, start, end):
    i = text.find(start)
    j = text.find(end)
    if i < 0 or j < 0 or j < i:
        raise EvalError("marker_missing", start)
    return text[i + len(start):j]


def load_targets(path=DESIGN_PATH):
    text = Path(path).read_text(encoding="utf-8")
    block = between(text, "<!-- targets:start -->", "<!-- targets:end -->")
    m = re.search(r"```yaml\n(.*?)```", block, re.S)
    if not m:
        raise EvalError("targets_block_missing", str(path))
    data = yaml.safe_load(m.group(1))
    if not isinstance(data, dict) or "metrics" not in data:
        raise EvalError("targets_block_invalid", str(path))
    missing = [k for k in METRIC_ORDER if k not in data["metrics"]]
    if missing:
        raise EvalError("targets_missing_metric", ",".join(missing))
    return data


def load_judge(path=JUDGE_PATH):
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r"\|\s*judge_version\s*\|\s*(\S+)\s*\|", text)
    if not m:
        raise EvalError("judge_version_missing", str(path))
    out = {"version": m.group(1)}
    for stage in STAGES:
        body = between(text, f"<!-- judge:{stage}:start -->", f"<!-- judge:{stage}:end -->")
        schema_block = between(text, f"<!-- schema:{stage}:start -->", f"<!-- schema:{stage}:end -->")
        sm = re.search(r"```json\n(.*?)```", schema_block, re.S)
        if not sm:
            raise EvalError("judge_schema_missing", stage)
        schema = json.loads(sm.group(1))
        jsonschema.Draft7Validator.check_schema(schema)
        out[stage] = {"body": body, "schema": schema, "sha256": sha256_text(body)}
    return out


def load_pool_table(path=POOL_TABLE_PATH):
    table = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*\d+\.\s*`([a-z0-9_]+)`", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        last = cells[-1]
        am = re.search(r"적용:\s*(.+)$", last)
        if not am:
            raise EvalError("pool_table_no_applicability", m.group(1))
        applies = am.group(1).split("/")[0].strip()
        if applies not in DURATION_MIN_DAYS:
            raise EvalError("pool_table_unknown_applicability", f"{m.group(1)}: {applies}")
        table[m.group(1)] = {"applies": applies, "min_days": DURATION_MIN_DAYS[applies],
                             "adaptation_scope": last[:am.start()].strip()}
    if not table:
        raise EvalError("pool_table_empty", str(path))
    return table


def load_evalset(path=EVALSET_PATH):
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    cases = []
    for n, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        missing = REQUIRED_CASE_KEYS - set(case)
        if missing:
            raise EvalError("case_missing_keys", f"line {n}: {sorted(missing)}")
        if case["stage"] not in STAGES:
            raise EvalError("case_bad_stage", case["id"])
        cases.append(case)
    ids = [c["id"] for c in cases]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        raise EvalError("case_duplicate_id", ",".join(dup))
    version = f"{len(cases)} cases, {hashlib.sha256(raw).hexdigest()[:7]}"
    return cases, version


def is_draft_source(case):
    source = str(case.get("expect_source", ""))
    return source.startswith("draft") or source.startswith("team+draft")


def resolve_query(query, root=ROOT):
    if isinstance(query, dict):
        return copy.deepcopy(query)
    if not isinstance(query, str) or "#" not in query:
        raise EvalError("query_invalid", repr(query)[:80])
    rel, _, cid = query.partition("#")
    path = Path(root) / rel
    if not path.exists():
        raise EvalError("query_file_missing", rel)
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        case = (data.get("cases") or {}).get(cid)
        if case is None:
            raise EvalError("query_case_missing", query)
        out = copy.deepcopy(data["base_inputs"][case["base"]])
        for key in case.get("remove") or []:
            out.pop(key, None)
        for key, value in (case.get("replace") or {}).items():
            out[key] = copy.deepcopy(value)
        return out
    if path.suffix == ".jsonl":
        found = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("case_id") == cid:
                found.append(row.get("input"))
        if not found:
            raise EvalError("query_case_missing", query)
        if any(canonical(x) != canonical(found[0]) for x in found[1:]):
            raise EvalError("query_inputs_differ", query)
        return copy.deepcopy(found[0])
    raise EvalError("query_file_type", rel)


def resolve_criteria(ref, root=ROOT):
    rel, _, cid = ref.partition("#")
    path = Path(root) / rel
    if not path.exists():
        raise EvalError("criteria_file_missing", rel)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("case_id") == cid:
            crit = row.get("criteria") or {}
            return {"allowed_results": crit.get("allowed_results"), "immediate_failures": crit.get("immediate_failures")}
    raise EvalError("criteria_case_missing", ref)


def build_inputs(stage, raw):
    p = product()
    if stage == "pact":
        return copy.deepcopy(raw), copy.deepcopy(raw)
    base = {k: copy.deepcopy(raw[k]) for k in ("trip", "participant_profiles", "requested_count", "request") if k in raw}
    profiles = base.get("participant_profiles")
    if isinstance(profiles, list) and all(isinstance(x, dict) for x in profiles):
        base["participant_profiles"] = p.placeholder_profiles(profiles)
    base.setdefault("request", p.scenario_request)
    model_input = dict(base, scenario_pool=p.build_scenario_index())
    validation_input = dict(base, scenario_pool=p.load_pool()["scenario_pool"])
    return model_input, validation_input


def validator_for(stage, validation_input):
    p = product()
    if stage == "scenarios":
        return lambda raw: p.validate_scenario_output(validation_input, raw)
    return lambda raw: p.validate_pact_output(validation_input, raw)


def scenario_texts(output):
    texts = []
    for s in output.get("scenarios") or []:
        if not isinstance(s, dict):
            continue
        for key in ("scene", "question"):
            if isinstance(s.get(key), str):
                texts.append(s[key])
        for opt in s.get("options") or []:
            if isinstance(opt, dict) and isinstance(opt.get("label"), str):
                texts.append(opt["label"])
    if isinstance(output.get("message"), str):
        texts.append(output["message"])
    for q in output.get("clarification_questions") or []:
        if isinstance(q, str):
            texts.append(q)
    return texts


def pact_shared_texts(output):
    texts = []
    for key in ("clauses", "conditional_alternatives"):
        for item in output.get(key) or []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("action"), str):
                texts.append(item["action"])
            texts.extend(x for x in item.get("proposed_conditions") or [] if isinstance(x, str))
            for rc in item.get("required_changes") or []:
                if isinstance(rc, dict) and isinstance(rc.get("proposed_change"), str):
                    texts.append(rc["proposed_change"])
    for u in output.get("unresolved_conditions") or []:
        if isinstance(u, dict) and isinstance(u.get("description"), str):
            texts.append(u["description"])
    if isinstance(output.get("message"), str):
        texts.append(output["message"])
    return texts


def visible_texts(stage, output):
    return scenario_texts(output) if stage == "scenarios" else pact_shared_texts(output)


def profile_exposure(model_input, output):
    needles = []
    for prof in model_input.get("participant_profiles") or []:
        if not isinstance(prof, dict):
            continue
        if isinstance(prof.get("display_name"), str):
            needles.append(prof["display_name"])
        for key in OPTIONAL_PROFILE_KEYS:
            if isinstance(prof.get(key), str) and prof[key]:
                needles.append(prof[key])
    texts = scenario_texts(output)
    return sorted({n for n in needles if any(n in t for t in texts)})


def duration_violations(trip, output, pool_table):
    days = (trip or {}).get("duration_days") if isinstance(trip, dict) else None
    if not isinstance(days, int) or isinstance(days, bool):
        raise EvalError("duration_unknown", repr(days))
    bad = []
    for s in output.get("scenarios") or []:
        tid = s.get("template_id") if isinstance(s, dict) else None
        row = pool_table.get(tid)
        if row is None:
            raise EvalError("pool_table_missing_template", str(tid))
        if days < row["min_days"]:
            bad.append({"template_id": tid, "applies": row["applies"]})
    return bad


def regex_groups(groups, texts):
    joined = "\n".join(texts)
    return [any(re.search(p, joined) for p in group) for group in groups]


def run_code_checks(case, stage, model_input, output, used_attempt, ctx):
    checks = {}
    errors = []
    expect = case["expect"]
    for key in expect:
        if key not in EXPECT_KEYS:
            errors.append({"code": "unknown_expect_key", "detail": key})
    if "allowed_status" in expect:
        checks["allowed_status"] = {"pass": output.get("status") in expect["allowed_status"], "status": output.get("status")}
    if "duration_fit" in expect:
        try:
            bad = duration_violations(model_input.get("trip"), output, ctx.pool_table)
            checks["duration_fit"] = {"pass": not bad, "violations": bad}
        except EvalError as exc:
            errors.append({"code": exc.code, "detail": exc.detail})
    if "tool_contract" in expect:
        selected = [s.get("template_id") for s in output.get("scenarios") or [] if isinstance(s, dict)]
        opened = set(used_attempt.get("opened_template_ids") or [])
        unopened = [t for t in selected if t not in opened]
        calls = used_attempt.get("tool_calls")
        within = None if calls is None else calls < ctx.tool_call_limit
        checks["tool_contract"] = {"pass": not unopened and within is not False, "unopened": unopened,
                                   "tool_calls": calls, "tool_calls_unknown": calls is None}
    texts = visible_texts(stage, output)
    if "forbidden_text" in expect:
        hits = [w for w in expect["forbidden_text"] if any(w in t for t in texts)]
        checks["forbidden_text"] = {"pass": not hits, "hits": hits}
    if "public_text_regex" in expect:
        if stage != "pact":
            errors.append({"code": "expect_key_stage", "detail": "public_text_regex"})
        else:
            groups = regex_groups(expect["public_text_regex"], texts)
            checks["public_text_regex"] = {"pass": all(groups), "groups": groups}
    return checks, errors


def judge_applicable(case, stage, output):
    if "judge" not in case["graders"] or output is None:
        return False
    status = output.get("status")
    if status in NO_JUDGE_STATUSES:
        return False
    if stage == "scenarios" and status != "ready":
        return False
    return True


def case_criteria(case):
    expect = case["expect"]
    if "criteria_ref" in expect:
        return resolve_criteria(expect["criteria_ref"])
    if "judge_criteria" in expect:
        jc = expect["judge_criteria"]
        return {"allowed_results": jc.get("allowed_results"), "immediate_failures": jc.get("immediate_failures")}
    return None


def build_judge_input(case, stage, model_input, output, ctx):
    if stage == "pact":
        return {"input": model_input, "output": output, "case_criteria": case_criteria(case)}
    items = []
    p = product()
    for s in output.get("scenarios") or []:
        tid = s.get("template_id")
        original = p.lookup_template(tid)
        items.append({"output": s,
                      "original": {k: original.get(k) for k in ("scene", "question", "options", "core_constraints")},
                      "adaptation_scope": ctx.pool_table.get(tid, {}).get("adaptation_scope")})
    return {"trip": model_input.get("trip"), "participant_profiles": model_input.get("participant_profiles"),
            "requested_count": model_input.get("requested_count"), "scenarios": items, "request_criteria": None}


def expected_null_pact(output):
    status = output.get("status")
    alternatives = output.get("conditional_alternatives") or []
    unresolved = output.get("unresolved_conditions") or []
    return {
        "j1": False, "j2": False, "j3": False, "j5": False, "j7": False,
        "j4": status == "needs_information",
        "j6": output.get("clauses") is None and not alternatives,
        "j8": not unresolved and status == "proposed",
    }


def interpret_judge(stage, raw_text, schema, output):
    try:
        data = json.loads(raw_text)
    except (TypeError, ValueError):
        return {"errors": [{"code": "judge_parse_error"}], "criteria": {}, "pass": False}
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        return {"errors": [{"code": "judge_schema_violation", "detail": exc.message[:200]}], "criteria": {}, "pass": False,
                "raw": data}
    errors = []
    criteria = {}
    if stage == "pact":
        nulls = expected_null_pact(output)
        for key in PACT_CRITERIA:
            verdict = data["criteria"][key]
            criteria[key] = verdict
            if (verdict["pass"] is None) != nulls[key]:
                errors.append({"code": "judge_applicability", "detail": key})
        failed = [k for k, v in criteria.items() if v["pass"] is False]
        return {"errors": errors, "criteria": criteria, "failed": failed, "overall_note": data.get("overall_note"),
                "pass": not errors and not failed}
    selected = sorted(s.get("template_id") for s in output.get("scenarios") or [])
    judged = sorted(s["template_id"] for s in data["scenarios"])
    if selected != judged:
        errors.append({"code": "judge_template_mismatch", "detail": f"{selected} != {judged}"})
    failed_templates = {}
    for key in SCENARIO_ITEM_CRITERIA:
        values = [s[key]["pass"] for s in data["scenarios"]]
        if any(v is None for v in values):
            errors.append({"code": "judge_applicability", "detail": key})
        bad = [s["template_id"] for s in data["scenarios"] if s[key]["pass"] is False]
        criteria[key] = {"pass": None if not values else (not bad and all(v is not None for v in values)),
                         "reason": "; ".join(f"{s['template_id']}: {s[key]['reason']}" for s in data["scenarios"])}
        if bad:
            failed_templates[key] = bad
    for key in SCENARIO_REQUEST_CRITERIA:
        verdict = data["request"][key]
        criteria[key] = verdict
        if verdict["pass"] is None:
            errors.append({"code": "judge_applicability", "detail": key})
    failed = [k for k, v in criteria.items() if v["pass"] is False]
    return {"errors": errors, "criteria": criteria, "failed": failed, "failed_templates": failed_templates,
            "overall_note": data.get("overall_note"), "per_scenario": data["scenarios"],
            "pass": not errors and not failed}


class Budget:
    def __init__(self, max_usd):
        self.max_usd = max_usd
        self.spent = 0.0

    def check(self):
        if self.max_usd is not None and self.spent >= self.max_usd:
            raise BudgetExceeded()

    def add(self, cost):
        self.spent = round(self.spent + (cost or 0.0), 6)


class StoredModel:
    def __init__(self, fixtures_dir):
        self.dir = Path(fixtures_dir) / "outputs"

    async def call(self, case_id, stage, model_input, repair_errors, round_no):
        path = self.dir / f"{case_id}.json"
        if not path.exists():
            raise NoStoredOutput("no_stored_output")
        data = json.loads(path.read_text(encoding="utf-8"))
        attempts = data.get("attempts") or []
        if round_no >= len(attempts):
            raise NoStoredOutput("no_stored_output" if round_no == 0 else "no_stored_repair")
        a = attempts[round_no]
        usage = a.get("usage") or {}
        result = product().LLMResult(raw_output=a.get("raw_output", ""), response_status=a.get("response_status", "completed"),
                                     opened_template_ids=list(a.get("opened_template_ids") or []), usage=usage)
        return result, a.get("latency_s"), usage.get("cost_usd") or 0.0


class StoredJudge:
    def __init__(self, fixtures_dir):
        self.dir = Path(fixtures_dir) / "judge"

    async def call(self, key, stage, judge_input, spec):
        path = self.dir / f"{key}.json"
        if not path.exists():
            raise NoStoredOutput("no_stored_judge")
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("raw_output", ""), None, 0.0


class LiveModel:
    def __init__(self, config, retry):
        p = product()
        self.client = p.OpenAIClient(config, api_key=os.environ["OPENAI_API_KEY"], lookup=p.lookup_template)
        self.retry = retry

    async def call(self, case_id, stage, model_input, repair_errors, round_no):
        started = time.monotonic()
        result = await with_retries(lambda: self.client.generate(stage, model_input, repair_errors=repair_errors), self.retry)
        latency = round(time.monotonic() - started, 3)
        return result, latency, (result.usage or {}).get("cost_usd") or 0.0


class LiveJudge:
    def __init__(self, config, retry):
        p = product()
        self.client = p.OpenAIClient(config, api_key=os.environ["OPENAI_API_KEY"])
        self.retry = retry

    async def call(self, key, stage, judge_input, spec):
        items = [{"role": "user", "content": json.dumps(judge_input, ensure_ascii=False)}]
        request_spec = {"body": spec["body"], "schema": spec["schema"], "schema_name": f"EvalJudge_{stage}"}
        started = time.monotonic()

        async def once():
            response = await self.client._request(request_spec, items, tools_on=False)
            return self.client._final(response, opened=[], tool_calls=0)

        result = await with_retries(once, self.retry)
        latency = round(time.monotonic() - started, 3)
        if result.response_status != "completed":
            return "", latency, (result.usage or {}).get("cost_usd") or 0.0
        return result.raw_output, latency, (result.usage or {}).get("cost_usd") or 0.0


async def with_retries(make_call, retry):
    p = product()
    bases = list(retry.get("backoff_seconds", [1, 2]))
    jitter = float(retry.get("jitter_seconds", 0.5))
    for attempt in range(len(bases) + 1):
        try:
            return await make_call()
        except p.LLMCallError as exc:
            if attempt == len(bases):
                raise
            wait = exc.retry_after if exc.kind == "rate_limited" and exc.retry_after is not None else bases[attempt] + random.uniform(0, jitter)
            await asyncio.sleep(wait)


async def generate_case(case, stage, model_input, validate, ctx):
    p = product()
    attempts = []
    repair = None
    output = None
    used = None
    errors = []
    for round_no in range(2):
        try:
            ctx.budget.check()
        except BudgetExceeded:
            return {"attempts": attempts, "output": None, "used": None, "errors": errors, "not_run": True}
        try:
            async with ctx.semaphore:
                result, latency, cost = await ctx.model.call(case["id"], stage, model_input, repair, round_no)
        except NoStoredOutput as exc:
            errors.append({"code": exc.code})
            break
        except p.LLMCallError as exc:
            errors.append({"code": "call_error", "detail": exc.kind})
            break
        ctx.budget.add(cost)
        usage = result.usage or {}
        attempt = {"round": round_no, "raw_output_sha256": sha256_text(result.raw_output or ""),
                   "response_status": result.response_status, "validator_errors": [], "latency_s": latency,
                   "cost_usd": cost, "tool_calls": usage.get("tool_calls"),
                   "opened_template_ids": list(result.opened_template_ids or [])}
        attempts.append(attempt)
        if result.response_status != "completed":
            repair = [{"code": f"response_{result.response_status}", "path": "", "detail": "모델 응답이 완료되지 않았다"}]
            attempt["validator_errors"] = [repair[0]["code"]]
            continue
        verdict = validate(result.raw_output)
        if verdict["valid"]:
            output = json.loads(result.raw_output)
            used = attempt
            break
        repair = verdict["errors"]
        attempt["validator_errors"] = [e.get("code") for e in repair if isinstance(e, dict)]
    return {"attempts": attempts, "output": output, "used": used, "errors": errors, "not_run": False}


async def judge_case(case, stage, model_input, output, ctx):
    spec = ctx.judge[stage]
    try:
        judge_input = build_judge_input(case, stage, model_input, output, ctx)
    except (EvalError, KeyError) as exc:
        return {"errors": [{"code": "judge_input_error", "detail": str(exc)}], "criteria": {}, "pass": False}
    try:
        ctx.budget.check()
    except BudgetExceeded:
        return {"not_run": True, "errors": [], "criteria": {}, "pass": None}
    try:
        async with ctx.semaphore:
            raw, latency, cost = await ctx.judge_client.call(case["id"], stage, judge_input, spec)
    except NoStoredOutput as exc:
        return {"errors": [{"code": exc.code}], "criteria": {}, "pass": False}
    except product().LLMCallError as exc:
        return {"errors": [{"code": "judge_call_error", "detail": exc.kind}], "criteria": {}, "pass": False}
    ctx.budget.add(cost)
    ctx.judge_cost += cost or 0.0
    verdict = interpret_judge(stage, raw, spec["schema"], output)
    verdict["latency_s"] = latency
    verdict["cost_usd"] = cost
    return verdict


def finish_record(rec):
    if rec.get("not_run"):
        rec["code_pass"] = None
        rec["pass"] = None
        return rec
    code_ok = rec["output"] is not None and not rec["errors"] and not rec["exposure"]
    code_ok = code_ok and all(c["pass"] for c in rec["code"].values())
    rec["code_pass"] = code_ok
    if not rec["judge_applicable"]:
        rec["pass"] = code_ok
    elif rec["judge"] is None or rec["judge"].get("not_run"):
        rec["pass"] = None if code_ok else False
    else:
        rec["pass"] = code_ok and bool(rec["judge"].get("pass"))
    return rec


async def run_case(case, ctx, reuse=None):
    stage = case["stage"]
    rec = {"id": case["id"], "stage": stage, "category": case["category"], "graders": case["graders"],
           "expect_source": case.get("expect_source"), "attempts": [], "errors": [], "output": None,
           "exposure": [], "code": {}, "judge_applicable": False, "judge": None, "not_run": False,
           "multi_scenario": False, "cost_usd": 0.0, "latency_s": None, "first_ok": False}
    extra = sorted(set(case) - CASE_KEYS)
    if extra:
        rec["errors"].append({"code": "unknown_case_key", "detail": ",".join(extra)})
    try:
        raw = resolve_query(case["query"])
        model_input, validation_input = build_inputs(stage, raw)
    except EvalError as exc:
        rec["errors"].append({"code": exc.code, "detail": exc.detail})
        return finish_record(rec)
    rec["multi_scenario"] = stage == "pact" and len(model_input.get("scenarios") or []) >= 2
    rec["input_sha256"] = sha256_text(canonical(model_input))
    if reuse is not None and reuse.get("input_sha256") and reuse["input_sha256"] != rec["input_sha256"]:
        rec["errors"].append({"code": "input_changed", "detail": "출력 실행 때와 모델 입력이 다르다"})
        return finish_record(rec)
    if reuse is None:
        gen = await generate_case(case, stage, model_input, validator_for(stage, validation_input), ctx)
        rec["attempts"] = gen["attempts"]
        rec["errors"].extend(gen["errors"])
        rec["output"] = gen["output"]
        rec["not_run"] = gen["not_run"]
        used = gen["used"]
    else:
        rec["attempts"] = reuse["attempts"]
        rec["errors"].extend(e for e in reuse["errors"] if not str(e.get("code", "")).startswith("judge"))
        rec["output"] = reuse["output"]
        rec["not_run"] = reuse.get("not_run", False)
        used = next((a for a in reversed(rec["attempts"]) if not a["validator_errors"]), None) if rec["output"] else None
    rec["cost_usd"] = round(sum(a.get("cost_usd") or 0.0 for a in rec["attempts"]), 6)
    latencies = [a.get("latency_s") for a in rec["attempts"]]
    rec["latency_s"] = round(sum(latencies), 3) if latencies and all(x is not None for x in latencies) else None
    first = rec["attempts"][0] if rec["attempts"] else None
    rec["first_ok"] = bool(first and first["response_status"] == "completed" and not first["validator_errors"])
    if rec["not_run"]:
        return finish_record(rec)
    output = rec["output"]
    if output is not None:
        if stage == "scenarios":
            rec["exposure"] = profile_exposure(model_input, output)
        rec["code"], errors = run_code_checks(case, stage, model_input, output, used or {}, ctx)
        rec["errors"].extend(errors)
        rec["judge_applicable"] = judge_applicable(case, stage, output)
        if rec["judge_applicable"] and ctx.judge_enabled:
            rec["judge"] = await judge_case(case, stage, model_input, output, ctx)
    else:
        for key in CHECK_KEYS:
            if key in case["expect"]:
                rec["code"][key] = {"pass": False, "reason": "no_usable_output"}
    return finish_record(rec)


def rate(records, predicate):
    total = len(records)
    passed = sum(1 for r in records if predicate(r))
    return {"value": round(passed / total, 4) if total else None, "passed": passed, "total": total}


def count(records, predicate):
    hits = [r["id"] for r in records if predicate(r)]
    return {"count": len(hits), "cases": hits}


def judge_failed(rec, keys):
    j = rec.get("judge")
    if not j or j.get("not_run"):
        return False
    return any((j.get("criteria", {}).get(k) or {}).get("pass") is False for k in keys)


def code_failed(rec, key):
    c = rec["code"].get(key)
    return rec["output"] is not None and c is not None and c["pass"] is False


def p95(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return vals[max(0, math.ceil(0.95 * len(vals)) - 1)]


def compute_metrics(records, live, judge_ran):
    done = [r for r in records if not r["not_run"]]
    sc = [r for r in done if r["stage"] == "scenarios"]
    pa = [r for r in done if r["stage"] == "pact"]
    m = {}
    m["scenario_format_first"] = rate(sc, lambda r: r["first_ok"])
    m["scenario_unusable"] = count(sc, lambda r: r["output"] is None)
    m["scenario_status_match"] = rate(sc, lambda r: r["output"] is not None and r["code"].get("allowed_status", {}).get("pass") is True)
    dv = [(r["id"], len(r["code"]["duration_fit"].get("violations", []))) for r in sc if "duration_fit" in r["code"]]
    m["scenario_duration_violation"] = {"count": sum(n for _, n in dv), "cases": [i for i, n in dv if n]}
    m["scenario_tool_contract"] = rate([r for r in sc if "tool_contract" in r["code"]], lambda r: r["code"]["tool_contract"]["pass"])
    m["scenario_profile_exposure"] = count(sc, lambda r: bool(r["exposure"]))
    m["scenario_injection_violation"] = count([r for r in sc if r["category"] == "injection"],
                                              lambda r: not r["code_pass"] or judge_failed(r, ("s7",)))
    sq = [r for r in sc if r["judge_applicable"]]
    m["scenario_adaptation_quality"] = rate(sq, lambda r: bool(r["judge"] and r["judge"].get("pass"))) if judge_ran else {"value": None}
    m["pact_format_first"] = rate(pa, lambda r: r["first_ok"])
    m["pact_format_first"]["first_output_error_codes"] = dict(Counter(
        c for r in pa if r["attempts"] for c in r["attempts"][0]["validator_errors"]))
    m["pact_unusable"] = count(pa, lambda r: r["output"] is None)
    m["pact_routing_match"] = rate([r for r in pa if r["category"] in ROUTING_CATEGORIES],
                                   lambda r: r["output"] is not None and r["code"].get("allowed_status", {}).get("pass") is True)
    m["pact_forbidden_errors"] = count(pa, lambda r: code_failed(r, "public_text_regex") or judge_failed(r, FORBIDDEN_ERROR_CRITERIA))
    pj = [r for r in pa if "judge" in r["graders"]]
    m["pact_quality_pass"] = rate(pj, lambda r: r["pass"] is True) if judge_ran else {"value": None}
    m["pact_public_privacy"] = count(pa, lambda r: code_failed(r, "forbidden_text") or judge_failed(r, ("j7",)))
    m["pact_injection_violation"] = count([r for r in pa if r["category"] == "injection"],
                                          lambda r: not r["code_pass"] or judge_failed(r, INJECTION_PACT_CRITERIA))
    if live:
        ready = [r for r in sc if r["output"] is not None and r["output"].get("status") == "ready"]
        multi = [r for r in pa if r["multi_scenario"] and r["attempts"]]
        m["scenario_latency_p95"] = {"value": p95([r["latency_s"] for r in ready])}
        m["pact_latency_p95"] = {"value": p95([r["latency_s"] for r in multi])}
        sc_costs = [r["cost_usd"] for r in ready]
        pa_costs = [r["cost_usd"] for r in multi]
        if sc_costs and pa_costs:
            m["room_cost_estimate_mean"] = {"value": round(sum(sc_costs) / len(sc_costs) + sum(pa_costs) / len(pa_costs), 6)}
            m["room_cost_estimate_max"] = {"value": round(max(sc_costs) + max(pa_costs), 6)}
        else:
            m["room_cost_estimate_mean"] = {"value": None}
            m["room_cost_estimate_max"] = {"value": None}
    else:
        for key in ("scenario_latency_p95", "pact_latency_p95", "room_cost_estimate_mean", "room_cost_estimate_max"):
            m[key] = {"value": None}
    return m


def metric_value(entry):
    if "count" in entry:
        return entry["count"]
    return entry.get("value")


def compare(op, value, target):
    return {">=": value >= target, "<=": value <= target, "==": value == target}[op]


def apply_targets(metrics, targets, judge_validated, live):
    for key in METRIC_ORDER:
        entry = metrics.setdefault(key, {"value": None})
        spec = targets["metrics"][key]
        entry["target"] = f"{spec['op']} {spec['value']}"
        entry["target_status"] = spec.get("status", "draft")
        value = metric_value(entry)
        notes = []
        if spec.get("live_only") and not live:
            notes.append("live 전용")
        if spec.get("judge") and not judge_validated:
            notes.append("judge 미검증")
        if entry["target_status"] != "confirmed":
            notes.append("목표 미확정")
        if value is None or (spec.get("judge") and not judge_validated):
            entry["met"] = None
        else:
            entry["met"] = compare(spec["op"], value, spec["value"])
        entry["note"] = ", ".join(notes)
    return metrics


def latest_validation(results_dir, judge):
    path = Path(results_dir) / "judge_validation.csv"
    if not path.exists():
        return None
    found = None
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if (row["judge_version"] == judge["version"] and row["judge_pact_sha256"] == judge["pact"]["sha256"]
                    and row["judge_scenarios_sha256"] == judge["scenarios"]["sha256"]):
                found = row
    return found


def validation_columns(row):
    if row is None:
        return {}
    agreement = json.loads(row["agreement_by_criterion"] or "{}")
    return {"judge_label_run_id": row["label_run_id"], "judge_labeled_cases": row["labeled_cases"],
            "judge_agreement_min": fmt(min(agreement.values())) if agreement else "",
            "judge_agreement_by_criterion": row["agreement_by_criterion"],
            "judge_forbidden_recall": row["forbidden_recall"], "judge_validation_passed": row["passed"]}


def judge_is_validated(results_dir, judge, targets):
    path = Path(results_dir) / "judge_validation.csv"
    if not path.exists():
        return False
    if (targets.get("judge_validation") or {}).get("status") != "confirmed":
        return False
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if (row["judge_version"] == judge["version"] and row["judge_pact_sha256"] == judge["pact"]["sha256"]
                    and row["judge_scenarios_sha256"] == judge["scenarios"]["sha256"] and row["passed"] == "true"):
                return True
    return False


def git_info():
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True,
                               check=True).stdout.strip()
        return commit + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def new_run_id(results_dir, override=None):
    run_id = override or datetime.now().strftime("%Y-%m-%dT%H%M")
    if (Path(results_dir) / f"{run_id}.json").exists():
        raise EvalError("run_id_exists", run_id)
    return run_id


def write_results(results_dir, run_id, payload):
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{run_id}.json"
    with path.open("x", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return path


def append_csv(path, columns, row):
    path = Path(path)
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not new:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            old_rows = list(reader)
        if header != list(columns):
            unknown = [h for h in header if h not in columns]
            if unknown:
                raise EvalError("csv_unknown_columns", f"{path.name}: {unknown}")
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(columns))
                w.writeheader()
                for r in old_rows:
                    w.writerow({k: r.get(k, "") for k in columns})
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columns))
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in columns})


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def history_row(info, metrics):
    row = {k: fmt(info.get(k)) for k in HISTORY_COLUMNS if k in info}
    row["scenario_prompt"] = f"v{info['prompts']['scenarios']['version']}"
    row["pact_prompt"] = f"v{info['prompts']['pact']['version']}"
    row["pool"] = f"v{info['pool']['version']}"
    for key in METRIC_ORDER:
        row[key] = fmt(metric_value(metrics[key]))
    row.update(info.get("judge_validation_columns") or {})
    return row


def failed_checks(rec):
    out = [e["code"] for e in rec["errors"]]
    if rec["exposure"]:
        out.append("profile_exposure")
    out += [k for k, v in rec["code"].items() if v["pass"] is False]
    j = rec.get("judge")
    if j:
        out += [f"judge:{e['code']}" for e in j.get("errors", [])]
        out += [f"judge:{k}" for k in j.get("failed", [])]
    return out


def print_report(info, metrics, records):
    print(f"run_id {info['run_id']}  mode {info['mode']}  commit {info['commit']}  evalset {info['evalset_version']}  judge {info['judge_version']}")
    print(f"baseline_eligible {fmt(info['baseline_eligible'])}  draft_cases {info['draft_cases']}  draft_targets {info['draft_targets']}  "
          f"judge_validated {fmt(info['judge_validated'])}  incomplete {fmt(info['incomplete'])}  cost_usd {info['cost_usd']}")
    print()
    print(f"{'지표':34} {'값':>10} {'목표':>12} {'충족':>6}  비고")
    for key in METRIC_ORDER:
        e = metrics[key]
        value = metric_value(e)
        shown = "" if value is None else str(value)
        if "total" in e and e.get("value") is not None:
            shown = f"{e['passed']}/{e['total']}"
        met = {True: "예", False: "아니오", None: "-"}[e["met"]]
        print(f"{key:34} {shown:>10} {e['target']:>12} {met:>6}  {e['note']}")
    codes = metrics["pact_format_first"].get("first_output_error_codes") or {}
    if codes:
        print(f"\n추천 최초 출력 검증기 오류 코드: {codes}")
    print()
    print(f"{'케이스':10} {'범주':15} {'상태':18} {'판정':6}  실패한 검사")
    for r in records:
        status = r["output"].get("status") if r["output"] else "-"
        verdict = {True: "통과", False: "실패", None: "보류"}[r["pass"]]
        if r["not_run"]:
            verdict = "미실행"
        print(f"{r['id']:10} {r['category']:15} {status:18} {verdict:6}  {', '.join(failed_checks(r))}")


def make_context(args, mode, judge_enabled, config, judge):
    retry = (config.data.get("retry") or {})
    concurrency = int((config.data.get("concurrency") or {}).get("max_generations", 4))
    ctx = SimpleNamespace(pool_table=load_pool_table(), tool_call_limit=config.tool_call_limit,
                          budget=Budget(args.max_usd if mode == "live" else None), semaphore=asyncio.Semaphore(concurrency),
                          judge=judge, judge_enabled=judge_enabled, judge_cost=0.0)
    if mode == "live":
        if not os.environ.get("OPENAI_API_KEY"):
            raise EvalError("no_api_key", "live 모드에는 OPENAI_API_KEY가 필요하다")
        ctx.model = LiveModel(config, retry)
        ctx.judge_client = LiveJudge(config, retry)
    else:
        ctx.model = StoredModel(args.fixtures_dir)
        ctx.judge_client = StoredJudge(args.fixtures_dir)
    return ctx


def run_info(run_id, args, mode, config, judge, targets, evalset_version, cases, source_run_id=None):
    p = product()
    pool = p.load_pool()
    pool_spec = config.data.get("pool") or {}
    draft_cases = sum(1 for c in cases if is_draft_source(c))
    draft_targets = sum(1 for v in targets["metrics"].values() if v.get("status") != "confirmed")
    if (targets.get("judge_validation") or {}).get("status") != "confirmed":
        draft_targets += 1
    return {
        "run_id": run_id, "source_run_id": source_run_id, "mode": mode, "commit": git_info(), "change": args.change,
        "model": config.model, "reasoning": config.reasoning_effort,
        "prompts": {s: {"version": config.prompts[s]["version"], "body_sha256": sha256_text(config.prompts[s]["body"]),
                        "schema_version": config.prompts[s]["schema_version"]} for s in STAGES},
        "pool": {"version": pool.get("pool_version"), "sha256": pool_spec.get("sha256")},
        "evalset_version": evalset_version, "evalset_path": str(Path(args.evalset).resolve().relative_to(ROOT))
        if Path(args.evalset).resolve().is_relative_to(ROOT) else str(args.evalset),
        "judge_version": judge["version"],
        "judge_sha256": {s: judge[s]["sha256"] for s in STAGES},
        "targets_version": targets.get("targets_version"), "golden_tests": args.golden,
        "draft_cases": draft_cases, "draft_targets": draft_targets,
        "cases_selected": [c["id"] for c in cases],
    }


def select_cases(cases, spec):
    if not spec:
        return cases
    wanted = [x.strip() for x in spec.split(",") if x.strip()]
    known = {c["id"] for c in cases}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise EvalError("unknown_case", ",".join(unknown))
    return [c for c in cases if c["id"] in set(wanted)]


async def run_main(args):
    p = product()
    config = p.LLMConfig.load(LLM_CONFIG_PATH, root=ROOT)
    targets = load_targets(args.design)
    judge = load_judge(args.judge_prompt)
    all_cases, evalset_version = load_evalset(args.evalset)
    source = None
    reuse = {}
    if args.judge_only:
        source = json.loads((Path(args.results_dir) / f"{args.judge_only}.json").read_text(encoding="utf-8"))
        reuse = {r["id"]: r for r in source["cases"]}
        known = {c["id"] for c in all_cases}
        missing = sorted(set(reuse) - known)
        if missing:
            raise EvalError("source_case_missing", ",".join(missing))
        if source["info"]["evalset_version"] != evalset_version:
            print(f"경고: 데이터셋이 출력 실행 뒤에 바뀌었다({source['info']['evalset_version']} -> {evalset_version}). "
                  "입력이 같은 케이스만 다시 판정하고, 입력 해시가 다르면 오류로 남긴다.", file=sys.stderr)
        cases = [c for c in all_cases if c["id"] in reuse]
        mode = args.mode
    else:
        cases = select_cases(all_cases, args.cases)
        mode = args.mode
    if mode == "live" and any(c["stage"] == "pact" for c in cases):
        raise EvalError("pact_live_retired", "추천 v14(챌린지 방식)에 맞춘 평가셋이 아직 없다. pact 케이스는 stored 모드로만 돈다")
    run_id = new_run_id(args.results_dir, args.run_id)
    judge_enabled = not args.skip_judge
    ctx = make_context(args, mode, judge_enabled, config, judge)
    tasks = [run_case(c, ctx, reuse.get(c["id"])) for c in cases]
    records = await asyncio.gather(*tasks)
    judge_validated = judge_is_validated(args.results_dir, judge, targets)
    validation = latest_validation(args.results_dir, judge) if judge_enabled else None
    live = mode == "live" and not args.judge_only
    metrics = compute_metrics(records, live=live, judge_ran=judge_enabled)
    model_cost = sum(r["cost_usd"] for r in records) if not args.judge_only else 0.0
    total_cost = round(model_cost + ctx.judge_cost, 6)
    metrics["eval_run_cost"] = {"value": total_cost if mode == "live" else None}
    apply_targets(metrics, targets, judge_validated, live)
    info = run_info(run_id, args, mode, config, judge, targets, evalset_version, cases,
                    source_run_id=args.judge_only)
    incomplete = any(r["not_run"] or (r.get("judge") or {}).get("not_run") for r in records)
    full_set = len(cases) == len(all_cases)
    if source is not None:
        info["source_evalset_version"] = source["info"]["evalset_version"]
    info["judge_validation_columns"] = validation_columns(validation)
    info.update({"judge_validated": judge_validated, "cost_usd": total_cost, "incomplete": incomplete,
                 "judge_enabled": judge_enabled, "full_evalset": full_set,
                 "baseline_eligible": info["draft_cases"] == 0 and info["draft_targets"] == 0 and full_set and not incomplete
                 and mode == "live"})
    payload = {"info": info, "metrics": metrics, "cases": records}
    write_results(args.results_dir, run_id, payload)
    append_csv(Path(args.results_dir) / "history.csv", HISTORY_COLUMNS, history_row(info, metrics))
    print_report(info, metrics, records)
    return payload


def load_labels(path, label_run_id):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("run_id") == label_run_id:
            rows.append(row)
    return rows


def validate_judge(args):
    targets = load_targets(args.design)
    judge = load_judge(args.judge_prompt)
    rules = targets.get("judge_validation") or {}
    run = json.loads((Path(args.results_dir) / f"{args.run}.json").read_text(encoding="utf-8"))
    label_run_id = run["info"].get("source_run_id") or run["info"]["run_id"]
    if run["info"]["judge_version"] != judge["version"] or run["info"]["judge_sha256"] != {s: judge[s]["sha256"] for s in STAGES}:
        raise EvalError("judge_changed", "실행의 judge 버전·해시가 현재 judge_prompt.md와 다르다")
    labels = load_labels(args.validate_judge, label_run_id)
    by_id = {r["id"]: r for r in run["cases"]}
    per = {}
    human_false = 0
    judge_false = 0
    compared_cases = 0
    disagreements = []
    forbidden = set(rules.get("forbidden_criteria") or [])
    for lab in labels:
        rec = by_id.get(lab["id"])
        if rec is None or not rec.get("judge") or not rec["judge"].get("criteria"):
            disagreements.append({"id": lab["id"], "reason": "judge 판정 없음"})
            continue
        compared_cases += 1
        jc = rec["judge"]["criteria"]
        for key, human in lab.get("labels", {}).items():
            judged = (jc.get(key) or {}).get("pass")
            stat = per.setdefault(key, {"match": 0, "total": 0})
            stat["total"] += 1
            if judged == human:
                stat["match"] += 1
            else:
                disagreements.append({"id": lab["id"], "criterion": key, "human": human, "judge": judged})
            if key in forbidden and human is False:
                human_false += 1
                if judged is False:
                    judge_false += 1
    agreement = {k: round(v["match"] / v["total"], 4) for k, v in sorted(per.items()) if v["total"]}
    recall = round(judge_false / human_false, 4) if human_false else None
    passed = bool(agreement) and all(a >= rules.get("agreement_min", 0.8) for a in agreement.values())
    passed = passed and (recall is None or recall >= rules.get("forbidden_recall_min", 1.0))
    row = {"created_at": datetime.now().isoformat(timespec="seconds"), "judge_version": judge["version"],
           "judge_pact_sha256": judge["pact"]["sha256"], "judge_scenarios_sha256": judge["scenarios"]["sha256"],
           "judge_run_id": args.run, "label_run_id": label_run_id, "labeled_cases": len(labels),
           "compared_cases": compared_cases, "agreement_by_criterion": json.dumps(agreement, ensure_ascii=False),
           "forbidden_recall": fmt(recall), "thresholds_status": rules.get("status", "draft"), "passed": fmt(passed)}
    append_csv(Path(args.results_dir) / "judge_validation.csv", VALIDATION_COLUMNS, row)
    print(f"judge {judge['version']}  라벨 실행 {label_run_id}  라벨 {len(labels)}건  비교 {compared_cases}건")
    for k, a in agreement.items():
        print(f"  {k}: {a}")
    print(f"금지 기준 재현율: {fmt(recall) or '잴 수 없음'}  합격: {fmt(passed)}  기준 상태: {rules.get('status', 'draft')}")
    for d in disagreements:
        print(f"  불일치 {d}")
    return {"agreement": agreement, "recall": recall, "passed": passed, "disagreements": disagreements}


async def calibrate(args):
    p = product()
    config = p.LLMConfig.load(LLM_CONFIG_PATH, root=ROOT)
    judge = load_judge(args.judge_prompt)
    run_id = new_run_id(args.results_dir, args.run_id)
    ctx = make_context(args, args.mode, True, config, judge)
    inputs = {}
    for line in CALIBRATION_INPUTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            inputs[row["case_id"]] = row["input"]
    rows = [json.loads(line) for line in CALIBRATION_EVAL.read_text(encoding="utf-8").splitlines() if line.strip()]

    async def one(row):
        key = f"calibrate_{row['case_id']}"
        judge_input = {"input": inputs[row["case_id"]], "output": row["output"],
                       "case_criteria": {"allowed_results": row["criteria"].get("allowed_results"),
                                         "immediate_failures": row["criteria"].get("immediate_failures")}}
        try:
            async with ctx.semaphore:
                raw, _, cost = await ctx.judge_client.call(key, "pact", judge_input, judge["pact"])
        except NoStoredOutput as exc:
            return {"case_id": row["case_id"], "human": row["human_verdict"]["final"], "judge": None, "error": exc.code}
        ctx.judge_cost += cost or 0.0
        verdict = interpret_judge("pact", raw, judge["pact"]["schema"], row["output"])
        jp = "pass" if verdict["pass"] else "fail"
        return {"case_id": row["case_id"], "human": row["human_verdict"]["final"], "judge": jp, "verdict": verdict}

    results = await asyncio.gather(*(one(r) for r in rows))
    compared = [r for r in results if r["judge"] is not None]
    agree = sum(1 for r in compared if r["judge"] == r["human"])
    payload = {"run_id": run_id, "judge_version": judge["version"], "judge_sha256": judge["pact"]["sha256"],
               "compared": len(compared), "agreement": round(agree / len(compared), 4) if compared else None,
               "cost_usd": round(ctx.judge_cost, 6), "cases": results}
    out = Path(args.results_dir) / f"calibration_{run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"사전 보정 {judge['version']}: {agree}/{len(compared)} 일치")
    for r in results:
        print(f"  {r['case_id']} 사람 {r['human']} judge {r['judge']} {r.get('error', '')}")
    return payload


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="evals 러너")
    ap.add_argument("--mode", choices=("stored", "live"), default="stored")
    ap.add_argument("--change", default="")
    ap.add_argument("--golden", default="")
    ap.add_argument("--cases", default="")
    ap.add_argument("--skip-judge", action="store_true")
    ap.add_argument("--judge-only", metavar="RUN_ID")
    ap.add_argument("--validate-judge", metavar="LABELS")
    ap.add_argument("--run", metavar="RUN_ID")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--max-usd", type=float, default=3.0)
    ap.add_argument("--fixtures-dir", default=str(FIXTURES_DIR))
    ap.add_argument("--evalset", default=str(EVALSET_PATH))
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    ap.add_argument("--design", default=str(DESIGN_PATH))
    ap.add_argument("--judge-prompt", default=str(JUDGE_PATH))
    ap.add_argument("--run-id")
    args = ap.parse_args(argv)
    if args.validate_judge and not args.run:
        ap.error("--validate-judge에는 --run이 필요하다")
    if args.judge_only and args.skip_judge:
        ap.error("--judge-only와 --skip-judge는 함께 쓸 수 없다")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.validate_judge:
            validate_judge(args)
        elif args.calibrate:
            asyncio.run(calibrate(args))
        else:
            asyncio.run(run_main(args))
    except EvalError as exc:
        print(f"오류 {exc.code}: {exc.detail}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
