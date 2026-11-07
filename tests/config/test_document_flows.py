"""version-03 P10 G7: document flow defaults (platform.yaml flows.document + team addons.flows)."""

import pytest
import yaml
from sdlc_config import ConfigError, document_flow, load_snapshot, resolve

from tests.support.entra import TEST_ENV


def load(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def edit_yaml(path, mutate):
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def payments_flow(mutate):
    def apply(t):
        mutate(t["addons"]["flows"]["document"])

    return apply


def test_platform_only_without_a_team(config_dir):
    snap = load(config_dir)
    policy = resolve(snap, ["eng-all", "payments-devs"])
    flow = document_flow(snap, policy, None)
    assert flow["team"] is None and flow["types"] == {}
    assert flow["lenses"][0] == "lens-zoom-out" and flow["max_lenses"] == 6


def test_the_locked_team_adds_its_types(config_dir):
    snap = load(config_dir)
    policy = resolve(snap, ["eng-all", "payments-devs"])
    flow = document_flow(snap, policy, "payments")
    assert flow["types"]["design"] == {
        "template": "payments-design-template",
        "lenses": ["lens-design-critic", "lens-implementation-readiness", "lens-zoom-out"],
        "required_lenses": ["payments-pci-lens"],
    }
    assert flow["types"]["user-story"]["brief"] == "payments-story-questions"
    # a team the caller is not in gives platform defaults only
    other = resolve(snap, ["eng-all", "platform-devs"])
    assert document_flow(snap, other, "payments")["types"] == {}


def test_team_caps_only_lower(config_dir):
    edit_yaml(
        config_dir / "teams/payments.yaml",
        payments_flow(lambda f: f.update(max_lenses=3, max_rereviews=0)),
    )
    snap = load(config_dir)
    flow = document_flow(snap, resolve(snap, ["eng-all", "payments-devs"]), "payments")
    assert (flow["max_lenses"], flow["max_rereviews"], flow["max_llm_calls_per_reviewer"]) == (
        3,
        0,
        8,
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda f: f.update(max_lenses=9), "max_lenses: 9 is above the platform value 6"),
        (
            lambda f: f["types"]["design"].update(template="lens-zoom-out"),
            "skill 'lens-zoom-out' is not tagged 'doc-template'",
        ),
        (
            lambda f: f["types"]["design"].update(required_lenses=["infra-change-review"]),
            "unknown skill 'infra-change-review' (must be a global skill or a payments add-on)",
        ),
        (lambda f: f.update(lenses=["no-such-lens"]), "unknown skill 'no-such-lens'"),
        (lambda f: f["types"]["design"].update(colour="red"), "colour"),  # unknown key
    ],
)
def test_bad_team_flows_fail(config_dir, mutate, message):
    edit_yaml(config_dir / "teams/payments.yaml", payments_flow(mutate))
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert message in str(exc.value), exc.value


def test_platform_lenses_are_global_lenses(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda p: p["flows"]["document"].update(lenses=["payments-pci-lens"]),
    )
    with pytest.raises(ConfigError, match="must be a global skill"):
        load(config_dir)
