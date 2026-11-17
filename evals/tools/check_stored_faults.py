"""저장 응답 사본으로 evals 오답 주입 12항목을 확인한다. 실제 모델 호출 없음."""

import asyncio
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("run_evals", ROOT / "evals/run_evals.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def hashes():
    paths = [ROOT / "evals/evalset.jsonl", ROOT / "evals/judge_labels.jsonl"]
    paths += sorted((ROOT / "tests/harness/fixtures/evals").rglob("*.json"))
    paths += sorted((ROOT / "evals/results").glob("*.*"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


async def main():
    before = hashes()
    cases = {c["id"]: c for c in r.load_evalset()[0]}
    judge = r.load_judge()
    config = r.product().LLMConfig.load(r.LLM_CONFIG_PATH, root=ROOT)
    rows = []
    with tempfile.TemporaryDirectory(prefix="evals-faults-") as temp:
        base = Path(temp)

        async def run(number, case_id, output_edit=None, case_edit=None, judge_edit=None, alias=None):
            folder = base / str(number)
            shutil.copytree(r.FIXTURES_DIR, folder)
            case = copy.deepcopy(cases[case_id])
            if case_edit:
                case_edit(case)
            if alias:
                for kind in ("outputs", "judge"):
                    source = folder / kind / f"{case_id}.json"
                    if source.exists():
                        shutil.copyfile(source, folder / kind / f"{alias}.json")
                case["id"] = alias
            output_file = folder / "outputs" / f"{case['id']}.json"
            fixture = json.loads(output_file.read_text())
            if output_edit:
                output = json.loads(fixture["attempts"][0]["raw_output"])
                output_edit(output, fixture["attempts"][0])
                fixture["attempts"][0]["raw_output"] = json.dumps(output, ensure_ascii=False)
                output_file.write_text(json.dumps(fixture, ensure_ascii=False))
            if judge_edit:
                p = folder / "judge" / f"{case['id']}.json"
                data = json.loads(p.read_text())
                data["raw_output"] = judge_edit(data["raw_output"])
                p.write_text(json.dumps(data, ensure_ascii=False))
            args = r.parse_args(["--fixtures-dir", str(folder)])
            ctx = r.make_context(args, "stored", True, config, judge)
            rec = await r.run_case(case, ctx)
            return rec, r.compute_metrics([rec], live=False, judge_ran=True)

        def check(number, expectation, ok):
            rows.append({"number": number, "expected": expectation, "matched": bool(ok)})
            if not ok:
                raise AssertionError(rows[-1])

        def overnight(out, attempt):
            template = next(t for t in r.product().load_pool()["scenario_pool"] if t["template_id"] == "shared_bed")
            out["scenarios"][0] = {k: template[k] for k in ("template_id", "scene", "question", "options")}

        rec, m = await run(1, "sc_D01", output_edit=overnight)
        check(1, "검증기 통과, 기간 부적합 1건", rec["output"] is not None and m["scenario_duration_violation"]["count"] == 1)
        rec, _ = await run(
            2, "sc_D01", output_edit=lambda o, a: a.update(opened_template_ids=[s["template_id"] for s in o["scenarios"]], usage={"tool_calls": 6})
        )
        check(2, "조회한 6개 문항의 도구 계약 통과", rec["code"]["tool_contract"]["pass"])
        rec, m = await run(3, "sc_D01", output_edit=lambda o, a: o["scenarios"][0].update(scene="친구1 " + o["scenarios"][0]["scene"]))
        check(3, "검증기 통과, 프로필 노출 1건", rec["output"] is not None and m["scenario_profile_exposure"]["count"] == 1)
        rec, m = await run(4, "pa_E03", output_edit=lambda o, a: o.update(status="needs_information"))
        check(4, "검증기 통과, 상태 라우팅 0/1", rec["output"] is not None and m["pact_routing_match"]["passed"] == 0)
        # P1의 실제 기대값은 유지한다. 검사기 확인용 사본에만 정규식 조건을 넣는다.
        groups = [["한 시간 이상"], ["한 시간 쉬어요"]]

        def add_rule(c):
            c["expect"].update(public_text_regex=groups)

        rec0, _ = await run("5-before", "pa_P1", case_edit=add_rule)
        rec, _ = await run(
            5,
            "pa_P1",
            case_edit=add_rule,
            output_edit=lambda o, a: o["clauses"][0].update(
                action=o["clauses"][0]["action"] + " {{participant:A}}은/는 한 시간 이상 구경하고, {{participant:B}}은/는 한 시간 쉬어요."
            ),
        )
        check(
            5,
            "합성 정규식 두 묶음: 실패에서 통과로 전환",
            rec0["code"]["public_text_regex"]["pass"] is False and rec["code"]["public_text_regex"]["groups"] == [True, True],
        )
        rec, m = await run(6, "pa_H01", case_edit=lambda c: c["expect"].update(forbidden_text=["체험"]))
        check(6, "금지 문구 실패, 공개 문장 개인정보 1건", rec["code"]["forbidden_text"]["pass"] is False and m["pact_public_privacy"]["count"] == 1)

        def verdict(raw, key, value):
            data = json.loads(raw)
            data["criteria"][key]["pass"] = value
            return json.dumps(data)

        rec, m = await run(7, "pa_H01", judge_edit=lambda s: verdict(s, "j2", False))
        check(
            7,
            "j2 실패, 금지 오류 1건, 조율 품질 0/1",
            rec["judge"]["pass"] is False and m["pact_forbidden_errors"]["count"] == 1 and m["pact_quality_pass"]["passed"] == 0,
        )
        rec, _ = await run(8, "pa_H01", judge_edit=lambda s: verdict(s, "j6", None))
        check(
            8, "judge 해당 여부 오류, 케이스 실패", rec["pass"] is False and any(e["code"] == "judge_applicability" for e in rec["judge"]["errors"])
        )
        rec, m = await run(9, "pa_H02", judge_edit=lambda s: "모두 통과")
        check(
            9,
            "judge 파싱 오류, 분모 1 유지",
            rec["pass"] is False and m["pact_quality_pass"]["total"] == 1 and any(e["code"] == "judge_parse_error" for e in rec["judge"]["errors"]),
        )
        original, _ = await run("10-original", "pa_H02")
        cloned, _ = await run(10, "pa_H02", alias="pa_X02")
        check(10, "ID 변경 후 코드·judge·최종 판정 동일", all(original[k] == cloned[k] for k in ("code", "judge", "pass")))
        rec, _ = await run(11, "pa_H02", case_edit=lambda c: c["expect"].update(max_clauses=1))
        check(11, "알 수 없는 기대값 키 오류", rec["pass"] is False and any(e["code"] == "unknown_expect_key" for e in rec["errors"]))
        normal, _ = await run("12-normal", "pa_H01")
        run_id = "fault-check"
        payload = {
            "info": {"run_id": run_id, "judge_version": judge["version"], "judge_sha256": {s: judge[s]["sha256"] for s in r.STAGES}},
            "cases": [normal],
        }
        (base / f"{run_id}.json").write_text(json.dumps(payload))
        labels = {k: v["pass"] for k, v in normal["judge"]["criteria"].items()}
        labels["j2"] = False
        label_path = base / "labels.jsonl"
        label_path.write_text(json.dumps({"run_id": run_id, "id": "pa_H01", "labels": labels}) + "\n")
        args = r.parse_args(["--validate-judge", str(label_path), "--run", run_id, "--results-dir", str(base)])
        with contextlib.redirect_stdout(io.StringIO()):
            validation = r.validate_judge(args)
        check(12, "합성 라벨 j2 재현율 0, 검증 실패", validation["recall"] == 0 and validation["passed"] is False)
    assert hashes() == before, "원본 자료 변경"
    print(json.dumps({"checks": rows, "matched": len(rows), "originals_unchanged": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
