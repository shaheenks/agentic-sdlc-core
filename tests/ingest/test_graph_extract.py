"""Stage 6: graph config, entity keys and validation of (untrusted) extraction output."""

import pytest
from sdlc_config import ConfigError, load_snapshot
from sdlc_db.graph import ExtractedEntity, ExtractedRelation, Extraction, entity_key
from sdlc_ingest.extract import cache_key

from tests.config.test_sources_config import edit_yaml
from tests.support.entra import TEST_ENV
from tests.support.graph import VocabularyExtractor


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("refund-worker", "refund-worker"),
        ("Refund Worker", "refund-worker"),
        ("`refund_worker`", "refund-worker"),
        ("RefundAmountSpike", "refund-amount-spike"),
        ("INC-2031", "inc-2031"),
        ("  ", ""),
    ],
)
def test_entity_key(name, key):
    assert entity_key(name) == key


def test_cleaned_keeps_only_allowed_and_connected():
    raw = Extraction(
        (
            ExtractedEntity("refund-worker", "service", "sends refunds"),
            ExtractedEntity("Refund Worker", "service", "duplicate by key"),
            ExtractedEntity("job-runner", "component"),
            ExtractedEntity("Kubernetes", "platform"),  # type not allowed
            ExtractedEntity("", "service"),  # no name
        ),
        (
            ExtractedRelation("refund-worker", "runs_on", "job-runner"),
            ExtractedRelation("Refund Worker", "runs_on", "job-runner"),  # same edge by key
            ExtractedRelation("refund-worker", "runs_on", "Kubernetes"),  # dangling
            ExtractedRelation("refund-worker", "hacks", "job-runner"),  # relation not allowed
            ExtractedRelation("refund-worker", "calls", "refund-worker"),  # self edge
        ),
    )
    clean = raw.cleaned(["service", "component"], ["runs_on", "calls"])
    assert [(e.name, e.type) for e in clean.entities] == [
        ("refund-worker", "service"),
        ("job-runner", "component"),
    ]
    assert [(r.source, r.relation, r.target) for r in clean.relations] == [
        ("refund-worker", "runs_on", "job-runner")
    ]


def test_cleaned_caps_entities_and_lengths():
    raw = Extraction(tuple(ExtractedEntity(f"svc-{i}", "service", "x" * 900) for i in range(40)))
    clean = raw.cleaned(["service"], ["calls"], max_entities=25)
    assert len(clean.entities) == 25 and all(len(e.description) == 500 for e in clean.entities)


def test_extraction_json_round_trip():
    e = Extraction(
        (ExtractedEntity("a-svc", "service", "d"), ExtractedEntity("b-svc", "service")),
        (ExtractedRelation("a-svc", "calls", "b-svc"),),
    )
    assert Extraction.from_json(e.to_json()) == e


def test_vocabulary_extractor_respects_source_types():
    ex = VocabularyExtractor().extract(
        "x", "refund-worker runs on job-runner (INC-2031)", ["service"], ["runs_on"]
    )
    assert {e.name for e in ex.entities} == {"refund-worker", "job-runner"}
    assert [(r.source, r.target) for r in ex.relations] == [("refund-worker", "job-runner")]


# --- config -------------------------------------------------------------------------------------


def test_graph_config_loads(config_dir):
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    assert snap.platform.graph_model and snap.platform.graph_thinking_level == "low"
    code, incidents = snap.sources["payments-code"], snap.sources["payments-incidents"]
    assert code.graph_enabled and "service" in code.entity_types
    assert code.relation_types == snap.platform.graph_relation_types  # platform default
    assert set(incidents.relation_types) < set(snap.platform.graph_relation_types)
    assert all(s.graph_enabled for s in snap.sources.values())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["spec"]["ingest"]["graph"].pop("entity_types"), "entity_types: required"),
        (
            lambda d: d["spec"]["ingest"]["graph"].update(relation_types=["teleports_to"]),
            "not in platform.yaml",
        ),
        (
            lambda d: d["spec"]["ingest"]["graph"].update(entity_types=["Bad Type"]),
            "does not match",
        ),
    ],
)
def test_bad_graph_config_fails(config_dir, mutate, message):
    edit_yaml(config_dir / "sources/payments-code.yaml", mutate)
    with pytest.raises(ConfigError, match=message):
        load_snapshot(config_dir, "local", TEST_ENV)


def test_graph_needs_platform_graph_settings(config_dir):
    edit_yaml(config_dir / "platform.yaml", lambda d: d["knowledge"].pop("graph"))
    with pytest.raises(ConfigError, match="platform.yaml has no knowledge.graph"):
        load_snapshot(config_dir, "local", TEST_ENV)


def test_cache_key_changes_with_types_and_text(config_dir):
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    code, infra = snap.sources["payments-code"], snap.sources["platform-infra"]
    base = cache_key("m", code, "text")
    assert base == cache_key("m", code, "text")
    assert base != cache_key("m", code, "other text")
    assert base != cache_key("m", infra, "text")  # different entity types
    assert base != cache_key("other-model", code, "text")
