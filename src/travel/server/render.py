"""토큰 치환과 조사 처리(SPEC 5절 "필드 연결과 검증 경계", AC13, AC15).

- `render_profile_tokens(text, profiles, viewer_profile_id)`: 문항의 `{{profile:ID}}`를 본인은 '당신', 다른 사람은 등록한
  이름·별명으로 바꾼다.
- `render_participant_tokens(text, roster)`: 추천 문장의 `{{participant:ID}}`를 채택 제출의 이름·별명으로 바꾼다.
  같은 이름의 제출에는 제출 순서로 `이름(응답 N)`을 붙이고, 조사는 이름을 기준으로 고른다.
- 토큰 뒤의 조사 쌍(은/는, 이/가, 을/를, 과/와, 으로/로)은 이름의 받침으로 고른다. ㄹ 받침은 '로'다.
  받침을 알 수 없는 영문·숫자 별명은 뒤에 '님'을 붙인다.
- 알 수 없는 ID, 깨진 토큰, 남은 토큰은 RenderError(code="render_failed")다. 부분 치환 문장을 돌려주지 않는다.
- 치환 결과는 텍스트이며 이름에 든 토큰을 다시 해석하지 않는다.
화면과 저장 이미지는 이 함수로 만든 같은 공유 결과를 쓴다.
"""

import re

from travel import pool

PAIRS = (("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"), ("으로", "로"))
PAIR_PATTERN = r"(?:은/는|이/가|을/를|과/와|으로/로)"
PROFILE_TOKEN = re.compile(r"\{\{profile:([^{}]*)\}\}(" + PAIR_PATTERN + ")?")
PARTICIPANT_TOKEN = re.compile(r"\{\{participant:([^{}]*)\}\}(" + PAIR_PATTERN + ")?")
SELF_NAME = "당신"
HONORIFIC = "님"
HOST_EDIT_LABEL = "방장 수정"


class RenderError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.code = "render_failed"


def _final_consonant(name):
    """이름 끝 글자의 받침 종류. None은 받침 없음, "ㄹ"은 ㄹ 받침, "other"는 그 밖의 받침이다.
    한글 음절이 아니면 판별할 수 없어 None 대신 ValueError를 낸다."""
    last = name[-1]
    code = ord(last)
    if not 0xAC00 <= code <= 0xD7A3:
        raise ValueError("한글 음절이 아니다")
    final = (code - 0xAC00) % 28
    if final == 0:
        return None
    if final == 8:
        return "ㄹ"
    return "other"


def display_with_particle(name, pair):
    """이름에 조사 쌍 하나를 붙인다. pair가 None이면 이름만 돌려준다(영문·숫자는 '님'을 붙인다)."""
    try:
        final = _final_consonant(name)
        shown = name
    except ValueError:
        shown = name + HONORIFIC
        final = "other"
    if pair is None:
        return shown
    with_final, without_final = pair.split("/")
    if final is None:
        return shown + without_final
    if final == "ㄹ" and (with_final, without_final) == ("으로", "로"):
        return shown + without_final
    return shown + with_final


def _render(text, token, resolve):
    """token 정규식에 맞는 자리를 resolve(id, pair)로 바꾼다. 토큰 밖에 중괄호 쌍이 남으면 실패다."""
    if not isinstance(text, str):
        raise RenderError("문장이 문자열이 아니다")
    parts = []
    pos = 0
    for match in token.finditer(text):
        between = text[pos:match.start()]
        if "{{" in between or "}}" in between:
            raise RenderError("치환되지 않은 토큰이 남았다")
        parts.append(between)
        parts.append(resolve(match.group(1), match.group(2)))
        pos = match.end()
    tail = text[pos:]
    if "{{" in tail or "}}" in tail:
        raise RenderError("치환되지 않은 토큰이 남았다")
    parts.append(tail)
    return "".join(parts)


