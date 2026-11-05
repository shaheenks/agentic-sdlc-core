"""version-02 N10: direct members in env/<env>/users.yaml (matched by oid, never by email)."""

import json

import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot, resolve
from sdlc_config.cli import main as cli_main
from sdlc_config.users import sync

from tests.support.config import DIRECT_DEV_OID
from tests.support.entra import TEST_ENV


def load(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def users_file(config_dir):
    return config_dir / "env/local/users.yaml"


def edit_users(config_dir, mutate):
    path = users_file(config_dir)
    doc = yaml.safe_load(path.read_text())
    mutate(doc["users"])
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_users_load_and_match_by_oid_only(config_dir):
    users = load(config_dir).users
    assert users.alias_for(DIRECT_DEV_OID.upper()) == "direct-dev"  # case-insensitive oid
    assert users.alias_for("direct.dev@example.com") is None  # an email never matches
    assert users.alias_for(None) is None
    assert users.pending == ("pending",)


def test_users_file_is_optional(config_dir):
    users_file(config_dir).unlink()
    snap = load(config_dir)
    assert snap.users.alias_by_oid == {} and snap.users.pending == ()


def test_committed_example_is_valid(config_dir):
    example = config_dir / "env/local/users.yaml.example"
    users_file(config_dir).write_text(example.read_text())
    users = load(config_dir).users
    assert set(users.email_by_alias) == {"paul", "ana", "ben"}
    assert set(users.pending) == {"ana", "ben"}


def test_users_file_path_override(config_dir, tmp_path):
    """GCP: users.yaml is a Secret Manager mount outside config/ (SDLC_USERS_FILE)."""
    mounted = tmp_path / "users-mount" / "users.yaml"
    mounted.parent.mkdir()
    users_file(config_dir).rename(mounted)
    assert load(config_dir).users.alias_by_oid == {}  # not in config/env/local any more
    snap = load_snapshot(config_dir, "local", {**TEST_ENV, "SDLC_USERS_FILE": str(mounted)})
    assert snap.users.alias_for(DIRECT_DEV_OID) == "direct-dev"
    assert "config/env/local/users.yaml" in snap.files  # named by its usual path
    rules = snap.teams["payments"].membership[-1].rule
    assert rules == "env/local/users.yaml#users/direct-dev/teams/payments"
    with pytest.raises(ConfigError, match="direct-dev"):
        mounted.write_text(mounted.read_text().replace("payments", "marketing"))
        load_snapshot(config_dir, "local", {**TEST_ENV, "SDLC_USERS_FILE": str(mounted)})


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda u: u["direct-dev"].update(teams={"marketing": ["developer"]}), "unknown team"),
        (lambda u: u["direct-dev"].update(teams={"payments": ["god"]}), "unknown role 'god'"),
        (lambda u: u["direct-viewer"].update(roles=["auditor"]), "unknown role 'auditor'"),
        (
            lambda u: u["direct-viewer"].update(oid=u["direct-dev"]["oid"].upper()),
            "also used by 'direct-dev'",
        ),
        (
            lambda u: u["direct-viewer"].update(email="Direct.Dev@example.com"),
            "also used by 'direct-dev'",
        ),
        (lambda u: u["direct-dev"].update(oid="not-a-guid"), "users/direct-dev/oid"),
        (lambda u: u["direct-dev"].update(email="no-at-sign"), "users/direct-dev/email"),
        (lambda u: u.update({"Bad_Alias": {"email": "x@example.com"}}), "users"),
        (lambda u: u["direct-dev"].update(groups=["eng-all"]), "groups"),
    ],
)
def test_bad_users_fail(config_dir, mutate, message):
    edit_users(config_dir, mutate)
    with pytest.raises(ConfigError, match=message):
        load(config_dir)


def test_direct_member_gets_team_roles_limits_skills_and_sources(config_dir):
    snap = load(config_dir)
    policy = resolve(snap, [], (), "direct-dev")
    assert policy.user == "direct-dev"
    assert policy.teams == {"payments": ("env/local/users.yaml#users/direct-dev/teams/payments",)}
    assert policy.roles["developer"] == ("env/local/users.yaml#users/direct-dev/teams/payments",)
    assert policy.tools["review_code"].constraints == {"repo": {"payments-api", "payments-ui"}}
    assert policy.sees_skill("pci-checklist")
    assert "payments-code" in policy.readable_sources
    assert policy.explain()["user"] == "direct-dev"


