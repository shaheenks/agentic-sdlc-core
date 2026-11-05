"use client";

// Artifacts panel (placeholder, version-02 chat UX): where files from the artifacts library
// (agent-generated test files, documents, reports) will be listed. No data source yet: the
// library is designed in docs/plans/pending-task.md (task 3). Display only, nothing is fetched.

type Props = { onClose: () => void };

export function ArtifactsPanel({ onClose }: Props) {
  return (
    <aside className="artifacts" aria-label="Artifacts">
      <div className="artifacts-head">
        <span className="artifacts-title">Artifacts</span>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Hide artifacts">
          ×
        </button>
      </div>
      <div className="artifacts-empty">
        <div className="artifacts-icon" aria-hidden="true">
          🗂
        </div>
        <p>No artifacts yet.</p>
        <p className="artifacts-hint">
          Files your agents create, such as generated tests, design documents and reports, will appear here.
        </p>
      </div>
    </aside>
  );
}
