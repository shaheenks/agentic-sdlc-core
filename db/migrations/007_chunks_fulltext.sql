-- version-03 P11 (K1): keyword (full-text) search on chunks, next to the vector index.
--
-- `simple` text search configuration: no stemming and no stop words, so identifiers stay whole
-- (Jira keys, error codes, config keys, file and function names); prose is covered by the vector
-- search. Generated column: ingest needs no change, and the column follows every content update.
-- Same table, same rows: RLS policies and grants are unchanged (sdlc_app reads it under app_read).
-- Adding a STORED generated column rewrites the table once.

ALTER TABLE sdlc.chunks
    ADD COLUMN content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', coalesce(heading, '') || ' ' || content)) STORED;

CREATE INDEX chunks_content_tsv ON sdlc.chunks USING gin (content_tsv);

COMMENT ON COLUMN sdlc.chunks.content_tsv IS 'simple-config tsvector of heading + content (keyword search, P11)';
