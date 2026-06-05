import pytest

from backend.services.recent_files_service import RecentFilesService


@pytest.fixture
def svc(tmp_path):
    return RecentFilesService(storage_path=tmp_path / "recent_files.json")


def test_get_returns_empty_when_no_file(svc):
    assert svc.get() == []


def test_add_single_file(svc, tmp_path):
    path = str(tmp_path / "a.mmd")
    svc.add(path)
    assert svc.get() == [path]


def test_add_prepends_to_list(svc, tmp_path):
    a = str(tmp_path / "a.mmd")
    b = str(tmp_path / "b.mmd")
    svc.add(a)
    svc.add(b)
    assert svc.get() == [b, a]


def test_add_deduplicates(svc, tmp_path):
    path = str(tmp_path / "a.mmd")
    svc.add(path)
    svc.add(path)
    assert svc.get() == [path]


def test_add_moves_existing_to_front(svc, tmp_path):
    a = str(tmp_path / "a.mmd")
    b = str(tmp_path / "b.mmd")
    svc.add(a)
    svc.add(b)
    svc.add(a)
    assert svc.get() == [a, b]


def test_add_trims_to_max_10(svc, tmp_path):
    for i in range(11):
        svc.add(str(tmp_path / f"file{i}.mmd"))
    assert len(svc.get()) == 10


def test_clear_empties_list(svc, tmp_path):
    svc.add(str(tmp_path / "a.mmd"))
    svc.clear()
    assert svc.get() == []


def test_persists_to_disk(tmp_path):
    storage = tmp_path / "recent_files.json"
    a = str(tmp_path / "a.mmd")
    svc1 = RecentFilesService(storage_path=storage)
    svc1.add(a)

    svc2 = RecentFilesService(storage_path=storage)
    assert svc2.get() == [a]


def test_clear_persists_to_disk(tmp_path):
    storage = tmp_path / "recent_files.json"
    svc1 = RecentFilesService(storage_path=storage)
    svc1.add(str(tmp_path / "a.mmd"))
    svc1.clear()

    svc2 = RecentFilesService(storage_path=storage)
    assert svc2.get() == []


def test_corrupted_storage_returns_empty(tmp_path):
    storage = tmp_path / "recent_files.json"
    storage.write_text("not json", encoding="utf-8")
    svc = RecentFilesService(storage_path=storage)
    assert svc.get() == []
