import json
from pathlib import Path

from backend.paths import APP_DATA_DIR

_MAX_RECENT = 10
_DEFAULT_STORAGE = APP_DATA_DIR / "recent_files.json"


class RecentFilesService:
    def __init__(self, storage_path: Path = _DEFAULT_STORAGE) -> None:
        self._storage = storage_path
        self._files: list[str] = self._load()

    def get(self) -> list[str]:
        return list(self._files)

    def add(self, path: str) -> None:
        self._files = [path] + [p for p in self._files if p != path]
        self._files = self._files[:_MAX_RECENT]
        self._save()

    def clear(self) -> None:
        self._files = []
        self._save()

    def _load(self) -> list[str]:
        if not self._storage.exists():
            return []
        try:
            data = json.loads(self._storage.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(p) for p in data]
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def _save(self) -> None:
        self._storage.write_text(json.dumps(self._files), encoding="utf-8")


recent_files_service = RecentFilesService()
