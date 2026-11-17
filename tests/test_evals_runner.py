import asyncio
import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_evals", ROOT / "evals" / "run_evals.py")
run_evals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_evals)


def evalset_by_id():
    cases, _ = run_evals.load_evalset()
    return {c["id"]: c for c in cases}


def test_design_judge_and_evalset_load():
    targets = run_evals.load_targets()
    assert set(run_evals.METRIC_ORDER) <= set(targets["metrics"])
    judge = run_evals.load_judge()
    assert judge["version"]
    cases, version = run_evals.load_evalset()
    assert version.startswith(f"{len(cases)} cases, ")
    for case in cases:
        assert set(case["expect"]) <= run_evals.EXPECT_KEYS, case["id"]
        assert set(case) <= run_evals.CASE_KEYS, case["id"]


def test_every_query_and_criteria_resolves():
    for case in evalset_by_id().values():
        raw = run_evals.resolve_query(case["query"])
        assert isinstance(raw, dict), case["id"]
        if "criteria_ref" in case["expect"]:
            crit = run_evals.resolve_criteria(case["expect"]["criteria_ref"])
            assert crit["allowed_results"], case["id"]


def test_resolve_structured_inputs_applies_remove_and_replace():
    s2 = run_evals.resolve_query("docs/research/structured_output_inputs.json#S2")
    assert "destination" not in s2["trip"]
    s4 = run_evals.resolve_query("docs/research/structured_output_inputs.json#S4")
    assert s4["requested_count"] == 9


def test_resolve_jsonl_requires_identical_duplicates(tmp_path):
    rows = [{"case_id": "X", "input": {"a": 1}}, {"case_id": "X", "input": {"a": 1}}]
    path = tmp_path / "same.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert run_evals.resolve_query(f"{path.relative_to(tmp_path)}#X", root=tmp_path) == {"a": 1}
    rows[1]["input"] = {"a": 2}
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    with pytest.raises(run_evals.EvalError) as err:
        run_evals.resolve_query(f"{path.relative_to(tmp_path)}#X", root=tmp_path)
    assert err.value.code == "query_inputs_differ"


def test_inline_query_is_copied():
    query = {"trip": {"duration_days": 1}}
    out = run_evals.resolve_query(query)
    out["trip"]["duration_days"] = 2
    assert query["trip"]["duration_days"] == 1


def test_pool_table_covers_pool_and_duration_rule():
    table = run_evals.load_pool_table()
    pool_ids = {item["template_id"] for item in run_evals.product().load_pool()["scenario_pool"]}
    assert set(table) == pool_ids
    one_day = [t for t, row in table.items() if row["min_days"] == 1]
    overnight = [t for t, row in table.items() if row["min_days"] == 2]
    two_nights = [t for t, row in table.items() if row["min_days"] == 3]
    assert one_day and overnight and two_nights
    output = {"scenarios": [{"template_id": one_day[0]}, {"template_id": overnight[0]}, {"template_id": two_nights[0]}]}
    assert [v["template_id"] for v in run_evals.duration_violations({"duration_days": 1}, output, table)] == overnight[:1] + two_nights[:1]
    assert [v["template_id"] for v in run_evals.duration_violations({"duration_days": 2}, output, table)] == two_nights[:1]
    assert run_evals.duration_violations({"duration_days": 3}, output, table) == []
    with pytest.raises(run_evals.EvalError):
        run_evals.duration_violations({"duration_days": "며칠"}, output, table)


def test_public_text_regex_groups():
    groups = [["(?<![가-힣])한 ?시간 ?이상", "1 ?시간 ?이상"], ["(?<![가-힣])한 ?시간(?! ?이상)", "1 ?시간(?! ?이상)"]]
    assert run_evals.regex_groups(groups, ["각자 필요한 시간을 정해요"]) == [False, False]
    assert run_evals.regex_groups(groups, ["A는 한 시간 이상 구경해요"]) == [True, False]
    assert run_evals.regex_groups(groups, ["B는 한 시간 쉬어요"]) == [False, True]


def pact_verdict(**overrides):
    crit = {k: {"reason": "r", "pass": True} for k in run_evals.PACT_CRITERIA}
    crit["j8"] = {"reason": "r", "pass": None}
    for key, value in overrides.items():
        crit[key] = {"reason": "r", "pass": value}
    return json.dumps({"criteria": crit, "overall_note": ""})


