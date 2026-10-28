"""version-01 M0: the loader contract and the registry for the existing source types."""

import subprocess
from dataclasses import replace

import pytest
from sdlc_config import load_snapshot
from sdlc_loaders import LOADERS, LoaderError, SourceItem, make_loader
from sdlc_loaders.local import GitLoader, LocalFolderLoader

from tests.support.entra import TEST_ENV


@pytest.fixture
def snapshot(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def test_registry_covers_every_schema_type():
    import json
    from pathlib import Path

    schema = json.loads(Path("config/schemas/source.schema.json").read_text())
    types = schema["properties"]["spec"]["properties"]["type"]["enum"]
    assert set(types) == set(LOADERS)


def test_local_folder_loader_yields_source_items(snapshot, config_dir):
    loader = make_loader(snapshot.sources["eng-standards"], config_dir.parent)
    assert isinstance(loader, LocalFolderLoader) and not loader.incremental
    items = list(loader.items())
    assert items and all(isinstance(i, SourceItem) for i in items)
    assert all(i.title is None and i.url is None and not i.restricted for i in items)
    assert loader.cursor is None  # full scans store no cursor
    with pytest.raises(NotImplementedError):
        loader.all_ids()


def test_missing_folder_is_a_loader_error(snapshot, tmp_path):
    source = replace(snapshot.sources["eng-standards"], location=str(tmp_path / "missing"))
    with pytest.raises(LoaderError, match="not found"):
        list(make_loader(source, tmp_path).items())


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_git_loader_reports_and_stores_the_commit(snapshot, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.md").write_text("# A\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "one")
    source = replace(
        snapshot.sources["sdlc-platform"],
        location=str(repo),
        ref="HEAD",
        include=("**/*.md",),
        exclude=(),
    )
    loader = make_loader(source, tmp_path)
    assert isinstance(loader, GitLoader)
    assert [i.path for i in loader.items()] == ["a.md"]
    commit = loader.details["commit"]
    assert len(commit) == 40 and loader.cursor == {"commit": commit}


def test_git_errors_are_loader_errors(snapshot, tmp_path):
    source = replace(snapshot.sources["sdlc-platform"], location=str(tmp_path / "nope"))
    with pytest.raises(LoaderError):
        list(make_loader(source, tmp_path).items())


def test_unknown_type_has_no_loader(snapshot, tmp_path):
    source = replace(snapshot.sources["eng-standards"], type="s3_bucket")
    with pytest.raises(LoaderError, match="no loader"):
        make_loader(source, tmp_path)
