"""
conftest.py

Shared pytest fixtures for the Movies API test suite.
Sets DUCKDB_PATH before the app is imported so get_db() resolves correctly.
"""

import os
import sys
import pytest
from pathlib import Path

# Make sure `src/` is on the path so imports like `from movies_api import app` work.
SRC_DIR = Path(__file__).resolve().parents[1]   # …/src
sys.path.insert(0, str(SRC_DIR))

# Point at the real database (relative to the project root, two levels up from src/test/)
PROJECT_ROOT = SRC_DIR.parent
os.environ.setdefault("DUCKDB_PATH", str(PROJECT_ROOT / "data" / "movies.duckdb"))

from fastapi.testclient import TestClient  # noqa: E402  (must come after env var is set)
from movies_api import app                 # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    """A single TestClient instance reused across the whole test session."""
    with TestClient(app) as c:
        yield c

