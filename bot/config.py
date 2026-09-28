"""Loads config.yaml + environment variables into a single Config object."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    # Where announcements are posted, and where reminders go. Names ("general") or IDs ("C0123...").
    watch_channel: str
    reminder_channel: str

    # Roster entries can be Slack user IDs, emails, or display/real names.
    members: list[str]

    # Emoji names without colons. Any one of these counts as "reacted".
    emojis: list[str] = field(default_factory=lambda: ["scream"])

    # Which broadcast mentions mark a message as an announcement to track.
    mentions: list[str] = field(default_factory=lambda: ["channel"])

    # Everyone has this long after an announcement is posted to react.
    deadline_hours: float = 24
    # Posts to the reminder channel, each tagging whoever still hasn't reacted:
    halfway_report: bool = True                 # halfway to the deadline
    warn_hours_before: list[float] = field(default_factory=lambda: [4, 1])
    final_report: bool = True                   # at the deadline: who never reacted

    check_interval_minutes: float = 5
    # Don't nag whoever posted the announcement.
    exclude_poster: bool = True
    dm_missing: bool = False
    announce_completion: bool = True

    db_path: str = "tracker.db"
    dry_run: bool = False

    bot_token: str = ""
    app_token: str = ""


def load_config(path: str | os.PathLike | None = None) -> Config:
    # On hosts like Railway/Render it's easier to paste the whole YAML into a CONFIG_YAML env var.
    if path is None and os.environ.get("CONFIG_YAML"):
        path, raw = "CONFIG_YAML", yaml.safe_load(os.environ["CONFIG_YAML"]) or {}
    else:
        path = Path(path or os.environ.get("CONFIG_PATH", "config.yaml"))
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    known = {k for k in Config.__dataclass_fields__}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"Unknown keys in {path}: {', '.join(sorted(unknown))}")

    raw["emojis"] = [e.strip(":") for e in raw.get("emojis", ["scream"])]
    raw["members"] = [str(m).strip() for m in raw.get("members") or [] if str(m).strip()]
    if not raw["members"]:
        raise ValueError(f"{path} has no members listed")

    cfg = Config(**raw)
    cfg.bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    cfg.app_token = os.environ.get("SLACK_APP_TOKEN", "")
    cfg.dry_run = cfg.dry_run or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    return cfg
