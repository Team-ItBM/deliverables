import { Download } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { ResultEntry, ResultsList, RoomView, SharedResult, Trip } from "../api/types";
import { EditForm } from "../components/EditForm";
import { HostPanel } from "../components/HostPanel";
import { ResultSheet } from "../components/PactSheet";
import { ErrorMessage, ICON } from "../components/ui";
import { displaySegments, setAtPointer } from "../lib/editable";
import { useHostToken, usePolling, usePrefersReducedMotion } from "../lib/hooks";
import { savePaperImage } from "../lib/saveImage";
import { keys, readJSON, writeJSON } from "../lib/storage";
import { tripMetaText } from "./CreateRoom";

/** 화면용 종이와, 저장 이미지용으로 화면 밖에 360px 폭으로 그린 같은 종이. */
function SheetWithSave({
  result,
  tripMeta,
  edited,
}: {
  result: Partial<SharedResult>;
  tripMeta: string | null;
  edited?: boolean;
}) {
  const captureRef = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const seenKey = keys.seen(result.result_id ?? "none");
  const [animate] = useState(() => !reduced && !readJSON<boolean>("session", seenKey));
  const [state, setState] = useState<"idle" | "busy" | "error" | "done">("idle");

  useEffect(() => {
    writeJSON("session", seenKey, true);
  }, [seenKey]);

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

  return (
    <div className="stack-lg">
      <ResultSheet result={result} tripMeta={tripMeta} animate={animate} edited={edited} />
      <div className="capture-host" aria-hidden="true">
        <ResultSheet ref={captureRef} result={result} tripMeta={tripMeta} capture edited={edited} />
      </div>
      {state === "error" && (
        <ErrorMessage text="이미지를 저장하지 못했어요. 화면의 협약서는 그대로 있어요." onRetry={save} retryLabel="이미지 다시 저장" />
      )}
      {state === "done" && <p className="secondary" role="status">이미지를 저장했어요.</p>}
      <button type="button" className="btn btn-secondary" onClick={save} disabled={state === "busy"}>
        <Download {...ICON} />
        {state === "busy" ? "이미지를 만드는 중이에요" : "이미지로 저장"}
      </button>
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

function HostResults({ code, token, tripMeta, onPublicChanged }: { code: string; token: string; tripMeta: string | null; onPublicChanged: () => void }) {
  const [list, setList] = useState<ResultsList | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

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

  return (
    <div className="stack-lg">
      {room.data && <HostPanel code={code} token={token} room={room.data} onChanged={room.reload} showResultLink={false} />}
      {error !== null && <ErrorMessage error={error} onRetry={() => void load()} />}
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
            {current.result_id === list?.selected_result_id
              ? "이 결과가 동행에게 공개되고 있어요."
              : current.result_id === publicId
                ? "방장이 고르기 전이라 이 결과가 초안으로 공개되고 있어요."
                : "아직 방장에게만 보이는 결과예요."}
          </p>
          {actionError !== null && <ErrorMessage error={actionError} />}
          {current.result_id !== list?.selected_result_id && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => act(() => api.select(code, current.result_id, token))}
            >
              이 결과로 공개하기
            </button>
          )}
          {editing && current.editable ? (
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
          ) : (
            current.editable &&
            current.editable.length > 0 && (
              <button type="button" className="btn-text" onClick={() => setEditing(true)}>
                문구 고치기
              </button>
            )
          )}
          <SheetWithSave result={overlay.view} tripMeta={tripMeta} edited={overlay.edited} />
        </>
      )}
    </div>
  );
}

export function Result() {
  const { code = "" } = useParams();
  const token = useHostToken(code);
  const trip = readJSON<Trip>("local", keys.trip(code));
  const tripMeta = trip ? tripMetaText(trip) : null;
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
        <HostResults code={code} token={token} tripMeta={tripMeta} onPublicChanged={() => setTick((t) => t + 1)} />
      ) : (
        result && <SheetWithSave result={result} tripMeta={tripMeta} />
      )}
    </main>
  );
}
