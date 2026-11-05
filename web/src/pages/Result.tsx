import { Download } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ApiError, isNotFound } from "../api/errors";
import type { ResultEntry, ResultsList, RoomView, SharedResult } from "../api/types";
import { EditForm } from "../components/EditForm";
import { HostPanel } from "../components/HostPanel";
import { PetalDrift } from "../components/PactBranch";
import { hasPaper, issueItemCount, ResultSheet } from "../components/PactSheet";
import { BottomBar, ErrorMessage, ICON, RoomNotFound } from "../components/ui";
import { useHeaderBack } from "../lib/back";
import { displaySegments, setAtPointer } from "../lib/editable";
import { useHostToken, usePolling, usePrefersReducedMotion } from "../lib/hooks";
import { savePaperImage } from "../lib/saveImage";
import { issueSeen, markIssueSeen, useIssueSequence } from "../lib/issue";
import { issueSoundFor, SILENT } from "../lib/issueSound";

/**
 * 화면용 종이와, 저장 이미지용으로 화면 밖에 360px 폭으로 그린 같은 종이.
 * 저장이 그 화면의 주 동작이면 아래 고정 영역에, 아니면 종이 아래에 둔다.
 */
function SheetWithSave({
  code,
  started,
  result,
  edited,
  saveIsPrimary,
  belowPaper,
}: {
  code: string;
  started: boolean;
  result: Partial<SharedResult>;
  edited?: boolean;
  saveIsPrimary: boolean;
  belowPaper?: ReactNode;
}) {
  const captureRef = useRef<HTMLDivElement>(null);
  const paperRef = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const paper = hasPaper(result.pact_status);
  // 첫 열람에 한 번만 재생한다. 줄인 움직임이면 완성 상태를 바로 보여 준다.
  const [animate] = useState(() => paper && !reduced && !issueSeen(code));
  const [sound] = useState(() => (animate ? issueSoundFor(started) : SILENT));
  const phase = useIssueSequence(animate, paperRef, issueItemCount(result), sound);
  const [state, setState] = useState<"idle" | "busy" | "error" | "done">("idle");

  useEffect(() => {
    markIssueSeen(code);
  }, [code]);

  const save = async () => {
    if (!captureRef.current) return;
    setState("busy");
    try {
      await document.fonts?.ready;
      const r = await savePaperImage(captureRef.current, "dowon-pact.png");
      setState(r === "cancelled" ? "idle" : "done");
    } catch {
      setState("error");
    }
  };

  const saveButton = (
    <button
      type="button"
      className={`btn ${saveIsPrimary ? "btn-primary" : "btn-secondary"}`}
      onClick={save}
      disabled={state === "busy"}
    >
      <Download {...ICON} />
      {state === "busy" ? "이미지를 만드는 중이에요" : "이미지로 저장"}
    </button>
  );

  return (
    <div className="stack-lg">
      <ResultSheet ref={paperRef} result={result} phase={phase} edited={edited} />
      <div className="capture-host" aria-hidden="true">
        <ResultSheet ref={captureRef} result={result} capture edited={edited} />
      </div>
      {belowPaper}
      {state === "error" && <ErrorMessage text="이미지를 저장하지 못했어요. 화면의 협약서는 그대로 있어요." />}
      {state === "done" && <p className="secondary" role="status">이미지를 저장했어요.</p>}
      {saveIsPrimary ? <BottomBar>{saveButton}</BottomBar> : saveButton}
    </div>
  );
}

/** 결과 목록 항목에 editable 문장(다음 수정이 시작할 판)을 덮어 그린다(결정 33). */
export function overlayEditable(entry: ResultEntry): { view: Partial<SharedResult>; edited: boolean } {
  let view: Partial<SharedResult> = entry;
  let edited = false;
  for (const item of entry.editable ?? []) {
    const text = displaySegments(item.segments);
    const before = pointerGet(view, item.path);
    if (typeof before === "string" && before !== text) {
      view = setAtPointer(view, item.path, text);
      edited = true;
    }
  }
  return { view, edited };
}

function pointerGet(obj: unknown, path: string): unknown {
  return path
    .split("/")
    .filter(Boolean)
    .reduce<unknown>((cur, k) => (cur && typeof cur === "object" ? (cur as Record<string, unknown>)[k] : undefined), obj);
}

function sortEntries(list: ResultEntry[]): ResultEntry[] {
  return [...list].sort((a, b) => a.attempt - b.attempt || a.created_at.localeCompare(b.created_at));
}

