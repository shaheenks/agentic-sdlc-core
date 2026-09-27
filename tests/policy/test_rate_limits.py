"""H8: per-user tool call rates from config (platform baseline + team limits)."""

import json

import pytest
import yaml
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sdlc_config import ConfigError, load_snapshot, resolve
from sdlc_policy import RateLimiter

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, TEST_ENV


def edit_yaml(path, mutate):
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# --- resolution ---------------------------------------------------------------------------------


def test_baseline_and_team_tool_limit(config_dir):
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    dev = resolve(snap, ["eng-all", "payments-devs"])
    assert dev.rate_limits["*"] == (120, "platform.yaml#defaults/rate_limit")
    assert dev.rate_limits["graph_query"] == (
        30,
        "teams/payments.yaml#policy/limits/tools/graph_query/calls_per_minute",
    )
    platform = resolve(snap, ["eng-all", "platform-devs"])
    assert "graph_query" not in platform.rate_limits


def test_most_generous_team_wins_and_team_overall_replaces_baseline(config_dir):
    edit_yaml(
        config_dir / "teams/platform.yaml",
        lambda d: d.setdefault("policy", {}).update(
            limits={"calls_per_minute": 40, "tools": {"graph_query": {"calls_per_minute": 90}}}
        ),
    )
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    both = resolve(snap, ["eng-all", "payments-devs", "platform-devs"])
    assert both.rate_limits["graph_query"][0] == 90  # platform's 90 beats payments' 30
    assert both.rate_limits["*"] == (40, "teams/platform.yaml#policy/limits/calls_per_minute")
    assert both.explain()["rate_limits"]["graph_query"]["calls_per_minute"] == 90


def test_unknown_tool_in_limits_fails(config_dir):
    edit_yaml(
        config_dir / "teams/payments.yaml",
        lambda d: d["policy"]["limits"]["tools"].update(teleport={"calls_per_minute": 1}),
    )
    with pytest.raises(ConfigError, match="policy/limits/tools: unknown tool 'teleport'"):
        load_snapshot(config_dir, "local", TEST_ENV)


# --- limiter ------------------------------------------------------------------------------------


@pytest.fixture
def policy(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["defaults"].update(rate_limit={"calls_per_minute": 3}),
    )
    edit_yaml(
        config_dir / "teams/payments.yaml",
        lambda d: d["policy"]["limits"]["tools"].update(graph_query={"calls_per_minute": 2}),
    )
    return resolve(load_snapshot(config_dir, "local", TEST_ENV), ["eng-all", "payments-devs"])


def test_limit_window_and_retry_after(policy):
    clock = Clock()
    limiter = RateLimiter(clock)
    assert [limiter.check(policy, "u1", "whoami") for _ in range(3)] == [None, None, None]
    denied = limiter.check(policy, "u1", "whoami")
    assert denied is not None and not denied.allowed
    assert "3 calls per minute for all tools; retry in 60 s" in denied.reason
    assert denied.matched_rule == "platform.yaml#defaults/rate_limit"
    clock.now += 30
    assert "retry in 30 s" in limiter.check(policy, "u1", "whoami").reason
    clock.now += 30.5  # the first calls leave the window
    assert limiter.check(policy, "u1", "whoami") is None


def test_tool_limit_applies_on_top_and_refusals_do_not_count(policy):
    limiter = RateLimiter(Clock())
    assert limiter.check(policy, "u1", "graph_query") is None
    assert limiter.check(policy, "u1", "graph_query") is None
    third = limiter.check(policy, "u1", "graph_query")
    assert "2 calls per minute for 'graph_query'" in third.reason
    assert third.matched_rule.endswith("tools/graph_query/calls_per_minute")
    # 2 counted overall (the refused call was not), so one more call of another tool fits
    assert limiter.check(policy, "u1", "whoami") is None
    assert limiter.check(policy, "u1", "whoami") is not None


def test_users_are_counted_separately_and_idle_windows_are_pruned(policy):
    clock = Clock()
    limiter = RateLimiter(clock)
    for _ in range(3):
        limiter.check(policy, "u1", "whoami")
    assert limiter.check(policy, "u1", "whoami") is not None
    assert limiter.check(policy, "u2", "whoami") is None
    clock.now += 61
    limiter.prune()
    assert limiter._calls == {}


# --- through the MCP server ---------------------------------------------------------------------


@pytest.fixture
def low_limit(config_dir, store):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["defaults"].update(rate_limit={"calls_per_minute": 2}),
    )
    assert store.reload()


async def test_mcp_refuses_and_audits_over_limit_calls(low_limit, base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    token = entra.token(
        oid="cccccccc-0000-0000-0000-00000000000c", groups=[G_ENG_ALL, G_PAYMENTS_DEVS]
    )
    async with Client(f"{base_url}/mcp", auth=token) as c:
        await c.call_tool("ping", {})
        await c.call_tool("ping", {})
        with pytest.raises(ToolError, match="rate limit: 2 calls per minute for all tools"):
            await c.call_tool("ping", {})
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    calls = [r for r in records if r["event"] == "tool_call"]
    assert [r["outcome"] for r in calls] == ["ok", "ok", "rate_limited"]
    assert calls[-1]["decision"] == "deny"
    assert calls[-1]["matched_rule"] == "platform.yaml#defaults/rate_limit"
