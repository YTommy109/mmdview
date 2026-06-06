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
_logger = logging.getLogger(__name__)


class UpdateService:
    def __init__(self) -> None:
        self._cache: dict = {"checked_at": None, "result": None}
        self._download_state: dict = {"percent": 0, "status": "idle", "dmg_path": None}
        self._state_lock = threading.Lock()

    def _is_newer(self, remote: str, current: str) -> bool:
        def to_tuple(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))

        return to_tuple(remote) > to_tuple(current)

    def _find_dmg_url(self, assets: list[dict]) -> str | None:
        for asset in assets:
            if asset.get("name", "").endswith(".dmg"):
                return asset.get("browser_download_url")
        return None

    def check_update(self) -> dict:
        """GitHub Releases API で最新バージョンを確認する（1時間TTLキャッシュ）。

        MMDVIEW_MOCK_DMG が設定されている場合は GitHub を呼ばずモック結果を返す。
        """
        if os.environ.get("MMDVIEW_MOCK_DMG"):
            return {"available": True, "version": "999.0.0", "download_url": None}
        now = time.monotonic()
        if self._cache["checked_at"] and now - self._cache["checked_at"] < _CACHE_TTL:
            return self._cache["result"]
        try:
            resp = httpx.get(GITHUB_API_URL, timeout=5, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            tag = data["tag_name"].lstrip("v")
            result: dict = {
                "available": self._is_newer(tag, _CURRENT_VERSION),
                "version": tag,
                "download_url": self._find_dmg_url(data.get("assets", [])),
            }
        except Exception:
            result = {"available": False, "version": _CURRENT_VERSION, "download_url": None}
        self._cache["checked_at"] = now
        self._cache["result"] = result
        _logger.info("更新確認: available=%s version=%s", result["available"], result["version"])
        return result

    def get_download_state(self) -> dict:
        """ダウンロード状態のコピーを返す。

        MMDVIEW_MOCK_DMG が設定されている場合はそのパスで完了状態を返す。
        """
        if mock_dmg := os.environ.get("MMDVIEW_MOCK_DMG"):
            return {"percent": 100, "status": "done", "dmg_path": mock_dmg}
        with self._state_lock:
            return dict(self._download_state)

    def _do_download(self, url: str, dest: Path | None = None) -> None:
        """実際のダウンロード処理（バックグラウンドスレッドで実行）。"""
        with self._state_lock:
            self._download_state.update({"percent": 0, "status": "downloading", "dmg_path": None})
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
                            with self._state_lock:
                                self._download_state["percent"] = int(downloaded / total * 100)
            with self._state_lock:
                self._download_state["status"] = "done"
                self._download_state["dmg_path"] = str(dmg_path)
        except Exception:
            _logger.error("ダウンロード失敗: url=%s", url, exc_info=True)
            with self._state_lock:
                self._download_state["status"] = "error"

    def invalidate_cache(self) -> None:
        """更新確認キャッシュを無効化する。"""
        self._cache["checked_at"] = None
        self._cache["result"] = None

    def download_update(self, url: str) -> None:
        """ダウンロードをバックグラウンドスレッドで開始する。"""
        with self._state_lock:
            if self._download_state["status"] == "downloading":
                return
        threading.Thread(target=self._do_download, args=(url,), daemon=True).start()

    def _reset_for_test(self) -> None:
        """テスト用: 全状態を初期値にリセットする。"""
        with self._state_lock:
            self._cache.update({"checked_at": None, "result": None})
            self._download_state.update({"percent": 0, "status": "idle", "dmg_path": None})


update_service = UpdateService()
