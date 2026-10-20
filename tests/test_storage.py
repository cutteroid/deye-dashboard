"""Tests for crash-safe JSON storage helpers."""
import json
import os

from storage import atomic_write_json, load_json


def test_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(str(path), {"a": 1, "b": [1, 2]}, indent=2)
    assert load_json(str(path), {}) == {"a": 1, "b": [1, 2]}
    assert not os.path.exists(f"{path}.tmp")


def test_missing_file_returns_default(tmp_path):
    assert load_json(str(tmp_path / "nope.json"), {"x": 0}) == {"x": 0}


def test_corrupt_file_is_moved_aside(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text('{"2026-10-17": {"l1_wh": 12')  # truncated by a power cut
    assert load_json(str(path), {}) == {}
    assert not path.exists()
    assert (tmp_path / "stats.json.corrupt").exists()
    # The feature recovers: next write/read works
    atomic_write_json(str(path), {"ok": True})
    assert load_json(str(path), {}) == {"ok": True}


def test_failed_write_keeps_old_content(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(str(path), {"version": 1})

    class Unserializable:
        pass

    try:
        atomic_write_json(str(path), {"bad": Unserializable()})
    except TypeError:
        pass
    assert json.loads(path.read_text()) == {"version": 1}


class TestDataPath:
    def test_uses_data_folder_when_present(self, tmp_path, monkeypatch):
        from storage import data_path
        monkeypatch.chdir(tmp_path)
        assert data_path("phase_stats.json") == "phase_stats.json"          # plain install
        (tmp_path / "data").mkdir()
        assert data_path("phase_stats.json") == os.path.join("data", "phase_stats.json")  # Docker volume
