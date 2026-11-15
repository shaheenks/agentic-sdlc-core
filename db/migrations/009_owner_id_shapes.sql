-- CH-0022: an artifact's owner is the token's user id on either stack: an Entra oid (GUID, Entra
-- stack) or a Google `sub` (digits, GCP stack). Only the shape check changes: ownership, RLS
-- (`app_owner` on sdlc.current_user_oid()) and grants are unchanged, and no row moves. The two
-- shapes never overlap, so one person on both stacks owns two separate sets of artifacts.
-- Same pattern as libs/sdlc_db (normalize_oid) and libs/sdlc_artifacts (object_key).

ALTER TABLE sdlc.artifacts DROP CONSTRAINT artifacts_owner_oid_check;
ALTER TABLE sdlc.artifacts ADD CONSTRAINT artifacts_owner_oid_check CHECK (
    owner_oid ~ '^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9]{1,64})$'
);

COMMENT ON COLUMN sdlc.artifacts.owner_oid IS 'the owner''s user id: Entra oid (GUID) or Google sub (digits)';
