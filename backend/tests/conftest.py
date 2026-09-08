"""Pytest fixtures for Phase 1 contract tests."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is on sys.path so app can be imported
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Provides a TestClient instance for contract endpoint calls."""
    with TestClient(app) as test_client:
        yield test_client
