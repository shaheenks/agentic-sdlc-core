"use client";

// Document viewer + inline review (version-03 P5, F5). An overlay modal over the chat:
// - Lines: the document with line numbers; click a line (shift-click for a range) to comment on it.
// - Preview: rendered Markdown. Raw HTML is not rendered (react-markdown escapes it), images are
//   dropped (no requests to other hosts), links open in a new tab without referrer.
// "Attach to chat" sends one user message with a reference (name + id) and the comments
// (lib/review.ts); the agent reads the text with read_artifact as the user. The text is fetched
// from the owner-only /artifacts/<id> API; nothing is stored here except an unsent draft of the
// comments in sessionStorage (this tab only), removed once attached.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import {
  attachmentMessage,
  cleanComments,
  DEFAULT_REQUEST,
  type LineComment,
  lineLabel,
  MAX_COMMENT_CHARS,
  MAX_COMMENTS,
  selectLines,
} from "@/lib/review";
import type { SavedArtifact } from "@/lib/results";

export const OPEN_ARTIFACT = "sdlc:open-artifact";

/** Ask the page to open the viewer for a saved document (from the panel or a chat card). */
export function openArtifact(a: Pick<SavedArtifact, "id" | "name">): void {
  window.dispatchEvent(new CustomEvent(OPEN_ARTIFACT, { detail: { id: a.id, name: a.name } }));
}

type Props = {
  artifact: Pick<SavedArtifact, "id" | "name">;
  onClose: () => void;
  onAttach: (message: string) => Promise<string | null>; // null = sent, else the problem
};

type Draft = { comments: LineComment[]; request: string };
const draftKey = (id: string) => `sdlc.review.${id}`;

function loadDraft(id: string): Draft {
  try {
    const raw = window.sessionStorage.getItem(draftKey(id));
    if (raw) {
      const d = JSON.parse(raw);
      if (Array.isArray(d.comments) && typeof d.request === "string") return d;
    }
  } catch {
    // storage blocked or bad JSON: start empty
  }
  return { comments: [], request: DEFAULT_REQUEST };
}

function saveDraft(id: string, draft: Draft | null): void {
  try {
    if (draft) window.sessionStorage.setItem(draftKey(id), JSON.stringify(draft));
    else window.sessionStorage.removeItem(draftKey(id));
  } catch {
    // storage blocked: the draft lasts while the modal is open
  }
}

type VersionInfo = { version: number; created: string };

