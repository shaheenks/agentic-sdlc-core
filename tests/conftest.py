"""Shared fixtures."""

from pathlib import Path

import pytest

from tests.support.config import make_config_dir
from tests.support.entra import FakeEntra


@pytest.fixture
def entra() -> FakeEntra:
    return FakeEntra()


@pytest.fixture
def config_dir(tmp_path) -> Path:
    """Repo config with a fixed test GroupMap; safe to mutate."""
    return make_config_dir(tmp_path)
