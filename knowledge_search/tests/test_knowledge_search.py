"""Knowledge search (FR-KNOW-002, FR-AUTHZ-004, NFR-ARCH-004): declared callers only, a filter on every query,
and nothing from an unreadable source in results, rankings or graph answers."""

import asyncio

import pytest
from knowledge_search.index import Index
from sdlc_identity import GoogleTokens, Rejected
from sdlc_knowledge import DOCUMENT, Chunk, Edge, Entity, HashEmbedder, Store
from starlette.testclient import TestClient

from knowledge_search import SERVICE, Settings, create_app

URL = "https://knowledge-search.example.test"
MCP = "user-agent-mcp@proj.iam.gserviceaccount.com"
EMBEDDER = HashEmbedder(64)
TEXTS = {
    ("pay", "refunds.md"): "Refunds are posted to the ledger within one day.",
    ("pay", "ledger.md"): "The ledger keeps balances for every merchant account.",
    ("secret", "plans.md"): "Refunds will be outsourced next year; ledger migration planned.",
}


def store() -> Store:
    vectors = asyncio.run(EMBEDDER.embed(list(TEXTS.values()), DOCUMENT))
    chunks = [
        Chunk(f"{s}:{p}#L1", s, "internal", p, f"https://x/{p}", 1, 1, "", t, "h", tuple(v))
        for ((s, p), t), v in zip(TEXTS.items(), vectors, strict=True)
    ]
    entities = [
        Entity("pay:file:refunds.md", "pay", "internal", "file", "refunds.md", "refunds.md"),
        Entity("pay:concept:ledger", "pay", "internal", "concept", "Ledger"),
        Entity("secret:file:plans.md", "secret", "internal", "file", "plans.md", "plans.md"),
        Entity("secret:concept:ledger", "secret", "internal", "concept", "Ledger"),
    ]
    edges = [
        Edge("pay", "internal", "pay:file:refunds.md", "pay:concept:ledger", "mentions"),
        Edge("secret", "internal", "secret:file:plans.md", "pay:concept:ledger", "mentions"),
        Edge("secret", "internal", "secret:file:plans.md", "secret:concept:ledger", "mentions"),
    ]
    manifest = {
        "embedding": {"model": EMBEDDER.model, "dimensions": 64},
        "sources": {"pay": {"status": "ok"}, "secret": {"status": "ok"}},
    }
    return Store(manifest, chunks, entities, edges)


def jwt_like(name):
    return f"eyJ{name}.payload.signature"


def verify(token):
    token = token.split(".")[0].removeprefix("eyJ")
    if token == "mcp":
        return {"aud": URL, "email": MCP, "email_verified": True, "sub": "1", "exp": 4_000_000_000}
    if token == "other-aud":
        return {"aud": "https://elsewhere", "email": MCP, "email_verified": True, "sub": "1", "exp": 4_000_000_000}
    if token == "stranger":
        return {"aud": URL, "email": "x@proj.iam.gserviceaccount.com", "email_verified": True, "exp": 4_000_000_000}
    raise Rejected("invalid_token")


def client(**overrides) -> TestClient:
    settings = Settings("dev", "-", URL, frozenset({MCP}), "id_token")
    tokens = GoogleTokens(verify_id_token=verify)
    app = create_app(overrides.get("settings", settings), Index(store()), overrides.get("embedder", EMBEDDER), tokens)
    return TestClient(app, headers={"Authorization": f"Bearer {jwt_like('mcp')}"})


@pytest.fixture
def c():
    return client()


def tokens_header(name):
    return {"Authorization": f"Bearer {jwt_like(name)}"}


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
def test_results_come_only_from_readable_sources(c, mode):
    response = c.post("/search", json={"query": "refunds ledger", "mode": mode, "filter": {"sources": ["pay"]}})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results and {r["source_id"] for r in results} == {"pay"}
    assert results[0]["link"].startswith("https://x/") and results[0]["lines"] == [1, 1]


def test_an_empty_filter_reads_nothing(c):
    response = c.post("/search", json={"query": "refunds", "filter": {"sources": []}})
    assert response.status_code == 200 and response.json()["results"] == []


