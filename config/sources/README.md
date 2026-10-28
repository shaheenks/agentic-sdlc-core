# config/sources

kind: Source — source artefact location, include/exclude, classification, ingest settings, access.

Types:
- `local_folder`: files under `location` (working tree).
- `git`: files of the commit `ref` in a repository at `location` (a path, e.g. `.` for this repo, or an
  `https://` URL, partially cloned into the ingest cache). Never the working tree. `ref` is a full commit SHA
  (pinned: keep this for eval corpora such as `sdlc-platform`) or a branch/tag (tracked: resolved every run).
  Re-runs read only files changed since the last ingested commit.
  Remote repositories (version-01 M1) need `provider` and, if private, `credentials`:

  ```yaml
  spec:
    type: git
    location: https://github.com/acme/payments.git   # bitbucket.org/<ws>/<repo>.git | https://<host>/scm/<proj>/<repo>.git
    provider: github                                 # github | bitbucket-cloud | bitbucket-dc
    ref: main
    credentials: { secret: github-acme-token }       # read-only token; never the value
  ```

  Tokens: GitHub App installation token or fine-grained PAT (Contents: read), Bitbucket Cloud repository access
  token (read), Bitbucket DC HTTP access token (repository read). The token is sent as an HTTP header to the
  repository host only, through git's environment (never the URL or argv). Results link to the file at its commit.

- `gcs` (version-01 M2): objects under `location: gs://<bucket>/<prefix>/`; globs match names relative to the
  prefix. Read with Application Default Credentials (gcloud ADC locally, the ingest service identity on GCP:
  add the bucket to Terraform `gcs_source_buckets` for `roles/storage.objectViewer` on that bucket only). No
  `credentials`, no keys. Unchanged objects (same generation) are not downloaded; results link to the object.

- `confluence` (version-01 M3): the pages of one space, Cloud or Data Center.

  ```yaml
  spec:
    type: confluence
    edition: cloud                                  # cloud | datacenter
    location: https://acme.atlassian.net/wiki       # DC: https://<host>[/<context>]
    space: PAY
    cql: "label = runbook"                          # optional narrowing
    attachments: [pdf]                              # optional: PDF attachments of selected pages
    credentials: { secret: confluence-pay }         # Cloud: "<email>:<api token>"; DC: a personal access token
  ```

  No `include`/`exclude` (narrow with `cql`). Pages with view restrictions on themselves or an ancestor are never
  ingested and a stored copy is deleted, checked on every run. Only pages whose version changed are downloaded.
  Pages become Markdown (`# Title`, the ancestor path, the body); results link to the page. Cloud PDF attachments
  download through `api.media.atlassian.com`: add it to `allowed_hosts` (credentials are not sent to it).

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
