import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "harness" / "fixtures" / "evals"
SYNTHETIC = "러너 기계 확인용 합성 응답. 판정 근거 아님"
REGRESSION_RUN = "v11-regression-20261007"


def rows(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line.strip()]


def attempt(output, opened=None):
    return {"raw_output": json.dumps(output, ensure_ascii=False), "response_status": "completed",
            "opened_template_ids": list(opened or []), "usage": None, "latency_s": None}


def stored_outputs():
    out = {}
    d01 = json.loads((ROOT / "config/replay/scenario_set_d01.json").read_text(encoding="utf-8"))
    out["sc_D01"] = {"source": f"config/replay/scenario_set_d01.json ({d01.get('source', '')})",
                     "attempts": [attempt(d01["scenario_set"])]}
    for row in rows("docs/spikes/grounded_pact_eval.jsonl"):
        out[f"pa_{row['case_id']}"] = {"source": f"docs/spikes/grounded_pact_eval.jsonl#{row['case_id']} (v11 출력)",
                                       "attempts": [attempt(row["output"])]}
    for row in rows("docs/spikes/grounded_pact_v11_regression_outputs.jsonl"):
        if row.get("run_id") != REGRESSION_RUN:
            continue
        out[f"pa_{row['case_id']}"] = {
            "source": f"docs/spikes/grounded_pact_v11_regression_outputs.jsonl#{row['case_id']} run_id {REGRESSION_RUN}",
            "attempts": [attempt(row["output"])]}
    for row in rows("docs/spikes/legacy/grounded_pact_v4_outputs.jsonl"):
        if row.get("case_id") == "R06":
            out["pa_R06"] = {"source": "docs/spikes/legacy/grounded_pact_v4_outputs.jsonl#R06 (v4 출력, 스키마 v3)",
                             "attempts": [attempt(row["output"])]}
    return out


def verdict(passed, reason="러너 기계 확인용 합성 판정"):
    return {"reason": reason if passed is not None else "해당하지 않음(합성)", "pass": passed}


def pact_judge(output):
    status = output.get("status")
    alternatives = output.get("conditional_alternatives") or []
    unresolved = output.get("unresolved_conditions") or []
    crit = {k: verdict(True) for k in ("j1", "j2", "j3", "j5", "j7")}
    crit["j4"] = verdict(None if status == "needs_information" else True)
    crit["j6"] = verdict(None if output.get("clauses") is None and not alternatives else True)
    crit["j8"] = verdict(None if not unresolved and status == "proposed" else True)
    return {"criteria": {k: crit[k] for k in ("j1", "j2", "j3", "j4", "j5", "j6", "j7", "j8")}, "overall_note": ""}


def scenario_judge(output):
    items = [{"template_id": s["template_id"], **{k: verdict(True) for k in ("s1", "s2", "s3", "s4", "s5")}}
             for s in output["scenarios"]]
    return {"scenarios": items, "request": {"s6": verdict(True), "s7": verdict(True)}, "overall_note": ""}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    outputs = stored_outputs()
    for case_id, data in sorted(outputs.items()):
        write(OUT / "outputs" / f"{case_id}.json", data)
    for case_id in ("pa_H01", "pa_H02"):
        output = json.loads(outputs[case_id]["attempts"][0]["raw_output"])
        write(OUT / "judge" / f"{case_id}.json", {"source": SYNTHETIC, "raw_output": json.dumps(pact_judge(output), ensure_ascii=False)})
    d01 = json.loads(outputs["sc_D01"]["attempts"][0]["raw_output"])
    write(OUT / "judge" / "sc_D01.json", {"source": SYNTHETIC, "raw_output": json.dumps(scenario_judge(d01), ensure_ascii=False)})
    print(f"outputs {len(outputs)}개, judge 3개 -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