export function ArtifactViewer({ artifact, onClose, onAttach }: Props) {
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [version, setVersion] = useState<number | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tab, setTab] = useState<"lines" | "preview">("lines");
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null);
  const [note, setNote] = useState("");
  const [draft, setDraft] = useState<Draft>({ comments: [], request: DEFAULT_REQUEST });
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  // comments refer to the line numbers of one version: drafts are kept per version
  const draftId = `${artifact.id}.v${version ?? 0}`;

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const response = await fetch(`/artifacts/${artifact.id}/versions`);
        if (!live) return;
        if (response.status === 404) {
          setLoadError("This document no longer exists (deleted or expired).");
          return;
        }
        if (!response.ok) {
          setLoadError(`Could not open the document (${response.status}).`);
          return;
        }
        const body = await response.json();
        const list: VersionInfo[] = (Array.isArray(body.versions) ? body.versions : [])
          .filter((v: { version?: unknown }) => typeof v.version === "number")
          .map((v: { version: number; created_at?: unknown }) => ({
            version: v.version,
            created: typeof v.created_at === "string" ? v.created_at.slice(0, 16).replace("T", " ") : "",
          }));
        setVersions(list);
        setVersion(list[0]?.version ?? null);
      } catch {
        if (live) setLoadError("Could not open the document. Reload the page to sign in again.");
      }
    })();
    dialog.current?.focus();
    return () => {
      live = false;
    };
  }, [artifact.id]);

  useEffect(() => {
    if (version === null) return;
    let live = true;
    setText(null);
    setSelection(null);
    setDraft(loadDraft(`${artifact.id}.v${version}`));
    (async () => {
      try {
        const response = await fetch(`/artifacts/${artifact.id}?version=${version}`);
        if (!live) return;
        if (response.status === 404) setLoadError("This version no longer exists (deleted or expired).");
        else if (!response.ok) setLoadError(`Could not open the document (${response.status}).`);
        else {
          setLoadError(null);
          setText(await response.text());
        }
      } catch {
        if (live) setLoadError("Could not open the document. Reload the page to sign in again.");
      }
    })();
    return () => {
      live = false;
    };
  }, [artifact.id, version]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const update = useCallback(
    (next: Draft) => {
      setDraft(next);
      saveDraft(draftId, next);
    },
    [draftId],
  );

  const lines = useMemo(() => (text ?? "").replace(/\r\n/g, "\n").split("\n"), [text]);
  const commented = useMemo(() => {
    const marks = new Set<number>();
    for (const c of draft.comments) for (let n = c.start; n <= c.end; n++) marks.add(n);
    return marks;
  }, [draft.comments]);

  function addComment() {
    if (!selection || !note.trim() || draft.comments.length >= MAX_COMMENTS) return;
    update({ ...draft, comments: cleanComments([...draft.comments, { ...selection, text: note }]) });
    setNote("");
    setSelection(null);
  }

  async function attach() {
    setSending(true);
    setSendError(null);
    const target = { ...artifact, version: version ?? undefined };
    const problem = await onAttach(attachmentMessage(target, draft.comments, draft.request));
    setSending(false);
    if (problem) {
      setSendError(problem);
      return;
    }
    saveDraft(draftId, null);
    onClose();
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={`Review ${artifact.name}`}
        tabIndex={-1}
        ref={dialog}
      >
        <header className="modal-head">
          <span className="modal-title">{artifact.name}</span>
          {versions.length > 1 && version !== null && (
            <select
              className="modal-version"
              aria-label="Version"
              value={version}
              onChange={(e) => setVersion(Number(e.target.value))}
            >
              {versions.map((v, i) => (
                <option key={v.version} value={v.version}>
                  v{v.version}
                  {i === 0 ? " (latest)" : ""} {v.created}
                </option>
              ))}
            </select>
          )}
          {versions.length === 1 && <span className="chip">v{versions[0].version}</span>}
          <div className="modal-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === "lines"} onClick={() => setTab("lines")}>
              Lines
            </button>
            <button type="button" role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>
              Preview
            </button>
          </div>
          <a
            className="modal-link"
            href={`/artifacts/${artifact.id}${version ? `?version=${version}` : ""}`}
            download={artifact.name}
          >
            Download
          </a>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <div className="modal-body">
          <div className="modal-doc">
            {loadError && <div className="conn-error">{loadError}</div>}
            {text === null && !loadError && <div className="tool pending">Loading…</div>}
            {text !== null && tab === "lines" && (
              <ol className="doc-lines">
                {lines.map((line, i) => {
                  const n = i + 1;
                  const selected = selection !== null && n >= selection.start && n <= selection.end;
                  return (
                    <li key={n} className={`${selected ? "selected" : ""} ${commented.has(n) ? "commented" : ""}`}>
                      <button
                        type="button"
                        className="doc-line"
                        onClick={(e) => setSelection(selectLines(selection, n, e.shiftKey))}
                        title="Click to comment, shift-click to select a range"
                      >
                        <span className="doc-num">{n}</span>
                        <span className="doc-text">{line || " "}</span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            )}
            {text !== null && tab === "preview" && (
              <div className="doc-preview">
                <ReactMarkdown
                  disallowedElements={["img"]}
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {text}
                </ReactMarkdown>
              </div>
            )}
          </div>

          <aside className="modal-side">
            <div className="side-title">Comments</div>
            {selection ? (
              <div className="comment-box">
                <label htmlFor="comment-text">{lineLabel(selection)}</label>
                <textarea
                  id="comment-text"
                  value={note}
                  maxLength={MAX_COMMENT_CHARS}
                  onChange={(e) => setNote(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && addComment()}
                  placeholder="What should change here?"
                  rows={3}
                  autoFocus
                />
                <div className="comment-actions">
                  <button type="button" onClick={addComment} disabled={!note.trim()}>
                    Add comment
                  </button>
                  <button type="button" onClick={() => setSelection(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="side-hint">Select a line in the Lines tab to comment on it (shift-click for a range).</p>
            )}
            <ul className="comment-list">
              {draft.comments.map((c, i) => (
                <li key={`${c.start}-${c.end}-${i}`}>
                  <button type="button" className="comment-where" onClick={() => setSelection(c)}>
                    {lineLabel(c)}
                  </button>
                  <span className="comment-text">{c.text}</span>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove comment on ${lineLabel(c)}`}
                    onClick={() => update({ ...draft, comments: draft.comments.filter((_, j) => j !== i) })}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
            <label className="side-title" htmlFor="review-request">
              Message to the assistant
            </label>
            <textarea
              id="review-request"
              value={draft.request}
              onChange={(e) => update({ ...draft, request: e.target.value })}
              rows={3}
            />
            {sendError && <div className="conn-error">{sendError}</div>}
            <button type="button" className="primary" onClick={attach} disabled={sending || !!loadError}>
              {sending ? "Attaching…" : `Attach to chat${draft.comments.length ? ` (${draft.comments.length})` : ""}`}
            </button>
          </aside>
        </div>
      </div>
    </div>
  );
}
