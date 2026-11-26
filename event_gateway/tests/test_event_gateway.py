"""The event gateway: verification, triage against declared subscriptions, deduplication, the hand-off and the run,
with faked queue, agent runtime and Google APIs (FR-TRIG-001, DEC-0015)."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from event_gateway.runs import CloudTasksQueue, Credentials, Runner, task_id
from event_gateway.settings import Settings
from event_gateway.store import DirStore, GcsStore
from event_gateway.triage import Event, matches
from sdlc_config_store import DirSource, make_bundle, make_pointer
from sdlc_identity import GoogleTokens
from sdlc_logging import AUDIT_LOGGER
from starlette.testclient import TestClient

from event_gateway import SERVICE, create_app, create_gateway

NOW = 1_800_000_000
SECRET = "webhook-secret-never-logged"
PUBLIC_URL = "https://gateway.example.test"
INVOKER = "event-gateway@proj.iam.gserviceaccount.com"
ID = "F-20261126-refunds"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CONFIG = {
    "providers": {
        "github": {"system": "github", "edition": "cloud", "base_url": "https://api.github.com"},
        "bitbucket_cloud": {"system": "bitbucket", "edition": "cloud"},
    },
    "system": {"tool_groups": [], "sources": [], "teams": ["payments"], "machine_users": {"github": "sdlc-bot"}},
    "team_systems": {
        "payments": {
            "control_repo": {"provider": "github", "repo": "org/payments-sdlc-control"},
            "repositories": [{"provider": "github", "repo": "org/payments"}],
        },
        "risk": {"control_repo": {"provider": "github", "repo": "org/risk-sdlc-control"}, "repositories": []},
    },
    "subscriptions": {
        "ci_plan": {
            "agent": "ci_workflow_agent",
            "workflow": "plan",
            "enabled": True,
            "event": {"provider": "github", "type": "pull_request", "action": "closed"},
            "filters": {
                "repository": "control_repo",
                "merged": True,
                "base_branch": "^feature/F-[0-9]{8}-[a-z0-9-]+$",
                "head_branch": "^sdlc/(?P<control_id>F-[0-9]{8}-[a-z0-9-]+)/design-",
            },
            "writes": ["plan_open_pull_request"],
            "limits": {"minutes": 20},
        },
        "ci_implement": {
            "agent": "ci_workflow_agent",
            "workflow": "implement",
            "enabled": True,
            "event": {"provider": "github", "type": "pull_request", "action": "closed"},
            "filters": {
                "repository": "control_repo",
                "merged": True,
                "base_branch": "^feature/F-",
                "head_branch": "^sdlc/(?P<control_id>F-[0-9]{8}-[a-z0-9-]+)/plan-(?P<repo>[A-Za-z0-9_.-]+)$",
            },
            "writes": ["workspace_run"],
            "limits": {},
        },
    },
}


def pr_event(head: str, repo: str = "org/payments-sdlc-control", merged: bool = True, base: str = f"feature/{ID}"):
    return {
        "action": "closed",
        "repository": {"full_name": repo},
        "sender": {"login": "grace"},
        "pull_request": {"number": 5, "merged": merged, "base": {"ref": base}, "head": {"ref": head}},
    }


def signed(payload: dict, delivery: str = "d-1", event: str = "pull_request", secret: str = SECRET):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": delivery, "X-Hub-Signature-256": signature}
    return body, headers


def id_token(email: str = INVOKER, aud: str = f"{PUBLIC_URL}/run") -> str:
    claims = {"iss": "https://accounts.google.com", "aud": aud, "sub": "77", "email": email, "email_verified": True}
    return jwt.encode({**claims, "exp": NOW + 3600}, KEY, algorithm="RS256")


def verify_locally(token: str) -> dict:
    return jwt.decode(token, KEY.public_key(), algorithms=["RS256"], options={"verify_aud": False, "verify_exp": False})


class FakeQueue:
    def __init__(self):
        self.tasks: dict[str, dict] = {}

    async def enqueue(self, name, job):
        if name in self.tasks:
            return False
        self.tasks[name] = job
        return True


class FakeRunner:
    def __init__(self):
        self.jobs = []

    async def run(self, job):
        self.jobs.append(job)
        return {"status": "done", "events": 3, "session_id": "s-1"}


@pytest.fixture
def env(tmp_path):
    source = DirSource(tmp_path / "config")
    doc = make_bundle("test", CONFIG)
    source.write(f"bundles/{doc['version']}.json", json.dumps(doc).encode())
    source.write("active.json", json.dumps(make_pointer(doc["version"], "tester", None)).encode())
    settings = Settings(
        env="test",
        config_source=str(tmp_path / "config"),
        public_url=PUBLIC_URL,
        events_dir=tmp_path / "events",
        tasks_queue="projects/p/locations/r/queues/q",
        tasks_invoker=INVOKER,
        agent_url="https://agent.example.test/v1/engine",
        config_refresh_seconds=0,
        secrets={"WEBHOOK_SECRET_GITHUB": SECRET},
    )
    queue, runner = FakeQueue(), FakeRunner()
    gateway = create_gateway(
        settings,
        queue=queue,
        runner=runner,
        tokens=GoogleTokens(verify_id_token=verify_locally, clock=lambda: NOW),
    )
    gateway.config.load()
    with TestClient(create_app(gateway=gateway)) as client:
        yield client, queue, runner, gateway


def post(client, payload, **kw):
    body, headers = signed(payload, **kw)
    return client.post("/webhooks/github", content=body, headers=headers)


def test_healthz(env):
    client, *_ = env
    assert client.get("/healthz").json()["service"] == SERVICE


def test_an_unsigned_or_wrongly_signed_delivery_is_refused_before_anything_else(env, caplog):
    client, queue, *_ = env
    body, headers = signed(pr_event(f"sdlc/{ID}/design-abc"), secret="wrong")
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        assert client.post("/webhooks/github", content=body, headers=headers).status_code == 401
        unsigned = {k: v for k, v in headers.items() if k != "X-Hub-Signature-256"}
        assert client.post("/webhooks/github", content=body, headers=unsigned).status_code == 401
    assert not queue.tasks
    assert [getattr(r, "reason", None) for r in caplog.records if getattr(r, "reason", None)] == ["bad_signature"] * 2
    assert SECRET not in " ".join(json.dumps(r.__dict__, default=str) for r in caplog.records)


def test_a_merged_design_starts_one_plan_run_and_a_redelivery_none(env, caplog):
    client, queue, *_ = env
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = post(client, pr_event(f"sdlc/{ID}/design-abc123"), delivery="d-1")
    assert response.status_code == 202 and response.json() == {"matched": 1}
    ((name, job),) = queue.tasks.items()
    assert name == task_id("d-1", "ci_plan")
    assert (job["subscription"], job["workflow"], job["team"], job["inputs"]) == (
        "ci_plan",
        "plan",
        "payments",
        {"control_id": ID},
    )
    assert job["run_id"] == "d-1:ci_plan" and job["minutes"] == 20
    assert job["event"]["subject"] == "org/payments-sdlc-control#5" and job["event"]["actor"] == "grace"
    again = post(client, pr_event(f"sdlc/{ID}/design-abc123"), delivery="d-1")
    assert again.status_code == 200 and again.json()["duplicate"] is True and len(queue.tasks) == 1


def test_a_merged_plan_starts_the_implementation_for_its_repository(env):
    client, queue, *_ = env
    post(client, pr_event(f"sdlc/{ID}/plan-payments"), delivery="d-2")
    (job,) = queue.tasks.values()
    assert job["subscription"] == "ci_implement" and job["inputs"] == {"control_id": ID, "repo": "payments"}


@pytest.mark.parametrize(
    "payload",
    [
        pr_event(f"sdlc/{ID}/design-abc", merged=False),  # closed without merging
        pr_event("fix/typo"),  # not an agent artifact branch
        pr_event(f"sdlc/{ID}/design-abc", base="main"),  # not into a feature branch
        pr_event(f"sdlc/{ID}/design-abc", repo="org/payments"),  # a product repository, not the control one
        pr_event(f"sdlc/{ID}/design-abc", repo="org/risk-sdlc-control"),  # a team the system identity does not serve
        {**pr_event(f"sdlc/{ID}/design-abc"), "action": "opened"},
    ],
)
def test_events_no_subscription_matches_are_ignored_and_audited(env, payload, caplog):
    client, queue, *_ = env
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = post(client, payload, delivery="d-3")
    assert response.status_code == 202 and response.json() == {"matched": 0} and not queue.tasks
    assert [r.getMessage() for r in caplog.records] == ["event.ignored"]


def test_triage_reads_only_metadata():
    event = Event("github", "pull_request", "d", "closed", "org/payments-sdlc-control", True, f"feature/{ID}", "x")
    assert matches(CONFIG, event) == []
    plan = Event(
        "github",
        "pull_request",
        "d",
        "closed",
        "ORG/payments-sdlc-control",
        True,
        f"feature/{ID}",
        f"sdlc/{ID}/plan-app",
    )
    (found,) = matches(CONFIG, plan)
    assert (found.subscription_id, found.team, found.inputs) == (
        "ci_implement",
        "payments",
        {"control_id": ID, "repo": "app"},
    )
    off = {**CONFIG, "subscriptions": {k: {**v, "enabled": False} for k, v in CONFIG["subscriptions"].items()}}
    assert matches(off, plan) == []


def test_run_accepts_only_the_queues_token_and_follows_the_run(env, caplog):
    client, queue, runner, _ = env
    post(client, pr_event(f"sdlc/{ID}/design-abc"), delivery="d-4")
    (job,) = queue.tasks.values()
    assert client.post("/run", json=job).status_code == 401
    assert (
        client.post(
            "/run", json=job, headers={"Authorization": f"Bearer {id_token(email='x@p.iam.gserviceaccount.com')}"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/run", json=job, headers={"Authorization": f"Bearer {id_token(aud='https://elsewhere')}"}
        ).status_code
        == 401
    )
    assert not runner.jobs
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = client.post("/run", json=job, headers={"Authorization": f"Bearer {id_token()}"})
    assert response.status_code == 200 and response.json()["status"] == "done" and runner.jobs == [job]
    finished = next(
        r for r in caplog.records if r.getMessage() == "run.finished" or getattr(r, "status", None) == "done"
    )
    assert finished.delivery_id == "d-4" and finished.subscription == "ci_plan"
    skipped = client.post("/run", json={**job, "team": "risk"}, headers={"Authorization": f"Bearer {id_token()}"})
    assert skipped.json()["status"] == "skipped" and len(runner.jobs) == 1


class FakeEngine:
    """Agent Runtime's :query and :streamQuery, faked."""

    def __init__(self):
        self.sessions, self.queries = 0, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.queries.append(body)
        if request.url.path.endswith(":query"):
            self.sessions += 1
            assert body["input"]["state"]["sdlc_team"] == "payments"
            return httpx.Response(200, json={"output": {"id": f"s-{self.sessions}"}})
        lines = 'data: {"author": "plan", "content": {}}\n\ndata: {"author": "plan"}\n'
        return httpx.Response(200, text=lines)


