"""The retrieval eval's expected files must exist, so the eval cannot go stale silently (it only
runs with SDLC_EVAL=1 against the ingested dev DB, never in CI). Runs in CI without .env."""

from pathlib import Path

import yaml

from tests.support.config import REPO_ROOT, SAMPLE_FOLDERS, SAMPLES_DIR

QUESTIONS = REPO_ROOT / "tests" / "evals" / "retrieval_questions.yaml"
REPO_SOURCE = "sdlc-platform"  # this repository (GitHub main); checked in the working tree


def _expected() -> list[tuple[str, str, str]]:
    doc = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    out = []
    for q in doc["questions"]:
        for entry in q["expect"]:
            source, _, path = entry.partition(":")
            out.append((q["q"], source, path))
    return out


def _configured_sources() -> set[str]:
    return {p.stem for p in (REPO_ROOT / "config" / "sources").glob("*.yaml")}


def test_expected_sources_are_configured():
    configured = _configured_sources()
    missing = {(source, q) for q, source, _ in _expected() if source not in configured}
    assert not missing, f"eval questions expect sources that are not in config/sources: {missing}"


def test_expected_files_exist():
    missing = []
    for q, source, path in _expected():
        if source == REPO_SOURCE:
            root = REPO_ROOT
        elif source in SAMPLE_FOLDERS:
            root = SAMPLES_DIR / SAMPLE_FOLDERS[source]
        else:
            continue  # a remote source: not checkable offline
        if not (Path(root) / path).is_file():
            missing.append(f"{source}:{path} ({q[:50]})")
    assert not missing, "eval questions expect files that do not exist:\n" + "\n".join(missing)
