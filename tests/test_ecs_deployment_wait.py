"""ECS 완료 판정의 조기 실패와 롤백 오인을 실제 AWS 호출 없이 재현한다."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def deployment(state, *, old=False):
    return {
        "id": "old" if old else "new",
        "taskDefinition": "app:9" if old else "app:10",
        "status": "PRIMARY",
        "rolloutState": state,
        "runningCount": 2,
        "desiredCount": 2,
        "pendingCount": 0,
    }


@pytest.mark.parametrize("scenario, expected_code, polls, message", [
    ("completes", 0, 2, "rollout state: COMPLETED"),
    ("fails", 1, 2, "entered state FAILED"),
    ("rolls_back", 1, 2, "replaced or rolled back"),
    ("times_out", 1, 60, "Timed out waiting"),
])
def test_wait_tracks_this_deployment(tmp_path, scenario, expected_code, polls, message):
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
    step = next(s for s in workflow["jobs"]["deploy"]["steps"]
                if s.get("name") == "Update ECS service and wait for stability")
    assert step["timeout-minutes"] == 10
    pending = deployment("IN_PROGRESS")
    final = {
        "completes": deployment("COMPLETED"),
        "fails": deployment("FAILED"),
        "rolls_back": deployment("COMPLETED", old=True),
        "times_out": pending,
    }[scenario]
    responses = []
    for target in (pending, final):
        responses.append({"failures": [], "services": [{
            "taskDefinition": target["taskDefinition"], "runningCount": 2,
            "desiredCount": 2, "pendingCount": 0, "deployments": [target], "events": [],
        }]})
    fixture = tmp_path / "responses.json"
    fixture.write_text(json.dumps({"update": {"service": {"deployments": [pending]}}, "reads": responses}))
    count = tmp_path / "reads"
    sleeps = tmp_path / "sleeps"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    aws = bin_dir / "aws"
    aws.write_text(f"#!{sys.executable}\n" + """
import json, os, sys
from pathlib import Path
data = json.loads(Path(os.environ['RESPONSES']).read_text())
assert sys.argv[1] == 'ecs'
assert sys.argv[sys.argv.index('--cluster') + 1] == 'test-cluster'
assert sys.argv[sys.argv.index('--output') + 1] == 'json'
if sys.argv[2] == 'update-service':
    assert sys.argv[sys.argv.index('--task-definition') + 1] == 'app:10'
    print(json.dumps(data['update']))
else:
    assert sys.argv[2] == 'describe-services'
    count = Path(os.environ['READS'])
    n = int(count.read_text()) if count.exists() else 0
    count.write_text(str(n + 1))
    print(json.dumps(data['reads'][min(n, len(data['reads']) - 1)]))
""")
    aws.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$SLEEPS"\n')
    sleep.chmod(0o755)
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CLUSTER": "test-cluster", "SERVICE": "test-service", "TASKDEF": "app:10",
        "RESPONSES": str(fixture), "READS": str(count), "SLEEPS": str(sleeps),
    }
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]],
                            env=env, cwd=tmp_path, capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    assert result.returncode == expected_code, output
    assert message in output
    assert int(count.read_text()) == polls
    assert sleeps.read_text().splitlines() == ["10"] * (polls - 1)
