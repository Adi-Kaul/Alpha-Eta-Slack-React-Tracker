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

    first_reminder_after_hours: float = 12
    reminder_interval_hours: float = 24
    stop_after_hours: float = 72

    # Reminders are held (not skipped) during quiet hours, then sent once they end.
    timezone: str = "America/Detroit"
    quiet_hours_start: int | None = 23
    quiet_hours_end: int | None = 9

    check_interval_minutes: float = 15
    # Don't nag whoever posted the announcement.
    exclude_poster: bool = True
    dm_missing: bool = False
    announce_completion: bool = True

    db_path: str = "tracker.db"
    dry_run: bool = False

    bot_token: str = ""
    app_token: str = ""


def load_config(path: str | os.PathLike | None = None) -> Config:
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
