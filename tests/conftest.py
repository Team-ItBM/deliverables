"""서버 계약 테스트 fixture와 server_case 표지.

기존 테스트(test_pact_golden.py, test_scenario_golden.py, test_tools.py, test_pool.py)는 이 파일의 fixture를 쓰지 않는다.
여기서 하는 일은 표지 등록, 테스트 결과 기록(hookwrapper), 서버·DB fixture뿐이며 기존 테스트의 수집과 실행을 바꾸지 않는다.

skip 규칙
  travel.server.app을 import할 수 없거나 create_app이 없으면 케이스 테스트를 skip한다(사유: 서버 미구현).
  travel.server 밖의 모듈을 찾지 못하는 등 그 밖의 import 오류는 실패로 드러낸다.
  TEST_DATABASE_URL이 없으면 케이스 테스트와 DB fixture 검사를 skip한다(사유: 테스트 DB 없음).
"""

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "tests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from harness.server import db as testdb  # noqa: E402
from harness.server.cases import CaseExpect, cases_by_id, load_cases_file  # noqa: E402

MARKER = "server_case"
MARKER_DUMP_ENV = "SERVER_CASE_MARKER_DUMP"
SERVER_MODULES = ("travel", "travel.server", "travel.server.app")
SKIP_NO_SERVER = "서버 미구현"
SKIP_NO_DB = "테스트 DB 없음: TEST_DATABASE_URL이 없다"


def pytest_configure(config):
    config.addinivalue_line("markers", f"{MARKER}(id): server_cases.yaml의 케이스 ID 하나에 대응하는 서버 계약 테스트")


def pytest_collection_modifyitems(config, items):
    """SERVER_CASE_MARKER_DUMP가 있으면 수집한 server_case 표지를 그 파일에 JSON으로 쓴다(일대일 검사용)."""
    path = os.environ.get(MARKER_DUMP_ENV)
    if not path:
        return
    rows = []
    for item in items:
        marks = list(item.iter_markers(name=MARKER))
        if marks or Path(str(item.fspath)).name.startswith("test_server_"):
            rows.append({
                "nodeid": item.nodeid,
                "file": Path(str(item.fspath)).name,
                "ids": [m.args[0] if m.args else None for m in marks],
            })
    Path(path).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


_SERVER = None


def load_server():
    """(서버 모듈 묶음, skip 사유)를 돌려준다. 서버 미구현 밖의 import 오류는 그대로 낸다."""
    global _SERVER
    if _SERVER is not None:
        return _SERVER
    try:
        app_module = importlib.import_module("travel.server.app")
    except ModuleNotFoundError as exc:
        if exc.name in SERVER_MODULES:
            _SERVER = (None, f"{SKIP_NO_SERVER}: {exc.name} 모듈을 찾을 수 없다")
            return _SERVER
        raise
    if not callable(getattr(app_module, "create_app", None)):
        _SERVER = (None, f"{SKIP_NO_SERVER}: travel.server.app에 create_app이 없다")
        return _SERVER
    bundle = SimpleNamespace(
        app=app_module,
        llm=importlib.import_module("travel.server.llm"),
        db=importlib.import_module("travel.server.db"),
        render=importlib.import_module("travel.server.render"),
    )
    _SERVER = (bundle, None)
    return _SERVER


@pytest.fixture
def server():
    bundle, reason = load_server()
    if bundle is None:
        pytest.skip(reason)
    return bundle


@pytest.fixture
def admin_database_url():
    url = testdb.admin_url()
    if not url:
        pytest.skip(SKIP_NO_DB)
    return url


@pytest.fixture
def database_url(admin_database_url):
    """테스트마다 새 데이터베이스를 만들고 끝나면 지운다. 값은 서버에 넘길 그 데이터베이스의 URL이다."""
    with testdb.fresh_database(admin_database_url) as (_, url):
        yield url


@pytest.fixture
def srv(server, database_url, tmp_path, request):
    from harness.server import scenario_outputs
    from harness.server.api import ServerHarness

    pool_path = scenario_outputs.write_test_pool(tmp_path / "scenario_pool.json")
    harness = ServerHarness(server, database_url, pool_path)
    yield harness
    harness.close()
    report = getattr(request.node, "rep_call", None)
    if report is not None and report.passed:
        failures = [f for r in harness.replays for f in r.failures]
        if failures:
            pytest.fail("재생 클라이언트 오류: " + "; ".join(failures))


_CASES = None


def _cases():
    global _CASES
    if _CASES is None:
        _CASES = cases_by_id(load_cases_file())
    return _CASES


@pytest.fixture
def expect(request):
    """표지의 케이스 ID로 server_cases.yaml의 판정 키를 읽는다. 테스트가 통과했는데 읽지 않은 판정 키가 있으면 실패다."""
    marks = list(request.node.iter_markers(name=MARKER))
    assert len(marks) == 1 and marks[0].args, f"{request.node.nodeid}: server_case 표지가 하나여야 한다"
    case_id = marks[0].args[0]
    case = _cases().get(case_id)
    assert case is not None, f"server_cases.yaml에 {case_id}가 없다"
    tracker = CaseExpect(case)
    yield tracker
    report = getattr(request.node, "rep_call", None)
    if report is not None and report.passed:
        unused = tracker.unused()
        if unused:
            pytest.fail(f"{case_id}: 테스트가 읽지 않은 판정 키 {unused}")
