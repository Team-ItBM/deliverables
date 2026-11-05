// 서버 계약(docs/prompts/delegation_server.md §0-B, §0-C, "편집용 응답")의 형태만 옮긴다.
// 여기에 없는 필드를 화면에 쓰지 않는다.

export type RoomStatus = "open" | "closed" | "generating" | "ready" | "failed";
export type FailureReason = "output_invalid" | "call_error" | "interrupted";
export type ScenarioStatus =
  | "preparing"
  | "ready"
  | "needs_information"
  | "unsupported"
  | "invalid_input"
  | "failed";
export type PactStatus =
  | "proposed"
  | "conditional_only"
  | "needs_information"
  | "unresolved"
  | "unsupported"
  | "invalid_input";

export interface Trip {
  destination: string;
  duration_days: number;
  party_size: number;
  relationship: string;
}

export interface ProfileInput {
  profile_id: string;
  display_name: string;
  gender?: string;
  age_band?: string;
  mbti?: string;
}

export interface CreateRoomResponse {
  room_code: string;
  host_token: string;
  created_at: string;
  expires_at: string;
  scenario_status: ScenarioStatus;
}

export interface RoomProfile {
  profile_id: string;
  display_name: string;
  has_submission: boolean;
}

export interface ScenarioNotice {
  message?: string;
  clarification_questions?: string[];
}

export interface RoomView {
  room_status: RoomStatus;
  scenario_status: ScenarioStatus;
  party_size: number;
  submitted_count: number;
  profiles: RoomProfile[];
  failure_reason?: FailureReason | null;
  scenario_notice?: ScenarioNotice | null;
}

export interface ScenarioOption {
  option_id: string;
  label: string;
}

export interface SessionScenario {
  scenario_id: string;
  scene: string;
  question: string;
  options: ScenarioOption[];
}

export interface SessionResponse {
  session_id: string;
  duplicate_name_notice: boolean;
  privacy_notice: string;
  scenarios: SessionScenario[];
}

export interface Answer {
  scenario_id: string;
  option_id: string;
  memo?: string;
}

export interface SubmissionBody {
  session_id: string;
  answers: Answer[];
}

export interface SubmissionResponse {
  participant_id: string;
  submitted_count: number;
  party_size: number;
}

export interface Clause {
  scenario_id: string;
  participant_names: string[];
  action: string;
  proposed_conditions: string[];
}

export interface ConditionalAlternative extends Clause {
  proposed_changes: string[];
}

export interface UnresolvedCondition {
  scenario_id: string;
  description: string;
}

export interface SharedResult {
  result_id: string;
  kind: "ai_original" | "host_edited";
  source_result_id?: string | null;
  label: string | null;
  draft: boolean;
  pact_status: PactStatus;
  included_count: number;
  excluded_names: string[];
  clauses: Clause[] | null;
  conditional_alternatives: ConditionalAlternative[] | null;
  unresolved_conditions: UnresolvedCondition[] | null;
  message?: string | null;
  humor?: { text: string; explanation: string } | null;
}

export interface TextSegment {
  text: string;
}
export interface ParticipantSegment {
  participant_id: string;
  display: string;
  pair: string | null;
}
export type Segment = TextSegment | ParticipantSegment;

export interface EditableItem {
  path: string;
  segments: Segment[];
}

/** 결과 목록 항목. 실패 항목은 공유 결과 필드가 비어 있을 수 있다(계약에 실패 항목의 형태가 없다). */
export type ResultEntry = Partial<SharedResult> & {
  result_id: string;
  attempt: number;
  state: "normal" | "failed";
  created_at: string;
  editable?: EditableItem[];
};

export interface ResultsList {
  selected_result_id: string | null;
  results: ResultEntry[];
}

export interface PushSubscriptionBody {
  role: "host" | "participant";
  session_id?: string;
  subscription: { endpoint: string; keys: { p256dh: string; auth: string } };
}
