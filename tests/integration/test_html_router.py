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


def test_viewer_has_zoom_controls(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w2", str(f))

    response = client.get("/?window_id=w2")
    assert response.status_code == 200
    assert 'id="diagram-wrap"' in response.text
    assert 'id="zoom-in"' in response.text
    assert 'id="zoom-out"' in response.text
    assert 'id="zoom-label"' in response.text
    assert 'class="zoom-controls"' in response.text


def test_viewer_includes_hyperscript(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-hyper-check", str(f))

    response = client.get("/?window_id=w-hyper-check")
    assert response.status_code == 200
    assert "_hyperscript.min.js" in response.text


def test_viewer_has_sse_connect_with_window_id(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-sse-check", str(f))

    response = client.get("/?window_id=w-sse-check")
    assert response.status_code == 200
    assert "new EventSource('/events?window_id=w-sse-check')" in response.text


def test_viewer_has_zoom_controller_and_no_viewer_js(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-zc-check", str(f))

    response = client.get("/?window_id=w-zc-check")
    assert response.status_code == 200
    assert "install ZoomController" in response.text
    assert "viewer.js" not in response.text


def test_viewer_has_deleted_sse_handler(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-del-handler", str(f))
    response = client.get("/?window_id=w-del-handler")
    assert response.status_code == 200
    assert 'id="mmd-deleted-banner"' in response.text
    assert "#e8e8e8" in response.text
