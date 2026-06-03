# backend/services/update_service.py
"""アプリ内自動アップデート処理。"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import httpx

from backend.version import __version__ as _CURRENT_VERSION

GITHUB_API_URL = "https://api.github.com/repos/YTommy109/mmdview/releases/latest"
_CACHE_TTL = 3600

_cache: dict = {"checked_at": None, "result": None}
_download_state: dict = {"percent": 0, "status": "idle", "dmg_path": None}
_state_lock = threading.Lock()
_logger = logging.getLogger(__name__)


def _is_newer(remote: str, current: str) -> bool:
    def to_tuple(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    return to_tuple(remote) > to_tuple(current)


def _find_dmg_url(assets: list[dict]) -> str | None:
    for asset in assets:
        if asset.get("name", "").endswith(".dmg"):
            return asset.get("browser_download_url")
    return None


def check_update() -> dict:
    """GitHub Releases API で最新バージョンを確認する（1時間TTLキャッシュ）。

    MMDVIEW_MOCK_DMG が設定されている場合は GitHub を呼ばずモック結果を返す。
    """
    if os.environ.get("MMDVIEW_MOCK_DMG"):
        return {"available": True, "version": "999.0.0", "download_url": None}
    now = time.monotonic()
    if _cache["checked_at"] and now - _cache["checked_at"] < _CACHE_TTL:
        return _cache["result"]
    try:
        resp = httpx.get(GITHUB_API_URL, timeout=5, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        tag = data["tag_name"].lstrip("v")
        result: dict = {
            "available": _is_newer(tag, _CURRENT_VERSION),
            "version": tag,
            "download_url": _find_dmg_url(data.get("assets", [])),
        }
    except Exception:
        result = {"available": False, "version": _CURRENT_VERSION, "download_url": None}
    _cache["checked_at"] = now
    _cache["result"] = result
    _logger.info("更新確認: available=%s version=%s", result["available"], result["version"])
    return result


def get_download_state() -> dict:
    """ダウンロード状態のコピーを返す。

    MMDVIEW_MOCK_DMG が設定されている場合はそのパスで完了状態を返す。
    """
    if mock_dmg := os.environ.get("MMDVIEW_MOCK_DMG"):
        return {"percent": 100, "status": "done", "dmg_path": mock_dmg}
    with _state_lock:
        return dict(_download_state)


def _do_download(url: str, dest: Path | None = None) -> None:
    """実際のダウンロード処理（バックグラウンドスレッドで実行）。"""
    with _state_lock:
        _download_state.update({"percent": 0, "status": "downloading", "dmg_path": None})
    dmg_path = dest or Path.home() / "Downloads" / "mmdview-update.dmg"
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with dmg_path.open("wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        with _state_lock:
                            _download_state["percent"] = int(downloaded / total * 100)
        with _state_lock:
            _download_state["status"] = "done"
            _download_state["dmg_path"] = str(dmg_path)
    except Exception:
        _logger.error("ダウンロード失敗: url=%s", url, exc_info=True)
        with _state_lock:
            _download_state["status"] = "error"


def invalidate_cache() -> None:
    """更新確認キャッシュを無効化する。"""
    _cache["checked_at"] = None
    _cache["result"] = None


def download_update(url: str) -> None:
    """ダウンロードをバックグラウンドスレッドで開始する。"""
    with _state_lock:
        if _download_state["status"] == "downloading":
            return
    threading.Thread(target=_do_download, args=(url,), daemon=True).start()
