import { useState } from "react";
import type { EditableItem, Segment } from "../api/types";
import { changedEdits, isParticipant, pathLabel } from "../lib/editable";
import { ErrorMessage } from "./ui";

/**
 * 방장 문구 편집. 글 조각은 입력란, 참여자 조각은 고칠 수 없는 칩이다(결정 29·34).
 * 저장할 때 바뀐 위치만 보낸다.
 */
export function EditForm({
  editable,
  onSave,
  onCancel,
}: {
  editable: EditableItem[];
  onSave: (edits: { path: string; text: string }[]) => Promise<void>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Record<string, Segment[]>>(() =>
    Object.fromEntries(editable.map((e) => [e.path, e.segments.map((s) => ({ ...s }))]))
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);

  const setText = (path: string, idx: number, text: string) =>
    setDraft((d) => ({
      ...d,
      [path]: (d[path] ?? []).map((s, i) => (i === idx && !isParticipant(s) ? { text } : s)),
    }));

  const save = async () => {
    const edits = changedEdits(editable, draft);
    setNote(null);
    setError(null);
    if (edits.length === 0) {
      setNote("바뀐 문구가 없어요.");
      return;
    }
    setBusy(true);
    try {
      await onSave(edits);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card stack-lg" aria-labelledby="edit-title">
      <h2 id="edit-title" className="t-headline-md">
        문구 고치기
      </h2>
      <p className="t-body-sm secondary">
        문장만 고칠 수 있어요. 이름 칸은 바꿀 수 없어요. 저장하면 바로 공개되고 협약서에 ‘방장 수정’이 표시돼요.
      </p>
      {editable.map((item) => {
        const label = pathLabel(item.path);
        const segs = draft[item.path] ?? [];
        return (
          <div className="edit-item" key={item.path} role="group" aria-label={label}>
            <p className="field-label">{label}</p>
            <div className="edit-row">
              {segs.map((s, i) =>
                isParticipant(s) ? (
                  <span key={i} className="chip" aria-label={`${s.display}, 고칠 수 없는 이름`}>
                    {s.display}
                  </span>
                ) : (
                  <textarea
                    key={i}
                    aria-label={`${label} 문구 ${i + 1}`}
                    value={s.text}
                    rows={Math.max(1, Math.ceil(Array.from(s.text).length / 16))}
                    onChange={(e) => setText(item.path, i, e.target.value)}
                  />
                )
              )}
            </div>
          </div>
        );
      })}
      {note && <p className="secondary">{note}</p>}
      {error !== null && <ErrorMessage error={error} />}
      <button type="button" className="btn btn-primary" onClick={save} disabled={busy}>
        {busy ? "저장하는 중이에요" : "수정본 저장"}
      </button>
      <button type="button" className="btn-text" onClick={onCancel}>
        고치지 않고 닫기
      </button>
    </section>
  );
}
