"""The real knowledge bundle passes the lint, so `uv run pytest` catches what CI's `knowledge` job
catches (CH-0007, NFR-MAINT-005)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_bundle_passes_the_lint():
    spec = importlib.util.spec_from_file_location(
        "okf_bundle_repo", ROOT / "scripts" / "okf_bundle.py"
    )
    okf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(okf)
    okf.configure(ROOT)
    assert okf.lint() == []
