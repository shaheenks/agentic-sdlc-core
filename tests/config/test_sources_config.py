"""Stage 5a: Source kind, knowledge settings and data resolution (allowed sources + ceiling)."""

import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot, resolve

from tests.support.entra import TEST_ENV


def load(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def edit_yaml(path, mutate):
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_sources_load(config_dir):
    snap = load(config_dir)
    assert set(snap.sources) == {
        "payments-code",
        "platform-infra",
        "eng-standards",
        "payments-incidents",
        "sdlc-platform",
        "webapp-code",
    }
    platform = snap.sources["sdlc-platform"]  # GitHub, tracking main (public: no credentials)
    assert (platform.type, platform.provider, platform.ref) == ("git", "github", "main")
    assert platform.location == "https://github.com/shaheenks/agentic-sdlc-core.git"
    assert platform.credentials is None and platform.access_teams == {"sdlc-platform"}
    incidents = snap.sources["payments-incidents"]
    assert incidents.classification == "confidential" and incidents.classification_rank == 2
    assert incidents.access_teams == {"payments"} and incidents.access_roles == {"admin"}
    assert snap.sources["eng-standards"].access_everyone
    assert snap.sources["platform-infra"].access_groups == {"infra-readers"}
    assert snap.platform.embedding_model == "gemini-embedding-2"
    assert snap.platform.embedding_dimensions == 768


@pytest.mark.parametrize(
    ("file", "mutate", "message"),
    [
        (
            "sources/payments-code.yaml",
            lambda d: d["spec"].update(classification="top-secret"),
            "unknown level 'top-secret'",
        ),
        (
            "sources/payments-code.yaml",
            lambda d: d["access"].update(teams=["marketing"]),
            "unknown team 'marketing'",
        ),
        (
            "sources/payments-code.yaml",
            lambda d: d["access"].update(roles=["auditor"]),
            "unknown role 'auditor'",
        ),
        (
            "sources/eng-standards.yaml",
            lambda d: d["access"].update(groups=["ghosts"]),
            "unknown group alias 'ghosts'",
        ),
        (
            "sources/eng-standards.yaml",
            lambda d: d["access"].update(everyone=False),
            "access/everyone",
        ),
        (
            "sources/payments-code.yaml",
            lambda d: d["metadata"].update(id="payments"),
            "must match the file name",
        ),
        (
            "sources/payments-code.yaml",
            lambda d: d["metadata"].update(owner_team="finance"),
            "unknown team 'finance'",
        ),
        ("sources/payments-code.yaml", lambda d: d.update(access={}), "access"),
        ("sources/payments-code.yaml", lambda d: d["spec"].update(type="s3_bucket"), "spec/type"),
        (
            "platform.yaml",
            lambda d: d["knowledge"]["embedding"].update(dimensions=1536),
            "knowledge/embedding/dimensions",
        ),
    ],
)
def test_bad_source_config_fails(config_dir, file, mutate, message):
    edit_yaml(config_dir / file, mutate)
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert message in str(exc.value), exc.value


@pytest.mark.parametrize(
    ("groups", "sources", "ceiling"),
    [
        ([], {"eng-standards"}, "public"),  # everyone: true
        (["eng-all", "infra-readers"], {"eng-standards", "platform-infra"}, "internal"),
        (["eng-all"], {"eng-standards"}, "internal"),
        (
            ["eng-all", "payments-devs"],
            {"eng-standards", "payments-code", "payments-incidents"},
            "internal",
        ),
        (
            ["eng-all", "payments-leads"],
            {"eng-standards", "payments-code", "payments-incidents"},
            "confidential",
        ),
        (
            ["eng-all", "platform-devs"],
            {"eng-standards", "platform-infra", "sdlc-platform"},
            "internal",
        ),
        (
            ["platform-admins"],
            {
                "eng-standards",
                "payments-code",
                "payments-incidents",
                "platform-infra",
                "sdlc-platform",
                "webapp-code",
            },
            "restricted",
        ),
    ],
)
def test_data_resolution(config_dir, groups, sources, ceiling):
    policy = resolve(load(config_dir), groups)
    assert set(policy.data_sources) == sources
    assert policy.max_classification == ceiling


def test_granted_source_above_ceiling_is_still_unreadable_by_rank(config_dir):
    snap = load(config_dir)
    dev = resolve(snap, ["eng-all", "payments-devs"])
    # granted by team access, but its classification is above the developer's ceiling
    assert "payments-incidents" in dev.data_sources
    assert "payments-incidents" not in dev.readable_sources  # granted, but above the ceiling
    assert set(dev.readable_sources) == {"eng-standards", "payments-code"}
    assert dev.source_classification["payments-incidents"] == 2
    assert snap.sources["payments-incidents"].classification_rank > dev.max_classification_rank


def test_data_grants_name_their_rule(config_dir):
    policy = resolve(load(config_dir), ["eng-all", "payments-devs"])
    assert policy.data_sources["payments-code"] == (
        "team:payments <- sources/payments-code.yaml#access/teams",
    )
    assert policy.data_sources["eng-standards"] == (
        "everyone <- sources/eng-standards.yaml#access/everyone",
    )
    assert policy.explain()["data"]["max_classification"] == "internal"


def test_source_group_grants_data_without_team(config_dir):
    """A source's own Entra group grants that source only; no team, no developer tools."""
    policy = resolve(load(config_dir), ["eng-all", "infra-readers"])
    assert policy.teams == {}
    assert policy.data_sources["platform-infra"] == (
        "group:infra-readers <- sources/platform-infra.yaml#access/groups",
    )
    assert set(policy.readable_sources) == {"eng-standards", "platform-infra"}
    assert policy.allows("graph_query") and not policy.allows("review_code")


def test_source_group_alone_has_no_knowledge_tool(config_dir):
    """Without eng-all (viewer) the user has the data grant but no tool to read it."""
    policy = resolve(load(config_dir), ["infra-readers"])
    assert "platform-infra" in policy.data_sources
    assert not policy.allows("graph_query") and not policy.allows("search_knowledge")
    data = policy.explain()["data"]
    assert data["tools"] == [] and data["readable"] == []
    assert "no knowledge tool" in data["note"]


def test_explain_signed_in_only_lists_everyone_source_as_unreadable(config_dir):
    """No sdlc groups: eng-standards (`everyone: true`, public) is granted, but signed-in has no
    knowledge tool, so whoami(explain) must not call it readable."""
    policy = resolve(load(config_dir), [])
    assert set(policy.roles) == {"signed-in"}
    assert "eng-standards" in policy.data_sources
    data = policy.explain()["data"]
    assert data["readable"] == [] and data["tools"] == []
    assert "eng-standards" in data["note"]


def test_explain_viewer_lists_readable_sources_and_tools(config_dir):
    data = resolve(load(config_dir), ["eng-all", "payments-devs"]).explain()["data"]
    assert data["tools"] == ["graph_query", "search_knowledge"]
    assert set(data["readable"]) == {"eng-standards", "payments-code"}
    assert "note" not in data


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["spec"].pop("ref"), "spec/ref: required for git sources"),
        (
            lambda d: d["spec"].update(location="git@github.com:org/repo.git"),
            "only local paths and https URLs",
        ),
    ],
)
def test_git_source_checks(config_dir, mutate, message):
    edit_yaml(config_dir / "sources/sdlc-platform.yaml", mutate)
    with pytest.raises(ConfigError, match=message):
        load(config_dir)


def test_ref_only_for_git_sources(config_dir):
    edit_yaml(config_dir / "sources/eng-standards.yaml", lambda d: d["spec"].update(ref="main"))
    with pytest.raises(ConfigError, match="only git sources have a ref"):
        load(config_dir)
