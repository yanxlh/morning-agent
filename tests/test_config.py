import pytest
from pathlib import Path


def test_get_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    assert config.get_config() == {"advance_minutes": 15}


def test_save_and_get_config(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    config.save_config({"advance_minutes": 30})
    assert config.get_config()["advance_minutes"] == 30


def test_get_config_handles_corrupt_file(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text("not json", encoding="utf-8")
    assert config.get_config() == {"advance_minutes": 15}


def test_save_config_merges_with_existing(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "_CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(
        '{"advance_minutes": 5, "other": "val"}', encoding="utf-8"
    )
    config.save_config({"advance_minutes": 20})
    assert config.get_config()["advance_minutes"] == 20
