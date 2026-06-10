import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # routers must exist before importing main
    from backend.main import app

    with TestClient(app) as c:
        yield c
