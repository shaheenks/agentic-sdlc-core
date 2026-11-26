"""Handing a matched event to a run, and following the run on the event agents' Agent Runtime (DEC-0015).

The webhook is answered at once: each match becomes one Cloud Task, named after the delivery and the subscription so
the queue refuses a second one. The task calls `/run` with an OIDC token of the gateway's own service account; `/run`
creates the run's session (once: its ID is kept under `events/runs/`) with the run in the session's state, sends the
event as the run's input and follows its stream until the workflow ends. A retried task continues the same session,
and the workflow's tools return what an earlier attempt already did instead of doing it twice.
"""

import asyncio
import base64
import json
import re
import time
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from event_gateway.store import EventStore

TASKS_API = "https://cloudtasks.googleapis.com/v2"
SYSTEM_USER = "system"  # the Agent Runtime user of unattended runs
# Session state keys the event agents read and forward to event_agent_mcp as headers.
STATE_KEYS = ("sdlc_team", "sdlc_subscription", "sdlc_run_id", "sdlc_event", "sdlc_inputs", "sdlc_workflow")


def run_id(delivery_id: str, subscription_id: str) -> str:
    return f"{delivery_id}:{subscription_id}"


def task_id(delivery_id: str, subscription_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{delivery_id}-{subscription_id}")[:400]


class Credentials:
    """Google access tokens of the service's own identity, refreshed when needed."""

    def __init__(self, credentials=None) -> None:
        self._credentials = credentials

    async def token(self) -> str:
        if self._credentials is None:
            import google.auth

            self._credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not self._credentials.valid:
            import google.auth.transport.requests

            await asyncio.to_thread(self._credentials.refresh, google.auth.transport.requests.Request())
        return self._credentials.token


class Queue(Protocol):
    async def enqueue(self, name: str, job: dict[str, Any]) -> bool: ...


class CloudTasksQueue:
    """One HTTP task per run, to `<run_url>` with an OIDC token of `invoker`; a task of the same name is refused."""

    def __init__(self, queue: str, run_url: str, invoker: str, credentials: Credentials, client=None) -> None:
        self.queue, self.run_url, self.invoker, self.credentials = queue, run_url, invoker, credentials
        self.client = client or httpx.AsyncClient(timeout=15)

    async def enqueue(self, name: str, job: dict[str, Any]) -> bool:
        task = {
            "name": f"{self.queue}/tasks/{name}",
            "dispatchDeadline": "1800s",
            "httpRequest": {
                "url": self.run_url,
                "httpMethod": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(json.dumps(job).encode()).decode(),
                "oidcToken": {"serviceAccountEmail": self.invoker, "audience": self.run_url},
            },
        }
        response = await self.client.post(
            f"{TASKS_API}/{self.queue}/tasks",
            json={"task": task},
            headers={"Authorization": f"Bearer {await self.credentials.token()}"},
        )
        if response.status_code == 409:  # already queued for this delivery and subscription
            return False
        response.raise_for_status()
        return True


class InlineQueue:
    """The local environment: the run starts in this process."""

    def __init__(self, runner: "Runner") -> None:
        self.runner = runner
        self.started: list[asyncio.Task] = []

    async def enqueue(self, name: str, job: dict[str, Any]) -> bool:
        self.started.append(asyncio.create_task(self.runner.run(job)))
        return True


class Runner:
    """Starts and follows one run of an event agent's workflow on Agent Runtime."""

    def __init__(self, agent_url: str, store: EventStore, credentials: Credentials | None, client=None) -> None:
        self.agent_url, self.store, self.credentials = agent_url, store, credentials
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(30, read=600))

    async def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.credentials is not None:
            headers["Authorization"] = f"Bearer {await self.credentials.token()}"
        return headers

    async def _query(self, method: str, payload: Mapping[str, Any]) -> Any:
        response = await self.client.post(
            f"{self.agent_url}:query", json={"class_method": method, "input": payload}, headers=await self._headers()
        )
        response.raise_for_status()
        return response.json().get("output")

    async def session(self, job: Mapping[str, Any]) -> tuple[str, bool]:
        """The run's session: created once, then the same one for every retry of the task. (id, created)."""
        record_name = f"runs/{task_id(job['event']['delivery_id'], job['subscription'])}.json"
        record = await self.store.read(record_name)
        if record and record.get("session_id"):
            return record["session_id"], False
        state = {
            "sdlc_team": job["team"],
            "sdlc_subscription": job["subscription"],
            "sdlc_run_id": job["run_id"],
            "sdlc_event": job["event"],
            "sdlc_inputs": job["inputs"],
            "sdlc_workflow": job["workflow"],
        }
        created = await self._query("async_create_session", {"user_id": SYSTEM_USER, "state": state})
        session_id = str((created or {}).get("id") or "")
        if not session_id:
            raise RuntimeError("the agent runtime returned no session")
        await self.store.write(record_name, {"session_id": session_id, "run_id": job["run_id"], "status": "running"})
        return session_id, True

    async def run(self, job: Mapping[str, Any]) -> dict[str, Any]:
        """Runs the workflow to its end within the subscription's minutes; returns {status, events, session_id}."""
        session_id, created = await self.session(job)
        message = json.dumps(
            {"workflow": job["workflow"], "inputs": job["inputs"], "event": job["event"], "resumed": not created}
        )
        payload = {"user_id": SYSTEM_USER, "session_id": session_id, "message": message}
        deadline = time.monotonic() + 60 * int(job.get("minutes") or 25)
        events, errors = 0, 0
        async with self.client.stream(
            "POST",
            f"{self.agent_url}:streamQuery?alt=sse",
            json={"class_method": "async_stream_query", "input": payload},
            headers=await self._headers(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                text = line.strip().removeprefix("data:").strip()
                if not text or text.startswith(":"):
                    continue
                events += 1
                try:
                    item = json.loads(text)
                except ValueError:
                    continue
                if isinstance(item, dict) and (item.get("error_code") or item.get("error")):
                    errors += 1
                if time.monotonic() > deadline:
                    break
        status = "timed_out" if time.monotonic() > deadline else ("failed" if errors else "done")
        record_name = f"runs/{task_id(job['event']['delivery_id'], job['subscription'])}.json"
        await self.store.write(record_name, {"session_id": session_id, "run_id": job["run_id"], "status": status})
        return {"status": status, "events": events, "session_id": session_id}
