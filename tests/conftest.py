"""Shared fixtures."""

import pytest

from tests.support.entra import FakeEntra


@pytest.fixture
def entra() -> FakeEntra:
    return FakeEntra()
