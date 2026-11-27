"""Receives, verifies, deduplicates and triages events, and starts unattended runs (FR-TRIG-001, FR-TRIG-004,
FR-IDN-004, NFR-OBS-003, DEC-0015).

- `POST /webhooks/github`: public. The signature is checked first; an unverified delivery is refused and audited
  before its body is read further. A verified delivery is matched against the subscriptions of the active
  configuration (only the system identity's teams); a match claims the delivery (create-if-absent, so a redelivery
  starts nothing) and queues one task per matched subscription; the answer is immediate.
- `GET /simulate` and `POST /simulate` (FR-TRIG-006, DEC-0016): sdlc_ui only, for a member of a team the
  environment allows to simulate. The pull request's facts are read from the provider, and the event then takes the
  same path as a verified webhook, marked `simulated` with the user who sent it (simulate.py).
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
from event_gateway.simulate import Refused, build_event, options, simulating_user, why_not
from event_gateway.simulate import allowed_teams as simulation_teams
from event_gateway.store import DirStore, EventStore, GcsStore
from event_gateway.triage import GITHUB, Event, Match, github_event, matches, verify_github

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
        self.provider_client = None  # tests give a faked provider's httpx.Client

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
        return await self.dispatch(event, found, bundle, fields)

    async def dispatch(
        self, event: Event, found: list[Match], bundle, fields: dict[str, Any], extra: dict[str, Any] | None = None
    ) -> JSONResponse:
        """Claims the delivery once and queues one run per match; a webhook and a simulation both end here."""
        delivery = event.delivery_id
        received = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        claim = {"received": received, "matched": [m.subscription_id for m in found], **(extra or {})}
        if not await self.store.claim(f"deliveries/{event.provider}/{task_id(delivery, 'delivery')}.json", claim):
            audit("event.duplicate", config_version=bundle.version, **fields)
            return JSONResponse({"matched": len(found), "duplicate": True, "delivery_id": delivery}, 200)
        for match in found:
            job = {
                "subscription": match.subscription_id,
                "agent": match.subscription.get("agent"),
                "workflow": match.subscription.get("workflow"),
                "team": match.team,
                "inputs": dict(match.inputs),
                "minutes": (match.subscription.get("limits") or {}).get("minutes", 25),
                "run_id": run_id(delivery, match.subscription_id),
                "event": {**event.metadata(), "actor": event.actor, "received": received, **(extra or {})},
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
        return JSONResponse({"matched": len(found), "delivery_id": delivery}, 202)

    async def simulation_options(self, request: Request) -> JSONResponse:
        try:
            bundle = await self.config.acurrent()
        except ConfigUnavailable:
            return JSONResponse({"error": "unavailable"}, 503)
        try:
            identity = await self._simulating_user(request, bundle.config)
        except Refused as exc:
            audit("simulation.denied", reason=exc.message if exc.status == 401 else exc.code)
            return JSONResponse({"error": exc.code}, exc.status)
        return JSONResponse(options(bundle.config, identity.email))

    async def simulate(self, request: Request) -> JSONResponse:
        try:
            bundle = await self.config.acurrent()
        except ConfigUnavailable:
            return JSONResponse({"error": "unavailable"}, 503)
        try:
            identity = await self._simulating_user(request, bundle.config)
        except Refused as exc:
            audit("simulation.denied", reason=exc.message if exc.status == 401 else exc.code)
            return JSONResponse({"error": exc.code}, exc.status)
        try:
            form = await request.json()
        except ValueError:
            form = None
        if not isinstance(form, dict):
            return JSONResponse({"error": "bad_request", "message": "send a JSON object"}, 400)
        team, sub_id = str(form.get("team") or ""), str(form.get("subscription") or "")
        fields = {"team": team[:60], "subscription": sub_id[:60], "user_id": identity.user_id}
        if team not in simulation_teams(bundle.config, identity.email):
            audit("simulation.denied", reason="team_not_allowed", **fields)
            message = "simulated events are not allowed for this team here, or you are not one of its members"
            return JSONResponse({"error": "forbidden", "message": message}, 403)
        sub = (bundle.config.get("subscriptions") or {}).get(sub_id)
        if not sub or not sub.get("enabled", True):
            return JSONResponse({"error": "not_found", "message": f"no enabled subscription {sub_id!r}"}, 404)
        try:
            event = await build_event(bundle.config, team, sub, form, self.settings.system_token, self.provider_client)
        except Refused as exc:
            audit("simulation.refused", reason=exc.code, **fields)
            return JSONResponse({"error": exc.code, "message": exc.message}, exc.status)
        fields |= event.metadata()
        found = [m for m in matches(bundle.config, event) if m.subscription_id == sub_id and m.team == team]
        if not found:
            audit("simulation.ignored", config_version=bundle.version, **fields)
            return JSONResponse({"error": "no_match", "message": why_not(sub, event)}, 422)
        audit("event.simulated", config_version=bundle.version, **fields)
        extra = {"simulated": True, "simulated_by": identity.user_id}
        matched = {**event.metadata(), "user_id": identity.user_id, "simulated": True}  # team and subscription per run
        return await self.dispatch(event, found, bundle, matched, extra)

    async def _simulating_user(self, request: Request, config):
        return await simulating_user(
            request.headers, config, self.tokens, env=self.settings.env, audience=self.settings.public_url
        )

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
        Route("/simulate", gateway.simulation_options, methods=["GET"]),
        Route("/simulate", gateway.simulate, methods=["POST"]),
        Route("/run", gateway.run, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app.state.gateway = gateway
    return app