def test_direct_membership_unions_with_groups(config_dir):
    policy = resolve(load(config_dir), ["eng-all", "platform-devs"], (), "direct-dev")
    assert set(policy.teams) == {"payments", "sdlc-platform"}
    assert policy.tools["review_code"].constraints["repo"] >= {"payments-api", "agentic-sdlc-core"}


def test_global_role_binding(config_dir):
    policy = resolve(load(config_dir), [], (), "direct-viewer")
    assert policy.teams == {}
    assert policy.roles["viewer"] == ("env/local/users.yaml#users/direct-viewer/roles",)


def test_pending_user_grants_nothing(config_dir):
    snap = load(config_dir)
    assert resolve(snap, [], (), "pending").roles.keys() == {"signed-in"}
    assert all(m.ref.value != "pending" for t in snap.teams.values() for m in t.membership)


def test_team_may_have_only_direct_members(config_dir):
    path = config_dir / "teams/payments.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["membership"] = []
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    snap = load(config_dir)
    assert set(resolve(snap, ["payments-devs"]).teams) == set()
    assert set(resolve(snap, [], (), "direct-dev").teams) == {"payments"}


def test_validate_warns_about_pending_users(config_dir, capsys):
    assert cli_main(["validate", "--config-dir", str(config_dir), "--dummy-env"]) == 0
    out = capsys.readouterr().out
    assert "users=2" in out and "users without an oid get no access: pending" in out


def test_explain_user(config_dir, capsys):
    args = ["explain", "--config-dir", str(config_dir), "--dummy-env", "--user", "direct-dev"]
    assert cli_main([*args, "--json"]) == 0
    view = json.loads(capsys.readouterr().out)
    assert view["user"] == "direct-dev" and set(view["teams"]) == {"payments"}
    assert (
        cli_main(["explain", "--config-dir", str(config_dir), "--dummy-env", "--user", "ghost"])
        == 0
    )
    assert "user:ghost" in capsys.readouterr().out


# --- users sync (Azure CLI stubbed; no network) --------------------------------------------------


class FakeAz:
    def __init__(self, directory: dict[str, dict]):
        self.directory, self.calls = directory, []

    def __call__(self, args: list[str]) -> tuple[int, str]:
        self.calls.append(args)
        if args[:2] == ["account", "show"]:
            return 0, "admin@tenant.test\n"
        assert args[:3] == ["ad", "user", "show"]  # read-only lookups only
        user = self.directory.get(args[4].lower())
        return (0, json.dumps(user)) if user else (3, "")


PENDING_USER = {
    "id": "bbbbbbbb-0000-0000-0000-000000000003",
    "userPrincipalName": "pending@example.com",
}


def test_sync_fills_missing_oids_only_with_write(config_dir):
    az = FakeAz({"pending@example.com": PENDING_USER})
    lines, problems = sync(users_file(config_dir), az)
    assert problems == 0 and "az signed in as: admin@tenant.test" in lines[0]
    assert "pending" in load(config_dir).users.pending  # not saved without --write
    lines, problems = sync(users_file(config_dir), az, write=True)
    users = load(config_dir).users
    assert users.pending == () and users.alias_for(PENDING_USER["id"]) == "pending"
    assert all(c[:3] in (["account", "show", "--query"], ["ad", "user", "show"]) for c in az.calls)
    # one flow-style (JSON-like) line per user, header comments kept
    text = users_file(config_dir).read_text(encoding="utf-8")
    entries = [line for line in text.splitlines() if line.startswith("  ") and ": {" in line]
    assert len(entries) == len(users.email_by_alias)
    assert any(line.startswith("  pending: {email: ") for line in entries)


def test_sync_reports_unknown_email(config_dir):
    lines, problems = sync(users_file(config_dir), FakeAz({}))
    assert problems == 1 and any("NOT FOUND" in line for line in lines)


def test_sync_check_detects_drift(config_dir):
    az = FakeAz(
        {
            DIRECT_DEV_OID: {"id": DIRECT_DEV_OID, "userPrincipalName": "someone.else@example.com"},
            "pending@example.com": PENDING_USER,
        }
    )
    lines, problems = sync(users_file(config_dir), az, check=True)
    assert problems == 2  # direct-dev renamed, direct-viewer gone
    assert any("direct-dev: sign-in name is now someone.else@example.com" in x for x in lines)
    assert any("direct-viewer: oid no longer exists" in x for x in lines)
