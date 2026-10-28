-- version-01 M0: item metadata for citations, and per-source sync state for incremental loaders.
--
-- documents.title / documents.url: shown and linked in search results (Confluence page, Jira issue,
-- repository file at a commit). Nullable: local files have neither. Covered by the existing
-- documents RLS policies (source_id + classification_rank).
--
-- sync_state: the cursor an incremental loader resumes from (e.g. "updated since", a commit, object
-- generations). Ingest-only, like extraction_cache: RLS enabled + forced, a policy for sdlc_ingest
-- only and NO grant to sdlc_app (users never see sync state). Rows go with their source (cascade).

ALTER TABLE sdlc.documents
  ADD COLUMN title text,
  ADD COLUMN url   text;

COMMENT ON COLUMN sdlc.documents.title IS 'item title for citations (NULL for local files)';
COMMENT ON COLUMN sdlc.documents.url IS 'https deep link to the item in its source system (NULL for local files)';

CREATE TABLE sdlc.sync_state (
    source_id       text PRIMARY KEY REFERENCES sdlc.sources(id) ON DELETE CASCADE,
    cursor          jsonb NOT NULL,
    last_synced_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE sdlc.sync_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.sync_state FORCE ROW LEVEL SECURITY;

CREATE POLICY ingest_all ON sdlc.sync_state TO sdlc_ingest USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON sdlc.sync_state TO sdlc_ingest;