def test_the_runner_creates_the_session_once_and_a_retry_continues_it(tmp_path):
    engine = FakeEngine()
    store = DirStore(tmp_path)
    runner = Runner("https://agent.test/v1/e", store, None, httpx.AsyncClient(transport=httpx.MockTransport(engine)))
    job = {
        "subscription": "ci_plan",
        "workflow": "plan",
        "team": "payments",
        "inputs": {"control_id": ID},
        "run_id": "d-5:ci_plan",
        "minutes": 1,
        "event": {"delivery_id": "d-5", "event_source": "github"},
    }
    first = asyncio.run(runner.run(job))
    second = asyncio.run(runner.run(job))
    assert first == {"status": "done", "events": 2, "session_id": "s-1"} and second["session_id"] == "s-1"
    assert engine.sessions == 1
    messages = [json.loads(q["input"]["message"]) for q in engine.queries if "message" in q["input"]]
    assert [m["resumed"] for m in messages] == [False, True] and messages[0]["inputs"] == {"control_id": ID}
    assert asyncio.run(store.read(f"runs/{task_id('d-5', 'ci_plan')}.json"))["status"] == "done"


def test_deliveries_are_claimed_once_in_the_bucket():
    seen = []

    def gcs(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(412) if len(seen) > 1 else httpx.Response(200, json={})

    creds = type("C", (), {"valid": True, "token": "t"})()
    store = GcsStore("bucket", httpx.AsyncClient(transport=httpx.MockTransport(gcs)), creds)
    assert asyncio.run(store.claim("deliveries/github/d-1.json", {})) is True
    assert asyncio.run(store.claim("deliveries/github/d-1.json", {})) is False
    assert (
        seen[0].url.params["ifGenerationMatch"] == "0"
        and seen[0].url.params["name"] == "events/deliveries/github/d-1.json"
    )
    with pytest.raises(ValueError):
        asyncio.run(store.claim("../x", {}))


def test_cloud_tasks_get_an_oidc_token_and_one_name_per_run():
    seen = []

    def tasks(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(409) if len(seen) > 1 else httpx.Response(200, json={})

    creds = Credentials(type("C", (), {"valid": True, "token": "t"})())
    queue = CloudTasksQueue(
        "projects/p/locations/r/queues/q",
        f"{PUBLIC_URL}/run",
        INVOKER,
        creds,
        httpx.AsyncClient(transport=httpx.MockTransport(tasks)),
    )
    assert asyncio.run(queue.enqueue("d-1-ci_plan", {"a": 1})) is True
    assert asyncio.run(queue.enqueue("d-1-ci_plan", {"a": 1})) is False
    task = seen[0]["task"]
    assert task["name"] == "projects/p/locations/r/queues/q/tasks/d-1-ci_plan"
    assert task["httpRequest"]["oidcToken"] == {"serviceAccountEmail": INVOKER, "audience": f"{PUBLIC_URL}/run"}
    assert json.loads(base64.b64decode(task["httpRequest"]["body"])) == {"a": 1}


def test_settings_fail_closed():
    base = {"CONFIG_SOURCE": "gs://c", "PUBLIC_URL": PUBLIC_URL, "AGENT_URL": "https://a"}
    with pytest.raises(SystemExit):
        Settings.from_env({**base, "SDLC_ENV": "dev", "EVENTS_DIR": "/tmp/e"})  # a folder only locally
    with pytest.raises(SystemExit):
        Settings.from_env({**base, "SDLC_ENV": "dev", "EVENTS_BUCKET": "b"})  # no queue
    with pytest.raises(SystemExit):
        Settings.from_env({**base, "SDLC_ENV": "dev", "EVENTS_BUCKET": "b", "TASKS_MODE": "inline"})
    ok = Settings.from_env(
        {
            **base,
            "SDLC_ENV": "dev",
            "EVENTS_BUCKET": "b",
            "TASKS_QUEUE": "projects/p/locations/r/queues/q",
            "TASKS_INVOKER": INVOKER,
            "WEBHOOK_SECRET_GITHUB": SECRET,
        }
    )
    assert (
        ok.webhook_secret("github") == SECRET.encode() and SECRET not in repr(ok) and ok.run_url == f"{PUBLIC_URL}/run"
    )
