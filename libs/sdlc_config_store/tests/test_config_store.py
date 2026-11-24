import json

import pytest
from sdlc_config_store import (
    ConfigStore,
    ConfigUnavailable,
    DirSource,
    make_bundle,
    make_pointer,
    parse_bundle,
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def publish(source: DirSource, env: str, config: dict) -> str:
    doc = make_bundle(env, config)
    source.write(f"bundles/{doc['version']}.json", json.dumps(doc).encode())
    return doc["version"]


def activate(source: DirSource, version: str) -> None:
    source.write("active.json", json.dumps(make_pointer(version, "tester", None)).encode())


def test_version_is_a_hash_of_env_and_content():
    a = make_bundle("local", {"x": 1})["version"]
    assert a == make_bundle("local", {"x": 1})["version"]
    assert a != make_bundle("local", {"x": 2})["version"]
    assert a != make_bundle("dev", {"x": 1})["version"]


def test_tampered_bundle_is_refused():
    doc = make_bundle("local", {"grants": []})
    doc["config"]["grants"] = [{"id": "everything"}]
    with pytest.raises(ConfigUnavailable, match="does not match"):
        parse_bundle(json.dumps(doc).encode())


def test_bundle_for_another_environment_is_refused():
    doc = make_bundle("dev", {})
    with pytest.raises(ConfigUnavailable, match="environment"):
        parse_bundle(json.dumps(doc).encode(), env="local")


def test_no_active_bundle_fails_closed(tmp_path):
    store = ConfigStore(DirSource(tmp_path), "local")
    with pytest.raises(ConfigUnavailable):
        store.load()


def test_activation_takes_effect_after_the_refresh_interval(tmp_path):
    source, clock = DirSource(tmp_path), Clock()
    first = publish(source, "local", {"n": 1})
    activate(source, first)
    store = ConfigStore(source, "local", refresh_seconds=30, clock=clock)
    assert store.load().version == first

    second = publish(source, "local", {"n": 2})
    activate(source, second)
    clock.now = 10
    assert store.current().version == first  # not re-read yet
    clock.now = 31
    assert store.current().version == second
    assert store.current().config == {"n": 2}


def test_broken_pointer_keeps_the_last_verified_bundle(tmp_path):
    source, clock = DirSource(tmp_path), Clock()
    first = publish(source, "local", {"n": 1})
    activate(source, first)
    store = ConfigStore(source, "local", refresh_seconds=1, clock=clock)
    store.load()

    activate(source, "0123456789abcdef")  # no such bundle
    clock.now = 5
    assert store.current().version == first
    assert "FileNotFoundError" in store.last_error


def test_reactivating_the_previous_version_restores_it(tmp_path):
    source, clock = DirSource(tmp_path), Clock()
    first, second = publish(source, "local", {"n": 1}), publish(source, "local", {"n": 2})
    activate(source, second)
    store = ConfigStore(source, "local", refresh_seconds=1, clock=clock)
    assert store.load().version == second
    activate(source, first)
    clock.now = 2
    assert store.current().version == first
