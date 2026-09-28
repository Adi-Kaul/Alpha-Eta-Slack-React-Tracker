"""Core logic: find @channel announcements, see who hasn't reacted, and nag them in the reminder channel."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config
from .store import Store

log = logging.getLogger(__name__)

# Slack encodes @channel as "<!channel>" (older messages: "<!channel|@channel>").
BROADCAST_RE = re.compile(r"<!(channel|here|everyone)(?:\|[^>]*)?>")
TRACKED_SUBTYPES = {None, "bot_message", "thread_broadcast"}


@dataclass
class Status:
    ts: str
    poster: str | None
    text: str
    permalink: str
    reacted: set[str]
    missing: list[str]  # user IDs, in roster order


def is_announcement(msg: dict, mentions: list[str]) -> bool:
    if msg.get("subtype") not in TRACKED_SUBTYPES:
        return False
    return any(m.group(1) in mentions for m in BROADCAST_RE.finditer(msg.get("text", "")))


def reacted_users(reactions: list[dict] | None, emojis: list[str]) -> set[str]:
    wanted = set(emojis)
    users: set[str] = set()
    for r in reactions or []:
        if r["name"].split("::")[0] in wanted:  # "scream::skin-tone-2" -> "scream"
            users.update(r.get("users", []))
    return users


def snippet(text: str, limit: int = 90) -> str:
    text = BROADCAST_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def in_quiet_hours(cfg: Config, now: float) -> bool:
    start, end = cfg.quiet_hours_start, cfg.quiet_hours_end
    if start is None or end is None or start == end:
        return False
    hour = datetime.fromtimestamp(now, ZoneInfo(cfg.timezone)).hour
    return start <= hour < end if start < end else hour >= start or hour < end


def reminder_due(cfg: Config, posted_at: float, last_reminded_at: float | None, now: float) -> bool:
    age_h = (now - posted_at) / 3600
    if age_h < cfg.first_reminder_after_hours or age_h > cfg.stop_after_hours:
        return False
    if last_reminded_at is None:
        return True
    return (now - last_reminded_at) / 3600 >= cfg.reminder_interval_hours


class Tracker:
    def __init__(self, client, cfg: Config, store: Store, watch_channel: str,
                 reminder_channel: str, roster: dict[str, str], clock=time.time):
        self.client = client
        self.cfg = cfg
        self.store = store
        self.watch_channel = watch_channel
        self.reminder_channel = reminder_channel
        self.roster = roster  # {user_id: label}
        self.clock = clock

    # ---- reading ----

    def announcements(self) -> list[dict]:
        oldest = self.clock() - self.cfg.stop_after_hours * 3600
        found, cursor = [], None
        while True:
            resp = self.client.conversations_history(
                channel=self.watch_channel, oldest=f"{oldest:.6f}", limit=200, cursor=cursor
            )
            found += [m for m in resp["messages"] if is_announcement(m, self.cfg.mentions)]
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                return sorted(found, key=lambda m: float(m["ts"]))

    def status_of(self, msg: dict) -> Status:
        # reactions.get with full=True is the only call guaranteed to return every reacting user.
        resp = self.client.reactions_get(channel=self.watch_channel, timestamp=msg["ts"], full=True)
        reacted = reacted_users(resp["message"].get("reactions"), self.cfg.emojis)
        poster = msg.get("user")
        missing = [
            uid for uid in self.roster
            if uid not in reacted and not (self.cfg.exclude_poster and uid == poster)
        ]
        permalink = self.client.chat_getPermalink(
            channel=self.watch_channel, message_ts=msg["ts"]
        )["permalink"]
        return Status(msg["ts"], poster, msg.get("text", ""), permalink, reacted, missing)

    def statuses(self) -> list[Status]:
        return [self.status_of(m) for m in self.announcements()]

    # ---- writing ----

    def _post(self, channel: str, text: str) -> None:
        if self.cfg.dry_run:
            log.info("[dry run] would post to %s:\n%s", channel, text)
            return
        self.client.chat_postMessage(channel=channel, text=text, unfurl_links=False)

    def emoji_str(self) -> str:
        return " or ".join(f":{e}:" for e in self.cfg.emojis)

    def reminder_text(self, st: Status) -> str:
        total = len(self.roster) - (1 if self.cfg.exclude_poster and st.poster in self.roster else 0)
        done = total - len(st.missing)
        who = f" from <@{st.poster}>" if st.poster else ""
        quote = f"\n> {snippet(st.text)}" if snippet(st.text) else ""
        pings = " ".join(f"<@{uid}>" for uid in st.missing)
        return (
            f":rotating_light: *{len(st.missing)} people still haven't reacted* with {self.emoji_str()} "
            f"to <{st.permalink}|this announcement>{who} ({done}/{total} done){quote}\n\n{pings}"
        )

    def send_reminder(self, st: Status) -> None:
        self._post(self.reminder_channel, self.reminder_text(st))
        if self.cfg.dm_missing:
            for uid in st.missing:
                self._post(uid, f"Hey! Please react with {self.emoji_str()} to <{st.permalink}|this announcement> so we know you saw it.")
        self.store.mark_reminded(self.watch_channel, st.ts, self.clock())

    def run_cycle(self, force: bool = False) -> list[Status]:
        """Checks every recent announcement and sends whatever reminders are due.

        force=True sends a reminder for every incomplete announcement right now,
        ignoring the schedule and quiet hours (used by `/reactcheck remind`).
        """
        now = self.clock()
        quiet = in_quiet_hours(self.cfg, now)
        reminded = []
        for msg in self.announcements():
            rec = self.store.get(self.watch_channel, msg["ts"])
            if rec.completed:
                continue
            due = reminder_due(self.cfg, float(msg["ts"]), rec.last_reminded_at, now)
            if not (force or (due and not quiet)):
                continue
            st = self.status_of(msg)
            if not st.missing:
                self.store.mark_completed(self.watch_channel, msg["ts"])
                if self.cfg.announce_completion and rec.reminders_sent > 0:
                    self._post(self.reminder_channel,
                               f":tada: Everyone reacted to <{st.permalink}|this announcement>. Thanks all!")
                continue
            self.send_reminder(st)
            reminded.append(st)
        return reminded