def test_judge_applicability_rules():
    schema = run_evals.load_judge()["pact"]["schema"]
    output = {"status": "proposed", "clauses": [{"action": "a"}], "positions": []}
    ok = run_evals.interpret_judge("pact", pact_verdict(), schema, output)
    assert ok["pass"] is True and ok["errors"] == []
    wrong = run_evals.interpret_judge("pact", pact_verdict(j8=True), schema, output)
    assert wrong["pass"] is False and wrong["errors"][0]["code"] == "judge_applicability"
    failed = run_evals.interpret_judge("pact", pact_verdict(j2=False), schema, output)
    assert failed["pass"] is False and failed["failed"] == ["j2"]
    broken = run_evals.interpret_judge("pact", "모두 통과", schema, output)
    assert broken["errors"][0]["code"] == "judge_parse_error"


class FakeModel:
    def __init__(self, raw, cost):
        self.raw = raw
        self.cost = cost
        self.calls = 0

    async def call(self, case_id, stage, model_input, repair_errors, round_no):
        self.calls += 1
        result = run_evals.product().LLMResult(raw_output=self.raw)
        return result, 1.0, self.cost


def test_budget_stops_before_next_call():
    model = FakeModel("{}", 0.6)
    ctx = SimpleNamespace(budget=run_evals.Budget(1.0), semaphore=asyncio.Semaphore(1), model=model)
    def validate(raw):
        return {"valid": False, "errors": [{"code": "schema_violation"}]}

    case = {"id": "x"}
    first = asyncio.run(run_evals.generate_case(case, "pact", {}, validate, ctx))
    assert model.calls == 2 and first["not_run"] is False and first["output"] is None
    second = asyncio.run(run_evals.generate_case(case, "pact", {}, validate, ctx))
    assert second["not_run"] is True and model.calls == 2


def test_results_file_is_never_overwritten(tmp_path):
    run_evals.write_results(tmp_path, "R1", {"a": 1})
    with pytest.raises(FileExistsError):
        run_evals.write_results(tmp_path, "R1", {"a": 2})
    with pytest.raises(run_evals.EvalError):
        run_evals.new_run_id(tmp_path, "R1")


def test_stored_run_writes_result_and_history(tmp_path):
    args = run_evals.parse_args(["--mode", "stored", "--cases", "sc_D01,pa_P2", "--results-dir", str(tmp_path),
                                 "--run-id", "T1", "--change", "test", "--golden", "-"])
    payload = asyncio.run(run_evals.run_main(args))
    assert (tmp_path / "T1.json").exists()
    with (tmp_path / "history.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["run_id"] == "T1" and list(rows[0]) == list(run_evals.HISTORY_COLUMNS)
    assert payload["info"]["baseline_eligible"] is False
    assert {r["id"] for r in payload["cases"]} == {"sc_D01", "pa_P2"}


def test_judge_only_rejudges_after_expect_change_but_not_input_change(tmp_path):
    original = tmp_path / "evalset_a.jsonl"
    cases = [json.loads(line) for line in run_evals.EVALSET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    keep = [c for c in cases if c["id"] in ("pa_H01", "pa_P2")]
    original.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in keep), encoding="utf-8")
    first = run_evals.parse_args(["--mode", "stored", "--evalset", str(original), "--results-dir", str(tmp_path),
                                  "--run-id", "OUT", "--skip-judge"])
    asyncio.run(run_evals.run_main(first))
    changed = tmp_path / "evalset_b.jsonl"
    keep[0]["expect"]["forbidden_text"] = ["존재하지-않는-문구"]
    keep[1]["query"] = {"participant_ids": [], "scenarios": [], "responses": [], "request": "다른 입력"}
    changed.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in keep), encoding="utf-8")
    second = run_evals.parse_args(["--mode", "stored", "--evalset", str(changed), "--results-dir", str(tmp_path),
                                   "--run-id", "J", "--judge-only", "OUT"])
    payload = asyncio.run(run_evals.run_main(second))
    recs = {r["id"]: r for r in payload["cases"]}
    assert recs["pa_H01"]["code"]["forbidden_text"]["pass"] is True
    assert recs["pa_H01"]["judge"]["pass"] is True
    assert [e["code"] for e in recs["pa_P2"]["errors"]] == ["input_changed"]
    assert payload["info"]["source_evalset_version"] != payload["info"]["evalset_version"]
