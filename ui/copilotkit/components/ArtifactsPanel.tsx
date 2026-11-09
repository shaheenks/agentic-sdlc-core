"use client";

// Artifacts panel (version-03 P5): the documents the agent saved for the signed-in user. Reads the
// MCP server's /artifacts/ API, same origin through oauth2-proxy (the proxy adds the user's Entra
// token; no token reaches this code). Owner only: the server returns the caller's documents and
// nobody else's. Links are built from the UUID only (lib/results.ts savedArtifacts). Refreshes when
// opened and when the chat saves a document (ARTIFACTS_CHANGED, sent by the save_artifact card).

import { useCallback, useEffect, useState } from "react";

import { openArtifact } from "@/components/ArtifactViewer";
import { type SavedArtifact, savedArtifacts } from "@/lib/results";

export const ARTIFACTS_CHANGED = "sdlc:artifacts-changed";
const API = "/artifacts/";

type Props = { onClose: () => void };

function size(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${Math.ceil(bytes / 1024)} KB`;
}

async function problem(response: Response): Promise<string> {
  if (response.status === 403) return "Saved documents are not available to you.";
  if (response.status === 503) return "Saved documents are not switched on for this server.";
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // not JSON
  }
  return `Could not load your documents (${response.status}).`;
}

function ArtifactRow({ a, onChange }: { a: SavedArtifact; onChange: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API}${a.id}`, { method: "DELETE", headers: { "X-SDLC-Request": "1" } });
      if (!response.ok && response.status !== 404) setError(await problem(response));
      else onChange();
    } catch {
      setError("Could not delete. Reload the page to sign in again.");
    }
    setBusy(false);
    setConfirm(false);
  }

  return (
    <li className="artifact-row">
      <button type="button" className="artifact-name" onClick={() => openArtifact(a)} title={`Open ${a.name}`}>
        {a.name}
      </button>
      <div className="citation-meta">
        <span>v{a.version}{a.versions > 1 ? ` · ${a.versions} versions` : ""}</span>
        <span>{size(a.sizeBytes)}</span>
        {a.expiresAt && <span>kept until {a.expiresAt.slice(0, 10)}</span>}
      </div>
      <div className="artifact-actions">
        {confirm ? (
          <>
            <span>Delete this document?</span>
            <button type="button" className="danger" onClick={remove} disabled={busy}>
              Delete
            </button>
            <button type="button" onClick={() => setConfirm(false)} disabled={busy}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={() => openArtifact(a)}>
              Review
            </button>
            <a href={a.href} download={a.name}>
              Download
            </a>
            <button type="button" onClick={() => setConfirm(true)}>
              Delete
            </button>
          </>
        )}
      </div>
      {error && <div className="conn-error">{error}</div>}
    </li>
  );
}

export function ArtifactsPanel({ onClose }: Props) {
  const [items, setItems] = useState<SavedArtifact[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch(API, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        setError(await problem(response));
        return;
      }
      setError(null);
      setItems(savedArtifacts(await response.json()));
    } catch {
      // a lapsed session redirects to sign-in, which fetch cannot follow cross-origin
      setError("Could not load your documents. Reload the page to sign in again.");
    }
  }, []);

  useEffect(() => {
    void load();
    const refresh = () => void load();
    window.addEventListener(ARTIFACTS_CHANGED, refresh);
    return () => window.removeEventListener(ARTIFACTS_CHANGED, refresh);
  }, [load]);

  return (
    <aside className="artifacts" aria-label="Artifacts">
      <div className="artifacts-head">
        <span className="artifacts-title">Artifacts</span>
        <span className="artifacts-tools">
          <button type="button" className="icon-button" onClick={() => void load()} aria-label="Refresh artifacts">
            ↻
          </button>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Hide artifacts">
            ×
          </button>
        </span>
      </div>
      {error && <div className="conn-error">{error}</div>}
      {items === null && !error && <div className="tool pending">Loading…</div>}
      {items?.length === 0 && (
        <div className="artifacts-empty">
          <div className="artifacts-icon" aria-hidden="true">
            🗂
          </div>
          <p>No saved documents yet.</p>
          <p className="artifacts-hint">
            Ask the assistant to save a design note, user stories or a report. Only you can see your documents; they are
            kept for a limited time.
          </p>
        </div>
      )}
      {items && items.length > 0 && (
        <ul className="artifact-list">
          {items.map((a) => (
            <ArtifactRow key={a.id} a={a} onChange={load} />
          ))}
        </ul>
      )}
    </aside>
  );
}
