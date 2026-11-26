"""event_agent_mcp end to end, through HTTP: the system identity, its runs, the write gate per subscription, and the
plan and implementation chain on the feature branches (DEC-0015), against faked GitHub repositories."""

import json
import logging
from pathlib import Path

import httpx
import jwt
import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa
from event_agent_mcp import SERVICE, create_app, create_platform
from event_agent_mcp.settings import Settings
from event_agent_mcp.tools import TOOLS
from sdlc_config_store import DirSource, make_bundle, make_pointer
from sdlc_connectors.testing import FakeGitHub
from sdlc_control import with_front_matter
from sdlc_identity import GoogleTokens
from sdlc_logging import AUDIT_LOGGER
from starlette.testclient import TestClient

NOW = 1_800_000_000
PROTOCOL = "2026-07-28"
PUBLIC_URL = "http://testserver"
EVENT_ACCOUNT = "event-agents@proj.iam.gserviceaccount.com"
AGENT_ACCOUNT = "user-agent@proj.iam.gserviceaccount.com"
SYSTEM_TOKEN = "ghp_system-token-never-logged"
ID = "F-20261126-refunds"
FEATURE = f"feature/{ID}"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CONFIG = {
    "tool_groups": {
        "repositories": {"description": "-", "tools": ["repo_list", "repo_read_file", "repo_pull_requests"]},
        "ci_read": {"description": "-", "tools": ["feature_status", "control_read_file"]},
        "ci_write": {
            "description": "-",
            "tools": ["plan_open_pull_request", "implementation_open_pull_request", "pull_request_comment"],
        },
        "code_workspace": {"description": "-", "tools": ["workspace_run"]},
    },
    "surfaces": {
        "event_agents": {
            "description": "-",
            "system": True,
            "tool_groups": ["repositories", "ci_read", "ci_write", "code_workspace"],
        },
        "user_agent": {"description": "-", "tool_groups": ["repositories"]},
    },
    "teams": {"payments": {"name": "Payments", "description": "-", "roles": ["member"]}},
    "user_groups": {},
    "grants": [{"id": "everyone", "tool_groups": ["repositories"], "to": {"everyone": True}}],
    "providers": {
        "github": {"name": "GitHub", "system": "github", "edition": "cloud", "base_url": "https://api.github.com"}
    },
    "sources": {},
    "identity": {
        "mode": "caller_token",
        "allowed_domains": ["example.test"],
        "callers": {"event_agents": [EVENT_ACCOUNT], "user_agent": [AGENT_ACCOUNT]},
        "clients": {},
    },
    "members": {},
    "blocked": [],
    "system": {
        "tool_groups": ["repositories", "ci_read", "ci_write", "code_workspace"],
        "sources": [],
        "teams": ["payments"],
        "machine_users": {"github": "sdlc-bot"},
    },
    "subscriptions": {
        "ci_plan": {
            "description": "-",
            "agent": "ci_workflow_agent",
            "workflow": "plan",
            "enabled": True,
            "writes": ["plan_open_pull_request", "pull_request_comment"],
            "limits": {},
        },
        "ci_implement": {
            "description": "-",
            "agent": "ci_workflow_agent",
            "workflow": "implement",
            "enabled": True,
            "writes": ["implementation_open_pull_request", "pull_request_comment", "workspace_run"],
            "limits": {"workspace_runs": 2},
        },
        "off": {
            "description": "-",
            "agent": "ci_workflow_agent",
            "workflow": "plan",
            "enabled": False,
            "writes": ["x"],
        },
    },
    "team_systems": {
        "payments": {
            "jira": [],
            "confluence": [],
            "repositories": [
                {
                    "provider": "github",
                    "repo": "org/payments",
                    "default": True,
                    "default_branch": "main",
                    "workspace": {"test": ["pytest -q"]},
                }
            ],
            "control_repo": {
                "provider": "github",
                "repo": "org/payments-sdlc-control",
                "branch": "main",
                "system_accounts": ["sdlc-bot"],
            },
        }
    },
}


