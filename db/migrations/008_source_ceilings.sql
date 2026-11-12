-- CH-0009: the classification ceiling is per source. A team role counts only in its own team, so
-- an approver in one team does not get a higher ceiling on another team's sources.
--
-- New RLS context, set per transaction by libs/sdlc_db (SET LOCAL via set_config):
--   app.source_ceilings  JSON object, source id -> ceiling rank, e.g. '{"payments-code": 1}'
-- Every row is compared with the ceiling of ITS OWN source. A missing or malformed setting, or a
-- source not in it, gives -1: no rows (fail closed). app.allowed_sources still applies.
-- app.max_classification_rank and its function stay for compatibility, but no policy uses them.

CREATE OR REPLACE FUNCTION sdlc.source_ceiling(source text) RETURNS integer
LANGUAGE sql STABLE AS $$
  SELECT COALESCE(
    (NULLIF(current_setting('app.source_ceilings', true), '')::jsonb ->> source)::integer, -1)
$$;

GRANT EXECUTE ON FUNCTION sdlc.source_ceiling(text) TO sdlc_app, sdlc_ingest;

DROP POLICY app_read ON sdlc.sources;
DROP POLICY app_read ON sdlc.documents;
DROP POLICY app_read ON sdlc.chunks;
DROP POLICY app_read ON sdlc.entities;
DROP POLICY app_read ON sdlc.mentions;
DROP POLICY app_read ON sdlc.edges;

CREATE POLICY app_read ON sdlc.sources FOR SELECT TO sdlc_app
  USING (id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.source_ceiling(id));
CREATE POLICY app_read ON sdlc.documents FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.source_ceiling(source_id));
CREATE POLICY app_read ON sdlc.chunks FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.source_ceiling(source_id));
CREATE POLICY app_read ON sdlc.entities FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.source_ceiling(source_id));
CREATE POLICY app_read ON sdlc.mentions FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.source_ceiling(source_id));
CREATE POLICY app_read ON sdlc.edges FOR SELECT TO sdlc_app
  USING (source_id = ANY (sdlc.allowed_sources()) AND classification_rank <= sdlc.source_ceiling(source_id));
