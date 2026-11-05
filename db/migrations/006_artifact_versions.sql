-- version-03 P5 (F6): versions of one saved document.
--
-- A document keeps one stable id (`document_id`); every save that replaces it adds a row with the
-- next `version`. Rows stay immutable (still no UPDATE grant): nothing is overwritten, older
-- versions remain readable until they expire. Each row keeps its own `id` (the content's object
-- key) and `expires_at`. Ownership and RLS are unchanged (owner per row, `app_owner`).
--
-- Backfill: existing rows become version 1 of their own document. The table forces RLS and has no
-- policy for sdlc_owner, so the backfill lifts FORCE for this transaction only.

ALTER TABLE sdlc.artifacts
    ADD COLUMN document_id uuid,
    ADD COLUMN version     integer NOT NULL DEFAULT 1 CHECK (version >= 1);

ALTER TABLE sdlc.artifacts NO FORCE ROW LEVEL SECURITY;
UPDATE sdlc.artifacts SET document_id = id WHERE document_id IS NULL;
ALTER TABLE sdlc.artifacts FORCE ROW LEVEL SECURITY;

ALTER TABLE sdlc.artifacts ALTER COLUMN document_id SET NOT NULL;
CREATE UNIQUE INDEX artifacts_document_version ON sdlc.artifacts (document_id, version);

COMMENT ON COLUMN sdlc.artifacts.document_id IS 'stable id of the document; equals id of version 1';
COMMENT ON COLUMN sdlc.artifacts.version IS '1, 2, ... per document; the highest live version is the current one';
