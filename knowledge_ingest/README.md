# knowledge_ingest

Ingests the knowledge sources declared in `config/env/<env>/sources.yaml` (read from the active bundle) into the JSONL knowledge store
([Ingest Pipeline](../spec/components/ingest-pipeline.md); FR-KNOW-001, FR-KNOW-003, DEC-0011). It runs as a
step of the build pipeline, before the Knowledge Search image is built from its output.

```sh
# Local: the hash embedder, no Google Cloud access
EMBEDDINGS=hash uv run sdlc-knowledge-ingest --env local --config .data/config --out .data/knowledge --no-extract
# With Vertex AI (your gcloud Application Default Credentials)
GOOGLE_CLOUD_PROJECT=<project> uv run sdlc-knowledge-ingest --env dev --config gs://<config bucket> \
    --out knowledge_search/knowledge
```

- Sources come from the active configuration bundle. A `folder` source is read under `--root` (default: the
  current folder, the build checkout) or from a `gs://` prefix; a `git` source is shallow-cloned at its `ref`.
- The previous store (`--previous`, default `--out`) supplies unchanged files' chunks, embeddings and
  extractions, so a refresh embeds and extracts only what changed. `--source ID` re-reads only those sources.
- `manifest.json` records the run and each source's status. The run exits 1 when a source failed; that source
  keeps its previous records.
- `extractions.jsonl` caches the model's answer per file; Knowledge Search does not read it.

## Refresh in Google Cloud

A refresh is one Cloud Build run of [cloudbuild.yaml](cloudbuild.yaml), as the knowledge_ingest service
account. It fetches the previous store from the knowledge bucket, ingests, keeps the new store, builds and
pushes the Knowledge Search image, and rolls `knowledge-search` out to it. From the repository root, with the
Terraform outputs `knowledge_bucket`, `config_bucket` and `knowledge_ingest_service_account` (you must be in
`knowledge_refreshers`):

```sh
gcloud builds submit --config knowledge_ingest/cloudbuild.yaml --region europe-west3 \
  --service-account projects/<project>/serviceAccounts/<knowledge_ingest_service_account> \
  --gcs-source-staging-dir gs://<knowledge_bucket>/source \
  --substitutions _CONFIG_BUCKET=<config_bucket>,_KNOWLEDGE_BUCKET=<knowledge_bucket> .
```

The upload skips what `.gitignore` lists; folder sources such as `spec/` are read from it. A failed source
stops the build before anything is kept or rolled out.

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `CONFIG_SOURCE` | - | Published bundles (or `--config`): a folder, or `gs://<configuration bucket>` |
| `SDLC_ENV` | `local` | The environment whose active bundle is read (or `--env`) |
| `KNOWLEDGE_PATH` | `.data/knowledge` | Output folder (or `--out`) |
| `EMBEDDINGS` | `vertex` | `vertex`, or `hash` for local runs and tests |
| `GOOGLE_CLOUD_PROJECT` | - | Project for Vertex AI and Secret Manager |
| `VERTEX_LOCATION` | `europe-west3` | Embedding region |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | `gemini-embedding-001`, `768` | Must match Knowledge Search |
| `EXTRACTION` | `vertex` | `vertex`, or anything else for no extraction (as `--no-extract`) |
| `EXTRACT_MODEL`, `EXTRACT_LOCATION` | `gemini-3.8-flash`, `eu` | Concept extraction; the model has no europe-west3 endpoint |
| `INGEST_SECRET_<NAME>` | - | Local only: a private repository's read token instead of Secret Manager secret `<name>` |
| `LOG_LEVEL` | `INFO` | Minimum log level |
