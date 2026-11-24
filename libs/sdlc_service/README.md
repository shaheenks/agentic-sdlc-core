# sdlc_service

HTTP service basics shared by the platform's services: the `/healthz` route and `serve()`, which runs a Starlette
app with uvicorn on the port Cloud Run (or Docker Compose) gives in `PORT`.

| Variable | Default | Meaning |
|---|---|---|
| `HOST` | `0.0.0.0` | Interface to listen on |
| `PORT` | the service's default | Port to listen on |
