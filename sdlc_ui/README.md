# sdlc_ui

The custom web UI and its backend-for-frontend (BFF), built and deployed as one container
([NFR-ARCH-001](../spec/requirements/non-functional/NFR-ARCH-001.md), [sdlc_ui](../spec/components/sdlc-ui.md)).
CopilotKit with an AG-UI stream comes in phase 3.

**Phase 0 skeleton:** a home page and `GET /api/healthz`.

```sh
npm ci
npm run typecheck && npm test && npm run build
npm run dev          # http://localhost:3000
```

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `3000` | Port to listen on (Cloud Run sets it) |
