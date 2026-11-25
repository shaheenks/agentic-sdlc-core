"use client";

import { useCallback, useEffect, useState } from "react";
import Markdown from "react-markdown";

import { api, formatWhen } from "@/lib/client";

// The latest version's metadata, and every version number
type Artifact = { name: string; version: number; created_at?: string; content_type?: string; size?: number; versions?: number[] };
type Read = { name: string; version: number; content: string; content_type: string };

// The user's own artifacts (FR-ART-001, FR-ART-002), read through user_agent_mcp as the signed-in user.
export default function ArtifactsPage() {
  const [items, setItems] = useState<Artifact[] | null>(null);
  const [open, setOpen] = useState<Read | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    api<{ artifacts: Artifact[] }>("/api/artifacts").then(
      (r) => setItems(r.artifacts),
      (e: Error) => setError(e.message),
    );
  }, []);
  useEffect(refresh, [refresh]);

  const view = async (name: string) => {
    try {
      setOpen(await api<Read>(`/api/artifacts/${encodeURIComponent(name)}`));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const remove = async (name: string) => {
    if (!window.confirm(`Delete ${name} with all its versions?`)) return;
    await api(`/api/artifacts/${encodeURIComponent(name)}`, { method: "DELETE" }).catch((e: Error) => setError(e.message));
    if (open?.name === name) setOpen(null);
    refresh();
  };

  return (
    <main className="page split">
      <section>
        <h1>Artifacts</h1>
        <p className="hint">What you and your chats saved. Artifacts are deleted 7 days after they are written.</p>
        {error && <p className="error">{error}</p>}
        {items === null ? (
          <p>Loading…</p>
        ) : items.length === 0 ? (
          <p className="empty">No artifacts yet. Ask the assistant to save one.</p>
        ) : (
          <ul className="list">
            {items.map((a) => {
              const count = a.versions?.length ?? 1;
              return (
                <li key={a.name} className={open?.name === a.name ? "active" : ""}>
                  <button type="button" className="link" onClick={() => view(a.name)}>
                    {a.name}
                  </button>
                  <small>
                    {count} version{count === 1 ? "" : "s"}
                    {a.created_at ? ` · ${formatWhen(a.created_at)}` : ""}
                  </small>
                  <button type="button" className="icon" aria-label={`Delete ${a.name}`} onClick={() => remove(a.name)}>
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <section className="preview">
        {open ? (
          <>
            <h2>
              {open.name} <small>v{open.version}</small>
            </h2>
            {open.content_type === "text/markdown" ? (
              <article className="markdown">
                <Markdown>{open.content}</Markdown>
              </article>
            ) : (
              <pre>{open.content}</pre>
            )}
          </>
        ) : (
          <p className="empty">Choose an artifact to read it.</p>
        )}
      </section>
    </main>
  );
}
