-- Stage 6: knowledge graph with the same row-level security as chunks.
--
-- Entities and edges belong to exactly one source (per-source graph). The same real-world thing
-- named in two sources is two rows with the same `key` (normalized name); graph_query joins them
-- by key at query time, so a caller only ever connects sources RLS lets them read.
-- Mentions and edges point at the chunk they were extracted from and disappear with it.

CREATE TABLE sdlc.entities (
    id                  bigserial PRIMARY KEY,
    source_id           text NOT NULL REFERENCES sdlc.sources(id) ON DELETE CASCADE,
    classification_rank integer NOT NULL,
    key                 text NOT NULL,      -- normalized name, e.g. 'refund-worker'
    name                text NOT NULL,      -- as written in the source
    type                text NOT NULL,      -- one of the Source's entity_types
    description         text NOT NULL DEFAULT '',
    UNIQUE (source_id, key)
);

CREATE TABLE sdlc.mentions (
    entity_id           bigint NOT NULL REFERENCES sdlc.entities(id) ON DELETE CASCADE,
    chunk_id            bigint NOT NULL REFERENCES sdlc.chunks(id) ON DELETE CASCADE,
    source_id           text NOT NULL,
    classification_rank integer NOT NULL,
    PRIMARY KEY (entity_id, chunk_id)
);

CREATE TABLE sdlc.edges (
    id                  bigserial PRIMARY KEY,
    source_id           text NOT NULL,
    classification_rank integer NOT NULL,
    src_id              bigint NOT NULL REFERENCES sdlc.entities(id) ON DELETE CASCADE,
    dst_id              bigint NOT NULL REFERENCES sdlc.entities(id) ON DELETE CASCADE,
    relation            text NOT NULL,
    chunk_id            bigint NOT NULL REFERENCES sdlc.chunks(id) ON DELETE CASCADE, -- evidence
    UNIQUE (src_id, dst_id, relation, chunk_id)
);

-- LLM extraction results keyed by a hash of (model, prompt version, types, chunk text), so
-- re-ingesting unchanged chunks costs nothing. Ingest-only: sdlc_app has no grant on it.
CREATE TABLE sdlc.extraction_cache (
    cache_key   text PRIMARY KEY,
    result      jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX entities_key ON sdlc.entities (key);
CREATE INDEX mentions_chunk ON sdlc.mentions (chunk_id);
CREATE INDEX edges_src ON sdlc.edges (src_id);
CREATE INDEX edges_dst ON sdlc.edges (dst_id);

ALTER TABLE sdlc.entities         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.entities         FORCE ROW LEVEL SECURITY;
ALTER TABLE sdlc.mentions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.mentions         FORCE ROW LEVEL SECURITY;
ALTER TABLE sdlc.edges            ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.edges            FORCE ROW LEVEL SECURITY;
ALTER TABLE sdlc.extraction_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdlc.extraction_cache FORCE ROW LEVEL SECURITY;

CREATE POLICY app_read ON sdlc.entities FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.max_classification_rank());
CREATE POLICY app_read ON sdlc.mentions FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.max_classification_rank());
CREATE POLICY app_read ON sdlc.edges FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.max_classification_rank());

CREATE POLICY ingest_all ON sdlc.entities         TO sdlc_ingest USING (true) WITH CHECK (true);
CREATE POLICY ingest_all ON sdlc.mentions         TO sdlc_ingest USING (true) WITH CHECK (true);
CREATE POLICY ingest_all ON sdlc.edges            TO sdlc_ingest USING (true) WITH CHECK (true);
CREATE POLICY ingest_all ON sdlc.extraction_cache TO sdlc_ingest USING (true) WITH CHECK (true);

GRANT SELECT ON sdlc.entities, sdlc.mentions, sdlc.edges TO sdlc_app;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON sdlc.entities, sdlc.mentions, sdlc.edges, sdlc.extraction_cache TO sdlc_ingest;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sdlc TO sdlc_ingest;
