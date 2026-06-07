import socket
import threading
import time

import httpx
import pytest
import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    """FastAPI サーバーをバックグラウンドスレッドで起動し、e2e ウィンドウを登録する。"""
    from backend.main import app
    from backend.services.window_registry import window_registry

    tmp = tmp_path_factory.mktemp("e2e")
    mmd_file = tmp / "test.mmd"
    mmd_file.write_text("graph TD\n    A --> B\n    B --> C", encoding="utf-8")
    window_registry.create("e2e", str(mmd_file))

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(url, timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)

    yield url

    server.should_exit = True
    window_registry.remove("e2e")


@pytest.fixture
def viewer_page(browser, server_url):
    """テストごとに新鮮な browser context（localStorage がクリアな状態）でビューアを開く。"""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{server_url}/?window_id=e2e")
    # SSE 接続が常時オープンのため networkidle には到達しない
    page.wait_for_load_state("load")
    page.locator("#zoom-label").wait_for()
    yield page
    context.close()
