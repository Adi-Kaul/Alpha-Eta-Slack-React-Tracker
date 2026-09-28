import pytest

from bot.config import load_config


def test_load_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CONFIG_YAML", raising=False)
    p = tmp_path / "c.yaml"
    p.write_text("watch_channel: a\nreminder_channel: b\nemojis: [':scream:']\nmembers: [Jane, '']\n")
    cfg = load_config(p)
    assert cfg.emojis == ["scream"]
    assert cfg.members == ["Jane"]


def test_load_from_env(monkeypatch):
    monkeypatch.setenv("CONFIG_YAML", "watch_channel: a\nreminder_channel: b\nmembers: [Jane]\n")
    monkeypatch.setenv("DRY_RUN", "1")
    cfg = load_config()
    assert cfg.watch_channel == "a" and cfg.dry_run


def test_example_configs_are_valid(monkeypatch):
    monkeypatch.delenv("CONFIG_YAML", raising=False)
    load_config("config.example.yaml")
    load_config("config.test.example.yaml")


def test_rejects_typos(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("watch_channel: a\nreminder_channel: b\nmembers: [x]\nemoji: [scream]\n")
    with pytest.raises(ValueError, match="emoji"):
        load_config(p)
