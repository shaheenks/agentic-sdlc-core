"""version-03 P5: artifact limits and content stores (no database, no network)."""

import json
import uuid

import httpx
import pytest
from sdlc_artifacts import (
    MAX_BYTES,
    ArtifactInputError,
    ArtifactStoreError,
    FileArtifactStore,
    GcsArtifactStore,
    object_key,
    store_from_env,
    validate,
)

OID = "11111111-2222-3333-4444-555555555555"


def test_validate_accepts_markdown():
    assert validate("design notes.md", "# Hi", "text/markdown") == b"# Hi"


@pytest.mark.parametrize(
    ("name", "content", "media_type", "message"),
    [
        ("a.md", "x", "text/html", "media_type must be one of"),
        ("a.html", "x", "text/markdown", "must end with .md"),
        ("../etc/passwd.md", "x", "text/markdown", "name:"),
        ("a/b.md", "x", "text/markdown", "name:"),
        (".hidden.md", "x", "text/markdown", "name:"),
        ("a..md", "x", "text/markdown", "name:"),
        ("x" * 98 + ".md", "x", "text/markdown", "name:"),
        ("a.md", "", "text/markdown", "content is empty"),
        ("a.md", "x" * (MAX_BYTES + 1), "text/markdown", "larger than"),
    ],
    ids=["html", "ext", "traversal", "slash", "dot", "dotdot", "long", "empty", "big"],
)
def test_validate_rejects(name, content, media_type, message):
    with pytest.raises(ArtifactInputError, match=message):
        validate(name, content, media_type)


def test_object_key_is_built_from_checked_values_only():
    artifact_id = str(uuid.uuid4())
    assert object_key(OID.upper(), artifact_id) == f"artifacts/{OID}/{artifact_id}"
    with pytest.raises(ValueError):
        object_key("../other", artifact_id)
    with pytest.raises(ValueError):
        object_key(OID, "../../x")


def test_file_store_round_trip_and_stays_inside_root(tmp_path):
    store = FileArtifactStore(tmp_path / "artifacts")
    key = object_key(OID, str(uuid.uuid4()))
    store.put(key, b"hello", "text/plain")
    assert store.get(key) == b"hello"
    store.delete(key)
    assert store.get(key) is None
    store.delete(key)  # deleting twice is fine
    with pytest.raises(ArtifactStoreError):
        store.get("../outside")


def test_store_from_env():
    assert store_from_env({}) is None
    gcs = store_from_env({"SDLC_ARTIFACT_STORE": "gs://bucket/some/prefix"})
    assert isinstance(gcs, GcsArtifactStore) and gcs.prefix == "some/prefix/"
    with pytest.raises(ValueError):
        store_from_env({"SDLC_ARTIFACT_STORE": "s3://bucket"})


def test_gcs_store_requests():
    calls = []
    objects = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"] == "Bearer t"
        if request.method == "POST":
            name = request.url.params["name"]
            assert request.url.params["ifGenerationMatch"] == "0"  # never overwrite
            objects[name] = request.content
            return httpx.Response(200, json={"name": name})
        name = request.url.path.rsplit("/o/", 1)[1]
        name = httpx.URL("http://x/" + name).path[1:]  # percent-decoded
        if request.method == "GET":
            return (
                httpx.Response(200, content=objects[name])
                if name in objects
                else httpx.Response(404)
            )
        objects.pop(name, None)
        return httpx.Response(204)

    store = GcsArtifactStore(
        "bkt", "pre", token_provider=lambda: "t", transport=httpx.MockTransport(handler)
    )
    key = object_key(OID, str(uuid.uuid4()))
    store.put(key, b"data", "text/markdown")
    assert objects == {f"pre/{key}": b"data"}
    assert calls[0].url.host == "storage.googleapis.com"
    assert store.get(key) == b"data"
    assert "/o/pre%2Fartifacts%2F" in calls[-1].url.raw_path.decode()  # one encoded object name
    store.delete(key)
    assert store.get(key) is None
    assert json.dumps(objects) == "{}"


def test_gcs_store_errors_are_store_errors():
    store = GcsArtifactStore(
        "bkt",
        token_provider=lambda: "t",
        transport=httpx.MockTransport(lambda r: httpx.Response(403)),
    )
    with pytest.raises(ArtifactStoreError, match="HTTP 403"):
        store.put(object_key(OID, str(uuid.uuid4())), b"x", "text/plain")