def caller_token(account: str, aud: str = PUBLIC_URL) -> str:
    claims = {"iss": "https://accounts.google.com", "aud": aud, "sub": "9" + str(len(account)), "email": account}
    return jwt.encode({**claims, "email_verified": True, "exp": NOW + 3600}, KEY, algorithm="RS256")


def verify_locally(token: str) -> dict:
    return jwt.decode(token, KEY.public_key(), algorithms=["RS256"], options={"verify_aud": False, "verify_exp": False})


def run_headers(subscription: str = "ci_plan", team: str = "payments", run_id: str = "run-1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {caller_token(EVENT_ACCOUNT)}",
        "X-SDLC-Team": team,
        "X-SDLC-Subscription": subscription,
        "X-SDLC-Run-Id": run_id,
        "X-SDLC-Event-Source": "github",
        "X-SDLC-Event-Type": "pull_request.closed",
        "X-SDLC-Event-Delivery": "d-123",
        "X-SDLC-Event-Subject": "org/payments-sdlc-control#5",
    }


class Workspace:
    """The Code Workspace, faked: applies the change set to the implementation branch of the target repository."""

    def __init__(self, target: FakeGitHub, ok: bool = True):
        self.target, self.ok, self.requests = target, ok, []

    async def run(self, request_path: Path, relative: str) -> None:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        self.requests.append(request)
        tree = self.target.trees.setdefault(request["branch"], dict(self.target.trees[request["base"]]))
        for change in request["changes"]:
            if change.get("delete"):
                tree.pop(change["path"], None)
            else:
                tree[change["path"]] = change["content"]
        step = {
            "name": "test",
            "command": "pytest -q",
            "exit_code": 0 if self.ok else 1,
            "seconds": 1,
            "log_tail": "ok",
        }
        result = {"ok": self.ok, "steps": [step], "commit": "abc123", "pushed": True}
        (request_path.parent / "result.json").write_text(json.dumps(result), encoding="utf-8")


