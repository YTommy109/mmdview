def _make_registry():
    from backend.services.window_registry import WindowRegistry

    return WindowRegistry()


def test_get_watch_returns_none_for_unknown():
    r = _make_registry()
    assert r.get_watch("nonexistent") is None


def test_get_bus_returns_none_for_unknown():
    r = _make_registry()
    assert r.get_bus("nonexistent") is None


def test_create_registers_watch_and_bus():
    r = _make_registry()
    r.create("w1")
    assert r.get_watch("w1") is not None
    assert r.get_bus("w1") is not None
    r.remove("w1")


def test_remove_stops_watch_and_clears_entry(tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A-->B")
    r = _make_registry()
    r.create("w1", str(f))
    watch = r.get_watch("w1")
    r.remove("w1")
    assert watch._observer is None
    assert r.get_watch("w1") is None


def test_find_by_path_returns_none_when_not_registered():
    r = _make_registry()
    r.create("w1")
    assert r.find_by_path("/nonexistent/file.mmd") is None
    r.remove("w1")


def test_find_by_path_returns_window_id(tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD")
    r = _make_registry()
    r.create("w1", str(f))
    assert r.find_by_path(str(f)) == "w1"
    r.remove("w1")


def test_snapshot_returns_all_window_ids_and_paths(tmp_path):
    f1 = tmp_path / "a.mmd"
    f1.write_text("graph TD")
    f2 = tmp_path / "b.mmd"
    f2.write_text("graph TD")
    r = _make_registry()
    r.create("w1", str(f1))
    r.create("w2", str(f2))
    snap = dict(r.snapshot())
    assert snap["w1"] == f1
    assert snap["w2"] == f2
    r.remove("w1")
    r.remove("w2")