@pytest.mark.parametrize(
    "body", [{"query": "refunds"}, {"query": "refunds", "filter": {}}, {"query": "x", "filter": {"sources": "pay"}}]
)
def test_a_query_without_a_filter_is_refused(c, body):
    response = c.post("/search", json=body)
    assert response.status_code == 400 and response.json()["error"] == "filter_required"
    assert (
        c.post("/graph", json={k: v for k, v in body.items() if k != "query"} | {"name": "ledger"}).status_code == 400
    )


def test_keyword_ranking_ignores_unreadable_records():
    index = Index(store())
    alone = Index(Store(store().manifest, [c for c in store().chunks if c.source_id == "pay"], [], []))
    assert [(h.chunk.id, h.score) for h in index.search("keyword", ["pay"], 5, "refunds ledger", None)] == [
        (h.chunk.id, h.score) for h in alone.search("keyword", ["pay"], 5, "refunds ledger", None)
    ]


def test_graph_stays_inside_readable_sources(c):
    body = {"name": "ledger", "depth": 2, "filter": {"sources": ["pay"]}}
    result = c.post("/graph", json=body).json()
    ids = {n["id"] for n in result["nodes"]}
    assert ids == {"pay:concept:ledger", "pay:file:refunds.md"}
    assert all(not e["from"].startswith("secret") for e in result["edges"])
    hidden = c.post("/graph", json={"entity": "secret:concept:ledger", "filter": {"sources": ["pay"]}}).json()
    assert hidden["nodes"] == []


@pytest.mark.parametrize(
    ("token", "status", "reason"),
    [("other-aud", 401, "wrong_audience"), ("stranger", 403, "undeclared_caller"), ("garbage", 401, "invalid_token")],
)
def test_only_declared_callers_with_this_audience(c, token, status, reason):
    body = {"query": "refunds", "filter": {"sources": ["pay"]}}
    response = c.post("/search", json=body, headers=tokens_header(token))
    assert response.status_code == status and response.json()["message"] == reason


def test_no_token_is_refused(c):
    response = c.post("/search", json={"query": "x", "filter": {"sources": ["pay"]}}, headers={"Authorization": ""})
    assert response.status_code == 401


def test_a_different_embedding_model_refuses_vector_queries_but_not_keyword():
    other = HashEmbedder(64)
    other.model = "gemini-embedding-001"
    c = client(embedder=other)
    body = {"query": "refunds", "filter": {"sources": ["pay"]}}
    assert c.post("/search", json=body | {"mode": "hybrid"}).json()["error"] == "embedding_model_mismatch"
    assert c.post("/search", json=body | {"mode": "keyword"}).status_code == 200


def test_status_shows_only_readable_sources(c):
    response = c.post("/status", json={"filter": {"sources": ["pay"]}})
    assert set(response.json()["sources"]) == {"pay"}


def test_invalid_arguments(c):
    f = {"filter": {"sources": ["pay"]}}
    assert c.post("/search", json=f | {"query": ""}).status_code == 400
    assert c.post("/search", json=f | {"query": "x", "mode": "magic"}).status_code == 400
    assert c.post("/search", json=f | {"query": "x", "limit": 500}).status_code == 400
    assert c.post("/graph", json=f).status_code == 400


def test_settings_fail_closed():
    with pytest.raises(SystemExit):
        Settings.from_env({"SDLC_ENV": "dev", "CALLER_AUTH": "none"})
    with pytest.raises(SystemExit):
        Settings.from_env({"SDLC_ENV": "dev"})
    assert Settings.from_env({"CALLER_AUTH": "none"}).caller_auth == "none"


def test_healthz_without_a_store():
    response = TestClient(create_app()).get("/healthz")
    assert response.json()["service"] == SERVICE


def test_graph_finds_an_entity_by_its_title():
    s = store()
    s.entities.append(Entity("pay:file:svc.md", "pay", "internal", "file", "svc.md", "svc.md", "Refund Service"))
    assert Index(s).graph(["pay"], name="refund service")["seeds"] == ["pay:file:svc.md"]