function HostResults({
  code,
  token,
  started,
  onPublicChanged,
}: {
  code: string;
  token: string;
  started: boolean;
  onPublicChanged: () => void;
}) {
  const [list, setList] = useState<ResultsList | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const [newResult, setNewResult] = useState<number | null>(null);
  const editRef = useRef<HTMLDivElement>(null);
  const known = useRef<Set<string> | null>(null);

  const load = async () => {
    try {
      const l = await api.getResults(code, token);
      setList(l);
      setError(null);
      return l;
    } catch (err) {
      setError(err);
      return null;
    }
  };

  const room = usePolling<RoomView>(
    () => api.getRoom(code, token),
    (r) => !r || r.room_status === "generating" || r.room_status === "closed",
    [code, token]
  );
  const roomStatus = room.data?.room_status;
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, token, roomStatus]);

  const entries = useMemo(() => sortEntries(list?.results ?? []), [list]);

  // 재생성이 끝나 새 정상 결과가 생기면 그 결과로 옮기고 알린다.
  useEffect(() => {
    if (!list) return;
    const ids = new Set(entries.map((e) => e.result_id));
    const fresh = known.current ? entries.filter((e) => e.state === "normal" && !known.current!.has(e.result_id)) : [];
    known.current = ids;
    const latest = fresh[fresh.length - 1];
    if (latest) {
      setTab(latest.result_id);
      setEditing(false);
      setNewResult(latest.attempt);
      window.scrollTo(0, 0);
    }
  }, [list, entries]);

  useEffect(() => {
    if (editing) editRef.current?.scrollIntoView?.({ block: "start" });
  }, [editing]);

  const firstNormal = entries.find((e) => e.state === "normal");
  const publicId = list?.selected_result_id ?? firstNormal?.result_id ?? null;
  const current = entries.find((e) => e.result_id === tab) ?? entries.find((e) => e.result_id === publicId) ?? entries[0];

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      await load();
      onPublicChanged();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  };

  const overlay = current && current.state === "normal" ? overlayEditable(current) : null;
  const isSelected = current?.result_id === list?.selected_result_id;

  const menu = room.data && (
    <HostPanel
      code={code}
      token={token}
      room={room.data}
      mode="result"
      onChanged={() => {
        setNewResult(null);
        room.reload();
        window.scrollTo(0, 0);
      }}
    />
  );

  return (
    <div className="stack-lg">
      {error !== null && <ErrorMessage error={error} onRetry={() => void load()} />}
      {roomStatus === "generating" && (
        <section className="card" aria-live="polite">
          <p>새 결과를 만들고 있어요. 지금 공개된 결과는 그대로예요.</p>
          <div className="progress-track" aria-hidden="true">
            <div className="progress-flow" />
          </div>
        </section>
      )}
      {newResult !== null && (
        <p className="card" role="status">
          {newResult}번째 결과가 나왔어요. 고르기 전까지 동행에게는 보이지 않아요.
        </p>
      )}
      {entries.length > 1 && (
        <div className="tabs" role="tablist" aria-label="만든 결과">
          {entries.map((e) => (
            <button
              key={e.result_id}
              type="button"
              role="tab"
              className="tab-result"
              aria-selected={current?.result_id === e.result_id}
              onClick={() => {
                setTab(e.result_id);
                setEditing(false);
              }}
            >
              {e.attempt}번째 결과{e.state === "failed" ? " (실패)" : ""}
            </button>
          ))}
        </div>
      )}
      {current && current.state === "failed" && <p className="card">이 결과는 만들지 못했어요.</p>}
      {current && overlay && (
        <>
          <p className="secondary" role="status">
            {isSelected
              ? "이 결과가 동행에게 공개되고 있어요."
              : current.result_id === publicId
                ? "고르기 전이라 이 결과가 초안으로 공개되고 있어요. 고르면 초안 표시가 사라져요."
                : "아직 방장에게만 보이는 결과예요. 고르면 동행에게 공개돼요."}
          </p>
          <SheetWithSave
            code={code}
            started={started}
            result={overlay.view}
            edited={overlay.edited}
            saveIsPrimary={isSelected && !editing}
            belowPaper={
              <>
                {actionError !== null && <ErrorMessage error={actionError} />}
                {editing && current.editable ? (
                  <div ref={editRef}>
                    <EditForm
                      key={current.result_id}
                      editable={current.editable}
                      onCancel={() => setEditing(false)}
                      onSave={async (edits) => {
                        await api.edit(code, current.result_id, edits, token);
                        setEditing(false);
                        await load();
                        onPublicChanged();
                      }}
                    />
                  </div>
                ) : (
                  current.editable &&
                  current.editable.length > 0 && (
                    <button type="button" className="btn-text" onClick={() => setEditing(true)}>
                      문구 고치기
                    </button>
                  )
                )}
              </>
            }
          />
          {!isSelected && !editing && (
            <BottomBar>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => act(() => api.select(code, current.result_id, token))}
              >
                이 결과로 고르기
              </button>
            </BottomBar>
          )}
        </>
      )}
      {menu}
    </div>
  );
}

export function Result() {
  const { code = "" } = useParams();
  const token = useHostToken(code);
  const navigate = useNavigate();
  const location = useLocation();
  const started = (location.state as { started?: boolean } | null)?.started === true;
  const reduced = usePrefersReducedMotion();
  useHeaderBack(() => navigate(token ? `/r/${encodeURIComponent(code)}` : "/"));
  const [result, setResult] = useState<SharedResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getResult(code)
      .then((r) => {
        if (!cancelled) {
          setResult(r);
          setError(null);
        }
      })
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [code, tick]);

  const notReady = error instanceof ApiError && error.code === "invalid_state";

  // 결과 화면은 표면색을 바탕으로 써서 종이가 한 단계 떠 보이게 한다.
  useEffect(() => {
    document.body.classList.add("result-bg");
    return () => document.body.classList.remove("result-bg");
  }, []);

  if (isNotFound(error)) return <RoomNotFound />;

  return (
    <main className="page">
      <h1 className="t-headline-lg">추천 협약서</h1>
      {notReady && (
        <section className="card">
          <p>아직 공개된 협약서가 없어요.</p>
          <Link className="btn-text" to={`/r/${encodeURIComponent(code)}/wait`}>
            진행 상황 보기
          </Link>
        </section>
      )}
      {error !== null && !notReady && <ErrorMessage error={error} onRetry={() => setTick((t) => t + 1)} />}
      {token ? (
        <HostResults code={code} token={token} started={started} onPublicChanged={() => setTick((t) => t + 1)} />
      ) : (
        result && <SheetWithSave code={code} started={started} result={result} saveIsPrimary />
      )}
      {!reduced && hasPaper(result?.pact_status) && <PetalDrift />}
    </main>
  );
}
