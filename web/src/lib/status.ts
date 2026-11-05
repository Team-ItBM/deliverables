import type { FailureReason, RoomStatus, ScenarioStatus } from "../api/types";

export const ROOM_STATUS_TEXT: Record<RoomStatus, string> = {
  open: "응답을 받고 있어요.",
  closed: "응답을 마감했어요. 협약서를 만들 준비를 하고 있어요.",
  generating: "추천 협약서를 만들고 있어요. 잠시만 기다려 주세요.",
  ready: "추천 협약서가 준비됐어요.",
  failed: "협약서를 만들지 못했어요.",
};

export const FAILURE_TEXT: Record<FailureReason, string> = {
  output_invalid: "만든 결과의 형식이 맞지 않아 쓰지 않았어요.",
  call_error: "추천을 만드는 서비스에 연결하지 못했어요.",
  interrupted: "만드는 도중에 멈췄어요.",
};

/** 방장이 아닌 참여자에게 보이는 문항 상태 안내. 방장은 scenario_notice를 따로 본다. */
export const SCENARIO_STATUS_TEXT: Record<Exclude<ScenarioStatus, "ready">, string> = {
  preparing: "문항을 준비하고 있어요. 잠시 뒤 자동으로 바뀌어요.",
  needs_information: "문항을 만들 정보가 부족해요. 방장이 여행 정보를 다시 확인해야 해요.",
  unsupported: "이 여행 정보로는 문항을 만들 수 없어요. 방장에게 알려 주세요.",
  invalid_input: "입력된 여행 정보에 문제가 있어 문항을 만들지 못했어요. 방장에게 알려 주세요.",
  failed: "문항을 준비하지 못했어요. 방장에게 알려 주세요.",
};
