from pathlib import Path

import pytest
from replayforge.cassettes import load_suite

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def suite():
    return load_suite(ROOT / "fixtures/suites/demo-suite.yaml")
