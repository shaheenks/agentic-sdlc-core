# config/sources

kind: Source — source artefact location, include/exclude, classification, ingest settings, access.

Types:
- `local_folder`: files under `location` (working tree).
- `git`: files of the commit `ref` in a repository at `location` (a path, e.g. `.` for this repo, or an
  `https://` URL, partially cloned into `.cache/git/`). Never the working tree; pin a full commit SHA so the
  corpus (and evals built on it) is reproducible, and bump it deliberately to re-index.

Remote sources (version-01): an `https://` location must be on a host listed in `platform.yaml`
`knowledge.allowed_hosts` (exact names or `*.example.net`; SSRF guard), and never carries credentials in the URL.
A source that needs a credential names it, never its value: `spec.credentials: { env: NAME }` or
`{ secret: name }` (Secret Manager on GCP, `SDLC_SECRET_<NAME>` locally; see `libs/sdlc_secrets`). Only source
types whose loaders read credentials accept the field.

PDFs (H10): add `**/*.pdf` to `include`; optional `spec.ingest.pdf: {ocr: none|gemini, max_mb: 50, max_pages: 500}`.
`ocr: gemini` sends pages without a text layer (scans) to `platform.yaml` `knowledge.ocr.model`; results cite pages.

Globs (`include`/`exclude`) match the whole path relative to the source root: `*` within a directory,
`**` across directories (`docs/**`, `**/*.md`). Every source needs rows in `tests/policy/matrix.yaml`
(data_rows) and a rule in `.github/CODEOWNERS`.
