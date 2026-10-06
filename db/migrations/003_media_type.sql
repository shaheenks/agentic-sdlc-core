-- H10: PDF ingestion. Each document records its media type; for PDFs the chunks' line columns
-- hold page numbers, so search results can cite pages. RLS policies and grants are unchanged
-- (they filter on source_id + classification_rank, which every row still carries).

ALTER TABLE sdlc.documents
  ADD COLUMN media_type text NOT NULL DEFAULT 'text/plain';

COMMENT ON COLUMN sdlc.documents.media_type IS
  'text/plain (text files, chunked by lines) or application/pdf (chunked by pages)';
COMMENT ON COLUMN sdlc.chunks.start_line IS
  'first line (text/plain documents) or first page (application/pdf documents), 1-based';
COMMENT ON COLUMN sdlc.chunks.end_line IS
  'last line (text/plain documents) or last page (application/pdf documents), 1-based';
