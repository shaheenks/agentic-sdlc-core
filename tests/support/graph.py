"""Deterministic graph extraction for tests (no model calls).

VocabularyExtractor finds known sample-corpus names in a chunk and emits the known relations
whose two ends both appear in it. Types are the first candidate the Source allows.
"""

import re

from sdlc_db.graph import ExtractedEntity, ExtractedRelation, Extraction

# name -> candidate types (first one the Source allows wins)
VOCABULARY: dict[str, tuple[str, ...]] = {
    "payments-api": ("service",),
    "refund-worker": ("service", "component"),
    "processor-gateway": ("service", "component"),
    "ledger-service": ("service", "component"),
    "reconciliation-job": ("process", "component"),
    "job-runner": ("service", "component"),
    "payments-db": ("data_store",),
    "ledger-db": ("data_store",),
    "jobstate-redis": ("data_store",),
    "payments-core": ("team",),
    "INC-2031": ("incident",),
    "INC-2044": ("incident",),
    "RefundAmountSpike": ("alert",),
    "LedgerPostingLag": ("alert",),
}

RELATIONS: tuple[tuple[str, str, str], ...] = (
    ("refund-worker", "runs_on", "job-runner"),
    ("reconciliation-job", "runs_on", "job-runner"),
    ("payments-api", "calls", "processor-gateway"),
    ("refund-worker", "calls", "processor-gateway"),
    ("payments-api", "stores_data_in", "payments-db"),
    ("ledger-service", "stores_data_in", "ledger-db"),
    ("payments-core", "owns", "refund-worker"),
    ("job-runner", "uses", "jobstate-redis"),
    ("INC-2031", "affects", "refund-worker"),
    ("INC-2044", "affects", "ledger-service"),
    ("RefundAmountSpike", "alerts", "refund-worker"),
)


def _mentions(name: str, text: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text, re.IGNORECASE) is not None


class VocabularyExtractor:
    model = "vocabulary-test"
    concurrency = 2

    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on  # raise for chunks whose location contains this (failure tests)
        self.calls = 0

    def extract(self, location, text, entity_types, relation_types) -> Extraction:
        self.calls += 1
        if self.fail_on and self.fail_on in location:
            raise RuntimeError("simulated model failure")
        entities = {}
        for name, candidates in VOCABULARY.items():
            allowed = [t for t in candidates if t in entity_types]
            if allowed and _mentions(name, text):
                entities[name] = ExtractedEntity(name, allowed[0], f"{name} (from {location})")
        relations = tuple(
            ExtractedRelation(s, r, t)
            for s, r, t in RELATIONS
            if s in entities and t in entities and r in relation_types
        )
        return Extraction(tuple(entities.values()), relations)
