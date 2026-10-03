"""Result store behavior on real temporary files."""
import json
import stat

from verisys.store import ResultStore, default_root

KEY = {"source": "https://github.com/o/r", "commit": "a" * 40, "architecture_id": "b" * 64}


def test_round_trip_requires_exact_key(tmp_path):
    store = ResultStore(tmp_path)
    saved_at = store.put("discovery", KEY, {"candidates": [1]})
    assert store.get("discovery", KEY) == ({"candidates": [1]}, saved_at)
    assert store.get("discovery", {**KEY, "commit": "c" * 40}) is None
    assert store.get("understanding", KEY) is None


def test_files_are_private_and_outside_any_repository(tmp_path):
    store = ResultStore(tmp_path / "results")
    store.put("verification", KEY, {"ok": True})
    [path] = (tmp_path / "results" / "verification").iterdir()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "results").stat().st_mode) == 0o700
    assert not list((tmp_path / "results" / "verification").glob(".tmp-*"))


def test_corrupt_foreign_or_oversized_files_are_misses(tmp_path):
    store = ResultStore(tmp_path)
    store.put("discovery", KEY, {"a": 1})
    [path] = (tmp_path / "discovery").iterdir()
    record = json.loads(path.read_text())
    for broken in ["{not json", json.dumps({**record, "key": {**KEY, "commit": "x"}}),
                   json.dumps({**record, "store_version": "old"}), json.dumps({**record, "payload": []}),
                   "x" * (4 * 1024 * 1024 + 1)]:
        path.write_text(broken)
        assert store.get("discovery", KEY) is None


def test_unwritable_store_never_fails(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    assert ResultStore(blocker / "results").put("discovery", KEY, {"a": 1}) is None
    assert ResultStore(blocker / "results").get("discovery", KEY) is None


def test_default_root(monkeypatch, tmp_path):
    monkeypatch.setenv("VERISYS_RESULTS_DIR", str(tmp_path / "custom"))
    assert default_root() == tmp_path / "custom"
    monkeypatch.delenv("VERISYS_RESULTS_DIR")
    assert default_root() == default_root().home() / ".verisys" / "results"
