"""Receives, verifies, deduplicates and triages events, and starts unattended runs (FR-TRIG-001, FR-TRIG-004,
FR-IDN-004, NFR-OBS-003, DEC-0015).

- `POST /webhooks/github`: public. The signature is checked first; an unverified delivery is refused and audited
  before its body is read further. A verified delivery is matched against the subscriptions of the active
  configuration (only the system identity's teams); a match claims the delivery (create-if-absent, so a redelivery
  starts nothing) and queues one task per matched subscription; the answer is immediate.
- `POST /run`: only the queue's OIDC token for the gateway's own service account. Starts the run on the event
  agents' Agent Runtime and follows it to its end (runs.py).

Every delivery received, matched, ignored, duplicated or rejected is audited with its metadata; payloads and
secrets never are.
"""

import time
from typing import Any

from sdlc_config_store import ConfigStore, ConfigUnavailable, source_from_url
from sdlc_identity import GoogleTokens, Rejected
from sdlc_logging import audit
from sdlc_service import health_routes
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from event_gateway.runs import CloudTasksQueue, Credentials, InlineQueue, Queue, Runner, run_id, task_id
from event_gateway.settings import Settings
from event_gateway.store import DirStore, EventStore, GcsStore
from event_gateway.triage import GITHUB, github_event, matches, verify_github

SERVICE = "event_gateway"
DEFAULT_PORT = 8084


class Gateway:
    def __init__(
        self,
        settings: Settings,
        config: ConfigStore,
        store: EventStore,
        runner: Runner,
        queue: Queue,
        tokens: GoogleTokens,
    ) -> None:
        self.settings, self.config, self.store, self.runner, self.queue, self.tokens = (
            settings,
            config,
            store,
            runner,
            queue,
            tokens,
        )

    async def github(self, request: Request) -> JSONResponse:
        event_type = request.headers.get("x-github-event", "")
        delivery = request.headers.get("x-github-delivery", "")
        fields = {"provider": GITHUB, "event_type": event_type[:60], "delivery_id": delivery[:100]}
        body = await request.body()
        if len(body) > self.settings.max_body_bytes:
            audit("event.rejected", reason="too_large", **fields)
            return JSONResponse({"error": "too_large"}, 413)
        if not verify_github(self.settings.webhook_secret(GITHUB), body, request.headers.get("x-hub-signature-256")):
            audit("event.rejected", reason="bad_signature", **fields)
            return JSONResponse({"error": "unauthorized"}, 401)
        if not delivery or not event_type:
            audit("event.rejected", reason="no_delivery", **fields)
            return JSONResponse({"error": "bad_request"}, 400)
        try:
            payload = await request.json()
        except ValueError:
            audit("event.rejected", reason="not_json", **fields)
            return JSONResponse({"error": "bad_request"}, 400)
        event = github_event(event_type, delivery, payload if isinstance(payload, dict) else {})
        fields |= event.metadata()
        try:
            bundle = await self.config.acurrent()
        except ConfigUnavailable:
            audit("event.rejected", reason="config_unavailable", **fields)
            return JSONResponse({"error": "unavailable"}, 503)  # the provider redelivers later
        found = matches(bundle.config, event)
        if not found:
            audit("event.ignored", config_version=bundle.version, **fields)
            return JSONResponse({"matched": 0}, 202)
        received = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        claim = {"received": received, "matched": [m.subscription_id for m in found]}
        if not await self.store.claim(f"deliveries/{GITHUB}/{task_id(delivery, 'delivery')}.json", claim):
            audit("event.duplicate", config_version=bundle.version, **fields)
            return JSONResponse({"matched": len(found), "duplicate": True}, 200)
        for match in found:
            job = {
                "subscription": match.subscription_id,
                "agent": match.subscription.get("agent"),
                "workflow": match.subscription.get("workflow"),
                "team": match.team,
                "inputs": dict(match.inputs),
                "minutes": (match.subscription.get("limits") or {}).get("minutes", 25),
                "run_id": run_id(delivery, match.subscription_id),
                "event": {**event.metadata(), "actor": event.actor, "received": received},
                "config_version": bundle.version,
            }
            queued = await self.queue.enqueue(task_id(delivery, match.subscription_id), job)
            audit(
                "event.matched",
                subscription=match.subscription_id,
                team=match.team,
                run_id=job["run_id"],
                queued=queued,
                config_version=bundle.version,
                **fields,
            )
        return JSONResponse({"matched": len(found)}, 202)

    async def run(self, request: Request) -> JSONResponse:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        try:
            if not token:
                raise Rejected("no_token")
            claims = await self.tokens.claims(token)
            if claims.get("kind") != "id" or claims.get("client_id") != self.settings.run_url:
                raise Rejected("wrong_audience")
            if not claims.get("email_verified") or claims.get("email") != self.settings.tasks_invoker:
                raise Rejected("not_the_queue")
        except Rejected as exc:
            audit("run.denied", reason=exc.reason)
            return JSONResponse({"error": "unauthorized"}, 401)
        job: dict[str, Any] = await request.json()
        return await self.start(job)

    async def start(self, job: dict[str, Any]) -> JSONResponse:
        fields = {"run_id": job.get("run_id"), "subscription": job.get("subscription"), "team": job.get("team")}
        fields |= {k: v for k, v in (job.get("event") or {}).items() if k != "actor"}
        bundle = await self.config.acurrent()
        sub = (bundle.config.get("subscriptions") or {}).get(job.get("subscription") or "")
        teams = (bundle.config.get("system") or {}).get("teams") or ()
        if not sub or not sub.get("enabled", True) or job.get("team") not in teams:
            audit("run.skipped", reason="no_longer_declared", config_version=bundle.version, **fields)
            return JSONResponse({"status": "skipped"}, 200)
        audit("run.started", agent=job.get("agent"), workflow=job.get("workflow"), **fields)
        result = await self.runner.run(job)  # an exception fails the task, and the queue retries it
        audit("run.finished", status=result["status"], events=result["events"], **fields)
        return JSONResponse(result, 200)


def create_gateway(settings: Settings, **overrides) -> Gateway:
    """The service's parts, built from settings; tests replace some of them."""
    store = overrides.pop("store", None) or (
        GcsStore(settings.events_bucket) if settings.events_bucket else DirStore(settings.events_dir)
    )
    credentials = Credentials()
    runner = overrides.pop("runner", None) or Runner(
        settings.agent_url, store, credentials if settings.agent_auth == "google" else None
    )
    queue = overrides.pop("queue", None) or (
        InlineQueue(runner)
        if settings.tasks_mode == "inline"
        else CloudTasksQueue(settings.tasks_queue, settings.run_url, settings.tasks_invoker, credentials)
    )
    parts = {
        "config": ConfigStore(source_from_url(settings.config_source), settings.env, settings.config_refresh_seconds),
        "tokens": GoogleTokens(),
        **overrides,
    }
    return Gateway(settings, store=store, runner=runner, queue=queue, **parts)


def create_app(settings: Settings | None = None, gateway: Gateway | None = None) -> Starlette:
    """The ASGI app. Without a gateway it loads the active configuration first, and refuses to start when no verified
    bundle can be loaded (FR-CFG-001)."""
    if gateway is None:
        gateway = create_gateway(settings or Settings.from_env())
        gateway.config.load()
    routes = health_routes(SERVICE) + [
        Route("/webhooks/github", gateway.github, methods=["POST"]),
        Route("/run", gateway.run, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app.state.gateway = gateway
    return app
