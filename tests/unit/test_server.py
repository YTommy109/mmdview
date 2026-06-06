# tests/unit/test_server.py
import socket
import threading
import time

from backend.server import find_free_port, wait_for_server


def test_find_free_port_returns_available_port():
    port = find_free_port()
    assert isinstance(port, int)
    assert 1024 < port < 65536
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_wait_for_server_succeeds_when_server_is_up():
    port = find_free_port()

    def _serve():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            s.listen(1)
            s.accept()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    time.sleep(0.05)
    wait_for_server(port, timeout=2.0)


def test_wait_for_server_raises_when_timeout():
    port = find_free_port()
    import pytest

    with pytest.raises(RuntimeError, match="did not start"):
        wait_for_server(port, timeout=0.1)
