import pytest


@pytest.fixture(autouse=True)
def cleanup_registry():
    yield
    from backend.services.window_registry import window_registry

    for wid, _ in list(window_registry.snapshot()):
        window_registry.remove(wid)


def test_index_shows_welcome_when_no_window_id(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "File → Open..." in response.text


def test_index_shows_welcome_for_unknown_window_id(client):
    response = client.get("/?window_id=unknown-id")
    assert response.status_code == 200
    assert "File → Open..." in response.text


def test_index_shows_viewer_when_file_registered(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w1", str(f))

    response = client.get("/?window_id=w1")
    assert response.status_code == 200
    assert "graph TD" in response.text
