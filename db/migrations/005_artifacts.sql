-- version-03 P5 (F1): metadata of agent-generated artifacts (design/review docs, stories, reports).
--
-- Content lives in the artifact store (local folder or GCS bucket, key artifacts/<owner>/<id>);
-- this table holds what is needed to list, limit and expire it. Owner only (decision A3): the
-- MCP server sets app.user_oid from the verified token per transaction (sdlc_db.owner_scoped) and
-- every row is filtered on it. Missing context = no rows, no writes.
--
-- Exception to "data tables carry source_id + classification_rank": artifacts are user-owned
-- files, not knowledge from a source. Classification arrives with team sharing (F3).
--
-- sdlc_app (otherwise read-only) gets SELECT, INSERT, DELETE on this table only (decision A2).
-- No UPDATE: an artifact is immutable; a revision is a new artifact. No grant to sdlc_ingest.

CREATE TABLE sdlc.artifacts (
    id                uuid PRIMARY KEY,
    owner_oid         text NOT NULL CHECK (owner_oid ~ '^[0-9a-f-]{36}$'),
    name              text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
    media_type        text NOT NULL,
    size_bytes        integer NOT NULL CHECK (size_bytes >= 0),
    sha256            text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    agent_session_id  text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    expires_at        timestamptz NOT NULL,
    CHECK (expires_at > created_at)
);

CREATE INDEX artifacts_owner_created ON sdlc.artifacts (owner_oid, created_at DESC);

COMMENT ON TABLE sdlc.artifacts IS 'agent-generated files (metadata only; content in the artifact store), owner only';
COMMENT ON COLUMN sdlc.artifacts.agent_session_id IS 'conversation id, client-supplied: correlation only, never authorization';

CREATE FUNCTION sdlc.current_user_oid() RETURNS text
    LANGUAGE sql STABLE
    AS $$ SELECT nullif(current_setting('app.user_oid', true), '') $$;

ALTER TABLE sdlc.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.artifacts FORCE ROW LEVEL SECURITY;

CREATE POLICY app_owner ON sdlc.artifacts TO sdlc_app
    USING (owner_oid = sdlc.current_user_oid())
    WITH CHECK (owner_oid = sdlc.current_user_oid());

GRANT SELECT, INSERT, DELETE ON sdlc.artifacts TO sdlc_app;
GRANT EXECUTE ON FUNCTION sdlc.current_user_oid() TO sdlc_app;