@pytest.fixture
def systems(monkeypatch):
    ctrl, target = FakeGitHub("/repos/org/payments-sdlc-control"), FakeGitHub("/repos/org/payments")
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        for fake in (ctrl, target):
            if request.url.path.startswith(fake.BASE + "/") or request.url.path == fake.BASE:
                return fake.handle(request)
        return httpx.Response(404)

    real = httpx.Client
    monkeypatch.setattr("sdlc_connectors.base.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(handle)))
    # the feature, approved in chat, its design merged into its branch by a person, its Jira keys and target branches
    ctrl.trees[FEATURE] = {}
    ctrl.push(FEATURE, f"features/{ID}/feature.md", with_front_matter("# Refunds", {"approved_by": "ada@example.test"}))
    ctrl.trees[FEATURE][f"features/{ID}/design.md"] = with_front_matter("# Design", {"kind": "design"})
    ctrl.how[(FEATURE, f"features/{ID}/design.md")] = (5, "grace")
    links = {
        "writes": [
            {"action": "create_in_jira", "results": {"feature": "PAY-1", "stories": ["PAY-2", "PAY-3"]}},
            {"action": "open_branches", "results": {"branch": FEATURE, "org/payments": "created"}},
        ]
    }
    ctrl.push(FEATURE, f"features/{ID}/links.yaml", yaml.safe_dump(links))
    target.trees["main"] = {"app.py": "print('hi')\n"}
    target.trees[FEATURE] = dict(target.trees["main"])
    return ctrl, target, seen


@pytest.fixture
def env(tmp_path, systems):
    ctrl, target, seen = systems
    config_root = tmp_path / "config"
    source = DirSource(config_root)
    doc = make_bundle("test", CONFIG)
    source.write(f"bundles/{doc['version']}.json", json.dumps(doc).encode())
    source.write("active.json", json.dumps(make_pointer(doc["version"], "tester", None)).encode())
    settings = Settings(
        env="test",
        config_source=str(config_root),
        store_root=tmp_path / "store",
        public_url=PUBLIC_URL,
        config_refresh_seconds=0,
        tokens={"SYSTEM_TOKEN_GITHUB": SYSTEM_TOKEN},
    )
    workspace = Workspace(target)
    platform = create_platform(
        settings, tokens=GoogleTokens(verify_id_token=verify_locally, clock=lambda: NOW), workspace=workspace
    )
    platform.store.load()
    with TestClient(create_app(platform=platform)) as client:
        yield client, ctrl, target, workspace, seen


def mcp(client, headers, method, params=None):
    params = dict(params or {})
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL,
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    headers = {**headers, "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
    headers["Mcp-Method"] = method
    if method == "tools/call":
        headers["Mcp-Name"] = params["name"]
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)


def call(client, tool, headers=None, /, **arguments):
    response = mcp(client, headers or run_headers(), "tools/call", {"name": tool, "arguments": arguments})
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    return json.loads(result["content"][0]["text"]), result.get("isError", False)


def listed(client, headers) -> set[str]:
    response = mcp(client, headers, "tools/list")
    assert response.status_code == 200, response.text
    return {t["name"] for t in response.json()["result"]["tools"]}


def test_every_tool_of_the_system_surfaces_is_served_here():
    groups = yaml.safe_load((Path(__file__).resolve().parents[3] / "config/tool_groups.yaml").read_text("utf-8"))
    surfaces = yaml.safe_load((Path(__file__).resolve().parents[3] / "config/surfaces.yaml").read_text("utf-8"))
    on_system = {g for s in surfaces["surfaces"].values() if s.get("system") for g in s["tool_groups"]}
    configured = {t for g in on_system for t in groups["tool_groups"][g]["tools"]}
    assert configured == set(TOOLS)


@pytest.mark.parametrize(
    ("change", "status", "reason"),
    [
        (lambda h: {}, 401, "no_token"),
        (lambda h: {**h, "Authorization": f"Bearer {caller_token(AGENT_ACCOUNT)}"}, 401, "not_a_system_caller"),
        (
            lambda h: {**h, "X-SDLC-User-Id": "1001", "X-SDLC-User-Email": "ada@example.test"},
            401,
            "user_on_system_surface",
        ),
        (lambda h: {**h, "Authorization": f"Bearer {caller_token(EVENT_ACCOUNT, 'https://x')}"}, 401, "wrong_audience"),
        (lambda h: {k: v for k, v in h.items() if k != "X-SDLC-Run-Id"}, 403, "no_run"),
        (lambda h: {**h, "X-SDLC-Team": "platform"}, 403, "not_a_system_team"),
        (lambda h: {**h, "X-SDLC-Subscription": "off"}, 403, "unknown_subscription"),
    ],
)
def test_only_the_system_identity_in_a_declared_run_gets_in(env, change, status, reason, caplog):
    client, *_ = env
    assert client.get("/healthz").json()["service"] == SERVICE
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        response = mcp(client, change(run_headers()), "tools/list")
    assert response.status_code == status
    assert any(getattr(r, "reason", None) == reason for r in caplog.records)


def test_a_run_sees_only_the_writes_its_subscription_declares(env):
    client, *_ = env
    reads = {"feature_status", "control_read_file", "repo_list", "repo_read_file", "repo_pull_requests"}
    assert listed(client, run_headers("ci_plan")) == reads | {"plan_open_pull_request", "pull_request_comment"}
    assert listed(client, run_headers("ci_implement")) == reads | {
        "implementation_open_pull_request",
        "pull_request_comment",
        "workspace_run",
    }
    result, error = call(
        client, "workspace_run", run_headers("ci_plan"), control_id=ID, repo="org/payments", changes=[]
    )
    assert error and result["error"] == "not_allowed"


def test_the_status_of_a_feature_with_its_targets_and_jira_keys(env):
    client, *_ = env
    status, error = call(client, "feature_status", None, control_id=ID, include_content=True)
    assert not error, status
    assert status["artifacts"]["design"]["approved"] and status["artifacts"]["design"]["merged_by"] == "grace"
    assert status["artifacts"]["design"]["content"].strip() == "# Design"
    assert status["target_repositories"] == ["org/payments"] and status["jira_keys"] == ["PAY-1", "PAY-2", "PAY-3"]
    assert status["plans"]["org/payments"]["published"] is False
    design, _ = call(client, "control_read_file", None, control_id=ID, file="design.md")
    assert design["meta"]["kind"] == "design"
    other, error = call(client, "repo_read_file", None, repo="org/elsewhere", path="a.py")
    assert error and other["error"] == "constraint_denied"


def test_a_plan_goes_into_the_feature_branch_once_and_is_recorded(env):
    client, ctrl, *_ = env
    plan, error = call(client, "plan_open_pull_request", None, control_id=ID, repo="payments", content="# Plan\n1. x")
    assert not error, plan
    pr = ctrl.prs[plan["pull_request"]["pull_request"]]
    assert (pr["head"], pr["base"]) == (f"sdlc/{ID}/plan-payments", FEATURE)
    assert pr["title"].startswith("PAY-1 PAY-2 PAY-3 ")
    text = ctrl.file(f"sdlc/{ID}/plan-payments", f"features/{ID}/plan-payments.md")
    assert "repo: org/payments" in text and "merged_by: grace" in text and "# Plan" in text
    links = yaml.safe_load(ctrl.file(FEATURE, f"features/{ID}/links.yaml"))
    assert links["writes"][-1]["action"] == "plan_pull_request" and links["writes"][-1]["run_id"] == "run-1"
    again, _ = call(client, "plan_open_pull_request", None, control_id=ID, repo="org/payments", content="# Plan")
    assert again["already_open"] is True and len(ctrl.prs) == 1
    status, _ = call(client, "feature_status", None, control_id=ID)
    assert [(p["kind"], p["branch"]) for p in status["open_pull_requests"]] == [
        ("plan-payments", f"sdlc/{ID}/plan-payments")
    ]


def test_no_plan_without_a_design_a_person_merged(env):
    client, ctrl, *_ = env
    ctrl.how[(FEATURE, f"features/{ID}/design.md")] = (5, "sdlc-bot")  # the machine user merged it
    result, error = call(client, "plan_open_pull_request", None, control_id=ID, repo="org/payments", content="# P")
    assert error and result["error"] == "not_approved" and "system account" in result["message"]
    assert not ctrl.prs


def test_a_merged_plan_is_built_in_the_workspace_and_opened_into_the_target_feature_branch(env):
    client, ctrl, target, workspace, _ = env
    implement = run_headers("ci_implement", run_id="run-2")
    result, error = call(
        client,
        "workspace_run",
        implement,
        control_id=ID,
        repo="org/payments",
        changes=[{"path": "a.py", "content": "x"}],
    )
    assert error and result["error"] == "not_approved"  # no plan merged yet
    plan, _ = call(client, "plan_open_pull_request", None, control_id=ID, repo="org/payments", content="# Plan")
    ctrl.merge(plan["pull_request"]["pull_request"], by="grace")

    early, error = call(client, "implementation_open_pull_request", implement, control_id=ID, repo="org/payments")
    assert error and early["error"] == "not_found"  # nothing pushed yet
    changes = [{"path": "refunds.py", "content": "def refund(): ...\n"}, {"path": "app.py", "delete": True}]
    built, error = call(
        client, "workspace_run", implement, control_id=ID, repo="org/payments", changes=changes, message="m"
    )
    assert not error, built
    assert built["ok"] and built["pushed"] and built["runs_left"] == 1 and built["built"] is True
    request = workspace.requests[0]
    assert request["branch"] == f"sdlc/{ID}/payments" and request["base"] == FEATURE
    assert request["clone_url"] == "https://github.com/org/payments.git" and request["commands"] == {
        "test": ["pytest -q"]
    }
    assert SYSTEM_TOKEN not in json.dumps(request)  # the job has its own copy of the token
    assert target.trees[f"sdlc/{ID}/payments"] == {"refunds.py": "def refund(): ...\n"}

    opened, error = call(client, "implementation_open_pull_request", implement, control_id=ID, repo="org/payments")
    assert not error, opened
    pr = target.prs[opened["pull_request"]["pull_request"]]
    assert (pr["head"], pr["base"]) == (f"sdlc/{ID}/payments", FEATURE) and pr["title"].startswith("PAY-1 ")
    assert "never merges" in pr["body"] and "https://gh/pr/" in pr["body"]
    again, _ = call(client, "implementation_open_pull_request", implement, control_id=ID, repo="org/payments")
    assert again["already_open"] is True and len(target.prs) == 1
    actions = [w["action"] for w in yaml.safe_load(ctrl.file(FEATURE, f"features/{ID}/links.yaml"))["writes"]]
    assert actions[-3:] == ["plan_pull_request", "workspace_push", "implementation_pull_request"]

    call(
        client,
        "workspace_run",
        implement,
        control_id=ID,
        repo="org/payments",
        changes=[{"path": "b.py", "content": "y"}],
    )
    over, error = call(
        client, "workspace_run", implement, control_id=ID, repo="org/payments", changes=[{"path": "c", "content": ""}]
    )
    assert error and over["error"] == "limit_reached"  # ci_implement allows 2 per run


@pytest.mark.parametrize("path", ["../x", ".git/config", "/abs", "a/../../b"])
def test_changes_stay_inside_the_repository(env, path):
    client, *_ = env
    result, error = call(
        client,
        "workspace_run",
        run_headers("ci_implement"),
        control_id=ID,
        repo="org/payments",
        changes=[{"path": path, "content": ""}],
    )
    assert error and result["error"] == "invalid_argument"


def test_comments_only_on_the_features_pull_requests(env):
    client, ctrl, *_ = env
    plan, _ = call(client, "plan_open_pull_request", None, control_id=ID, repo="org/payments", content="# Plan")
    number = plan["pull_request"]["pull_request"]
    done, error = call(
        client, "pull_request_comment", None, control_id=ID, repo="control", number=number, body="Blocked: x"
    )
    assert not error, done
    assert ctrl.comments[number][0].startswith("Blocked: x") and "run run-1" in ctrl.comments[number][0]
    on_design, error = call(client, "pull_request_comment", None, control_id=ID, repo="control", number=5, body="hi")
    assert not error  # the merged design pull request is the feature's
    other, error = call(client, "pull_request_comment", None, control_id=ID, repo="control", number=99, body="hi")
    assert error and other["error"] == "constraint_denied"


def test_calls_are_audited_with_the_event_and_no_argument_values(env, caplog):
    client, _, _, _, seen = env
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        call(client, "plan_open_pull_request", None, control_id=ID, repo="org/payments", content="# SECRET PLAN TEXT")
    record = next(r for r in caplog.records if getattr(r, "tool", None) == "plan_open_pull_request")
    assert (record.delivery_id, record.subscription, record.team, record.outcome) == (
        "d-123",
        "ci_plan",
        "payments",
        "ok",
    )
    assert record.caller == EVENT_ACCOUNT
    logged = " ".join(r.getMessage() + json.dumps(r.__dict__, default=str) for r in caplog.records)
    assert "SECRET PLAN TEXT" not in logged and SYSTEM_TOKEN not in logged
    assert all(r.headers["authorization"] == f"Bearer {SYSTEM_TOKEN}" for r in seen)  # the machine user's connection


def test_settings_fail_closed():
    with pytest.raises(SystemExit):
        Settings.from_env({"CONFIG_SOURCE": "x"})
    with pytest.raises(SystemExit):
        Settings.from_env(
            {"CONFIG_SOURCE": "x", "STORE_MOUNT_PATH": "/m", "SDLC_ENV": "dev", "WORKSPACE_MODE": "local"}
        )
    with pytest.raises(SystemExit):
        Settings.from_env(
            {"CONFIG_SOURCE": "x", "STORE_MOUNT_PATH": "/m", "WORKSPACE_MODE": "job", "WORKSPACE_JOB": "j"}
        )
    s = Settings.from_env({"CONFIG_SOURCE": "x", "STORE_MOUNT_PATH": "/m", "SYSTEM_TOKEN_GITHUB": "ghp_xyz"})
    assert s.system_token("github") == "ghp_xyz" and s.system_token("bitbucket_cloud") is None
    assert "ghp_xyz" not in repr(s)
