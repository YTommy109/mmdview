import pytest


@pytest.fixture(autouse=True)
def reset_watch_service():
    from backend.services.watch_service import watch_service

    watch_service.stop()
    watch_service._path = None
    yield
    watch_service.stop()
    watch_service._path = None


def test_index_shows_welcome_when_no_file(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ファイルを開く" in response.text


def test_index_shows_viewer_when_file_set(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.watch_service import watch_service

    watch_service.set_file(str(f))

    response = client.get("/")
    assert response.status_code == 200
    assert "graph TD" in response.text
    assert 'class="toolbar"' not in response.text
