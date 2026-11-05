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

PAIRS = (("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"), ("으로", "로"))
PAIR_PATTERN = r"(?:은/는|이/가|을/를|과/와|으로/로)"
PROFILE_TOKEN = re.compile(r"\{\{profile:([^{}]*)\}\}(" + PAIR_PATTERN + ")?")
PARTICIPANT_TOKEN = re.compile(r"\{\{participant:([^{}]*)\}\}(" + PAIR_PATTERN + ")?")
SELF_NAME = "당신"
HONORIFIC = "님"
HUMOR_TEXT = "너네 조합 꽝이니 여행 가지 마세요!"
HUMOR_EXPLANATION = "이번 응답 조건에서는 추천안을 찾지 못했습니다."
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

EDITABLE_KINDS = ("clauses", "conditional_alternatives")


def shared_result(output, roster, *, result_id, kind, source_result_id, draft, included_count, excluded_names):
    """검증을 통과한 PactRecommendation(토큰 그대로)을 §0-C 공유 결과로 바꾼다. 치환 실패는 RenderError다.

    positions, original_condition, source_response_ids, response_id는 넣지 않는다(§0-A 6).
    """
    def text(value):
        return render_participant_tokens(value, roster)

    def names(ids):
        return [participant_name(pid, roster) for pid in ids]

    clauses = []
    for item in output.get("clauses") or []:
        clauses.append({
            "scenario_id": item["scenario_id"],
            "participant_names": names(item.get("participant_ids") or []),
            "action": text(item["action"]),
            "proposed_conditions": [text(t) for t in item.get("proposed_conditions") or []],
        })
    alternatives = []
    for item in output.get("conditional_alternatives") or []:
        alternatives.append({
            "scenario_id": item["scenario_id"],
            "participant_names": names(item.get("participant_ids") or []),
            "action": text(item["action"]),
            "proposed_conditions": [text(t) for t in item.get("proposed_conditions") or []],
            "proposed_changes": [text(c["proposed_change"]) for c in item.get("required_changes") or []],
        })
    unresolved = [
        {"scenario_id": item["scenario_id"], "description": text(item["description"])}
        for item in output.get("unresolved_conditions") or []
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
        "clauses": clauses,
        "conditional_alternatives": alternatives,
        "unresolved_conditions": unresolved,
    }
    if isinstance(output.get("message"), str):
        result["message"] = text(output["message"])
    if output["status"] == "unresolved":
        result["humor"] = {"text": HUMOR_TEXT, "explanation": HUMOR_EXPLANATION}
    return result


def editable_paths(output):
    """결정 4의 편집 가능한 위치. (공유 결과 기준 JSON Pointer, 출력 안의 문장) 쌍을 순서대로 낸다."""
    for kind in EDITABLE_KINDS:
        for i, item in enumerate(output.get(kind) or []):
            yield f"/{kind}/{i}/action", item["action"]
            for j, sentence in enumerate(item.get("proposed_conditions") or []):
                yield f"/{kind}/{i}/proposed_conditions/{j}", sentence
            if kind == "conditional_alternatives":
                for j, change in enumerate(item.get("required_changes") or []):
                    yield f"/{kind}/{i}/proposed_changes/{j}", change["proposed_change"]


def set_sentence(output, path, text):
    """편집 가능한 위치의 문장을 바꾼다. 위치가 없으면 KeyError다."""
    parts = path.strip("/").split("/")
    kind, i, field = parts[0], int(parts[1]), parts[2]
    item = output[kind][i]
    if field == "action":
        item["action"] = text
    elif field == "proposed_conditions":
        item["proposed_conditions"][int(parts[3])] = text
    elif field == "proposed_changes":
        item["required_changes"][int(parts[3])]["proposed_change"] = text
    else:
        raise KeyError(path)


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