def render_profile_tokens(text, profiles, viewer_profile_id):
    """문항 문장의 프로필 토큰을 뷰어 기준으로 치환한다. profiles는 [{profile_id, display_name}]이다."""
    names = {}
    for profile in profiles:
        pid = profile.get("profile_id")
        if isinstance(pid, str) and pid not in names:
            names[pid] = profile.get("display_name")

    def resolve(profile_id, pair):
        if profile_id not in names:
            raise RenderError("등록되지 않은 프로필 토큰")
        name = SELF_NAME if profile_id == viewer_profile_id else names[profile_id]
        if not isinstance(name, str) or not name:
            raise RenderError("표시할 이름이 없다")
        return display_with_particle(name, pair)

    return _render(text, PROFILE_TOKEN, resolve)


def participant_display_names(roster):
    """제출 순서의 명단에서 participant_id → (조사 선택 기준 이름, 표시 이름)을 만든다.
    같은 이름이 둘 이상이면 제출 순서로 `이름(응답 N)`을 붙인다."""
    counts = {}
    for entry in roster:
        counts[entry["display_name"]] = counts.get(entry["display_name"], 0) + 1
    seen = {}
    mapping = {}
    for entry in roster:
        name = entry["display_name"]
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            shown = f"{name}(응답 {seen[name]})"
        else:
            shown = name
        mapping[entry["participant_id"]] = (name, shown)
    return mapping


def _display_numbered(base, shown, pair):
    """번호가 붙은 표시 이름에 조사를 붙인다. 조사는 base 이름의 받침으로 고른다."""
    with_pair = display_with_particle(base, pair)
    if base in with_pair and shown != base:
        # base + (님) + 조사 → base(응답 N) + (님) + 조사
        suffix = with_pair[len(base):]
        return shown + suffix
    return with_pair


def render_participant_tokens(text, roster):
    """추천 문장의 참여자 토큰을 치환한다. roster는 제출 순서의 [{participant_id, display_name}]이다."""
    mapping = participant_display_names(roster)

    def resolve(participant_id, pair):
        if participant_id not in mapping:
            raise RenderError("명단에 없는 참여자 토큰")
        base, shown = mapping[participant_id]
        return _display_numbered(base, shown, pair)

    return _render(text, PARTICIPANT_TOKEN, resolve)


def participant_name(participant_id, roster):
    mapping = participant_display_names(roster)
    if participant_id not in mapping:
        raise RenderError("명단에 없는 참여자")
    base, shown = mapping[participant_id]
    return _display_numbered(base, shown, None)


# ---- 공유 결과(§0-C)

EDITABLE_KINDS = ("clauses", "discussion_items")
PUBLIC_TRIP_KEYS = ("destination", "duration_days", "party_size")
GROUP_NAME = "일행"
DECISIONS = {
    "agreed": "의견이 같아 정함",
    "middle": "중간 안으로 정함",
    "fallback": "기본 절충안으로 정함",
    "open": "그때 정하기로 함",
}
SHOWDOWN_DECISIONS = {
    "compromise": "승부처에서 절충안으로 정함",
    "duel": "승부처에서 가위바위보로 정함",
    "lottery": "승부처에서 제비뽑기로 정함",
    "talk": "승부처에서 직접 논의하기로 함",
}
CLAUSE_PLAIN = "응답을 정리해 정함"
DISCUSSION_PLAIN = "의견이 갈려 직접 논의"


def public_trip(trip):
    return {key: trip[key] for key in PUBLIC_TRIP_KEYS}


def _generic_profile_text(text):
    if not isinstance(text, str):
        return text
    return PROFILE_TOKEN.sub(lambda m: display_with_particle(GROUP_NAME, m.group(2)), text)


def _scenario_title(scenario_id, scenario):
    try:
        title = pool.lookup_template(scenario_id).get("title")
    except (KeyError, TypeError):
        title = None
    if isinstance(title, str) and title:
        return title
    return _generic_profile_text((scenario or {}).get("question") or scenario_id)


