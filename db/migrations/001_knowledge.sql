-- Stage 5: knowledge store with row-level security.
-- Applied by `sdlc-db migrate` as sdlc_owner (search_path = sdlc).
--
-- RLS context, set per transaction by libs/sdlc_db (SET LOCAL via set_config):
--   app.allowed_sources          text[] literal, e.g. '{payments-code,eng-standards}'
--   app.max_classification_rank  integer (0 = public ... per platform.yaml classification_levels)
-- Missing context => empty array / -1 => no rows (fail closed).

CREATE OR REPLACE FUNCTION sdlc.allowed_sources() RETURNS text[]
LANGUAGE sql STABLE AS $$
  SELECT COALESCE(NULLIF(current_setting('app.allowed_sources', true), ''), '{}')::text[]
$$;

CREATE OR REPLACE FUNCTION sdlc.max_classification_rank() RETURNS integer
LANGUAGE sql STABLE AS $$
  SELECT COALESCE(NULLIF(current_setting('app.max_classification_rank', true), '')::integer, -1)
$$;

CREATE TABLE sdlc.sources (
    id                  text PRIMARY KEY,
    classification      text NOT NULL,
    classification_rank integer NOT NULL,
    owner_team          text NOT NULL,
    config_version      text NOT NULL,
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sdlc.documents (
    id                  bigserial PRIMARY KEY,
    source_id           text NOT NULL REFERENCES sdlc.sources(id) ON DELETE CASCADE,
    path                text NOT NULL,
    content_hash        text NOT NULL,
    classification_rank integer NOT NULL,
    ingested_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, path)
);

CREATE TABLE sdlc.chunks (
    id                  bigserial PRIMARY KEY,
    document_id         bigint NOT NULL REFERENCES sdlc.documents(id) ON DELETE CASCADE,
    source_id           text NOT NULL,
    classification_rank integer NOT NULL,
    ordinal             integer NOT NULL,
    start_line          integer NOT NULL,
    end_line            integer NOT NULL,
    heading             text,
    content             text NOT NULL,
    embedding           vector(768) NOT NULL,
    embedding_model     text NOT NULL
);

CREATE INDEX chunks_embedding_hnsw ON sdlc.chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_source ON sdlc.chunks (source_id);
CREATE INDEX documents_source ON sdlc.documents (source_id);

-- Row-level security: enabled AND forced (the owner is subject to it too).
ALTER TABLE sdlc.sources   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.sources   FORCE ROW LEVEL SECURITY;
ALTER TABLE sdlc.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.documents FORCE ROW LEVEL SECURITY;
ALTER TABLE sdlc.chunks    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.chunks    FORCE ROW LEVEL SECURITY;

-- MCP server (sdlc_app): read-only, scoped to the caller's sources and classification ceiling.
CREATE POLICY app_read ON sdlc.sources FOR SELECT TO sdlc_app
  USING (id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.max_classification_rank());
CREATE POLICY app_read ON sdlc.documents FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.max_classification_rank());
CREATE POLICY app_read ON sdlc.chunks FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.max_classification_rank());

-- Ingest (sdlc_ingest): not user-scoped; maintains every source.
CREATE POLICY ingest_all ON sdlc.sources   TO sdlc_ingest USING (true) WITH CHECK (true);
CREATE POLICY ingest_all ON sdlc.documents TO sdlc_ingest USING (true) WITH CHECK (true);
CREATE POLICY ingest_all ON sdlc.chunks    TO sdlc_ingest USING (true) WITH CHECK (true);

GRANT SELECT ON sdlc.sources, sdlc.documents, sdlc.chunks TO sdlc_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON sdlc.sources, sdlc.documents, sdlc.chunks TO sdlc_ingest;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sdlc TO sdlc_ingest;
GRANT EXECUTE ON FUNCTION sdlc.allowed_sources(), sdlc.max_classification_rank() TO sdlc_app, sdlc_ingest;