def _decision(record, default):
    if not record:
        return default
    if record.get("outcome") == "showdown":
        return SHOWDOWN_DECISIONS.get(record.get("how"), default)
    return DECISIONS.get(record.get("outcome"), default)


def process_items(output, model_input, judgments=None):
    model_input = model_input if isinstance(model_input, dict) else {}
    records = {r["scenario_id"]: r for r in judgments or [] if isinstance(r, dict) and "scenario_id" in r}
    scenarios = {s.get("scenario_id", s.get("template_id")): s for s in model_input.get("scenarios") or []}

    def entry(label, scenario_id, default):
        return {"label": label, "scenario_id": scenario_id,
                "title": _scenario_title(scenario_id, scenarios.get(scenario_id)),
                "decision": _decision(records.get(scenario_id), default)}

    items = [entry(f"제{i + 1}조", c["scenario_id"], CLAUSE_PLAIN) for i, c in enumerate(output.get("clauses") or [])]
    items.extend(entry("협의 사항", d["scenario_id"], DISCUSSION_PLAIN) for d in output.get("discussion_items") or [])
    return items


def shared_result(output, roster, *, result_id, kind, source_result_id, draft, included_count, excluded_names, trip,
                  model_input=None, judgments=None):
    def text(value):
        return render_participant_tokens(value, roster)

    clauses = [
        {"article": i + 1, "scenario_id": item["scenario_id"], "text": text(item["text"])}
        for i, item in enumerate(output.get("clauses") or [])
    ]
    discussion = [
        {"scenario_id": item["scenario_id"], "text": text(item["text"])}
        for item in output.get("discussion_items") or []
    ]
    result = {
        "result_id": str(result_id),
        "kind": kind,
        "source_result_id": str(source_result_id) if source_result_id else None,
        "label": HOST_EDIT_LABEL if kind == "host_edited" else None,
        "draft": bool(draft),
        "pact_status": output["status"],
        "included_count": included_count,
        "excluded_names": list(excluded_names),
        "trip": public_trip(trip),
        "clauses": clauses,
        "discussion_items": discussion,
        "process": process_items(output, model_input, judgments) if output["status"] == "ready" else [],
    }
    if isinstance(output.get("message"), str):
        result["message"] = text(output["message"])
    return result


def editable_paths(output):
    for kind in EDITABLE_KINDS:
        for i, item in enumerate(output.get(kind) or []):
            yield f"/{kind}/{i}/text", item["text"]


def set_sentence(output, path, text):
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] not in EDITABLE_KINDS or parts[2] != "text":
        raise KeyError(path)
    output[parts[0]][int(parts[1])]["text"] = text


def editable_segments(output, roster):
    """결과 목록의 `editable`(결정 29·34): 위치마다 글 조각과 참여자 조각(display는 조사까지 붙인 이름, pair는 원래 쌍)."""
    mapping = participant_display_names(roster)
    items = []
    for path, sentence in editable_paths(output):
        segments = []
        pos = 0
        for match in PARTICIPANT_TOKEN.finditer(sentence):
            if match.start() > pos:
                segments.append({"text": sentence[pos:match.start()]})
            participant_id, pair = match.group(1), match.group(2)
            if participant_id not in mapping:
                raise RenderError("명단에 없는 참여자 토큰")
            base, shown = mapping[participant_id]
            segments.append({"participant_id": participant_id, "display": _display_numbered(base, shown, pair),
                             "pair": pair})
            pos = match.end()
        if pos < len(sentence) or not segments:
            segments.append({"text": sentence[pos:]})
        items.append({"path": path, "segments": segments})
    return items


def participant_tokens(sentence):
    """문장 안 참여자 토큰의 ID 목록(순서 포함)."""
    return [m.group(1) for m in PARTICIPANT_TOKEN.finditer(sentence)]
