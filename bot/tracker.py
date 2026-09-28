"""Core logic: find @channel announcements, see who hasn't reacted, and nag them in the reminder channel."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
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
    reacted_at: dict[str, tuple[float | None, bool]] = field(default_factory=dict)  # user -> (unix time, exact?)


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


def fmt_duration(hours: float) -> str:
    mins = round(hours * 60)
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h} hour{'s' if h != 1 else ''}" + (f" {m} min" if m else "")


def checkpoints(cfg: Config, posted_at: float) -> list[tuple[str, float]]:
    """(key, unix time) for every scheduled post about an announcement, in time order.

    Keys: "halfway", "warn:<hours>", "deadline". Warnings that would land before the
    announcement was even posted (e.g. a 4h warning on a 3h deadline) are dropped.
    """
    deadline = posted_at + cfg.deadline_hours * 3600
    points = []
    if cfg.halfway_report:
        points.append(("halfway", posted_at + cfg.deadline_hours * 1800))
    for h in cfg.warn_hours_before:
        if deadline - h * 3600 > posted_at:
            points.append((f"warn:{h:g}", deadline - h * 3600))
    if cfg.final_report:
        points.append(("deadline", deadline))
    return sorted(points, key=lambda p: p[1])


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
        # The background loop and /reactcheck can both call run_cycle; don't let them double-post.
        self._cycle_lock = threading.Lock()
        self._last_checked: dict[str, float] = {}  # announcement ts -> when this process last read its reactions

    # ---- reading ----

    def announcements(self) -> list[dict]:
        # Look back a little past the deadline so a final report isn't lost if the bot was briefly down.
        oldest = self.clock() - (self.cfg.deadline_hours + 2) * 3600
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
        # Slack doesn't say when a reaction happened. reaction_added events give exact times;
        # anything they missed is stamped with the first check that noticed it. On the first check
        # since startup there's no earlier check to bound it, so the time is unknown.
        now = self.clock()
        seen_at = now if msg["ts"] in self._last_checked else None
        self.store.record_reactions(self.watch_channel, msg["ts"], reacted, seen_at, exact=False)
        self._last_checked[msg["ts"]] = now
        poster = msg.get("user")
        missing = [
            uid for uid in self.roster
            if uid not in reacted and not (self.cfg.exclude_poster and uid == poster)
        ]
        permalink = self.client.chat_getPermalink(
            channel=self.watch_channel, message_ts=msg["ts"]
        )["permalink"]
        times = self.store.reaction_times(self.watch_channel, msg["ts"])
        return Status(msg["ts"], poster, msg.get("text", ""), permalink, reacted, missing,
                      {u: times[u] for u in reacted if u in times})

    def on_reaction_added(self, event: dict) -> None:
        item = event.get("item") or {}
        if (item.get("type") == "message" and item.get("channel") == self.watch_channel
                and event.get("reaction", "").split("::")[0] in self.cfg.emojis):
            self.store.record_reactions(self.watch_channel, item["ts"], [event["user"]],
                                        float(event["event_ts"]), exact=True)

    def statuses(self) -> list[Status]:
        return [self.status_of(m) for m in self.announcements()]

    def deadline_of(self, st: Status) -> float:
        return float(st.ts) + self.cfg.deadline_hours * 3600

    # ---- writing ----

    def _post(self, channel: str, text: str) -> None:
        # The announcements channel is read-only: never post there, whatever the config says.
        if channel == self.watch_channel:
            log.error("Refusing to post in the watched channel %s", channel)
            return
        if self.cfg.dry_run:
            log.info("[dry run] would post to %s:\n%s", channel, text)
            return
        self.client.chat_postMessage(channel=channel, text=text, unfurl_links=False)

    def emoji_str(self) -> str:
        return " or ".join(f":{e}:" for e in self.cfg.emojis)

    def expected_count(self, st: Status) -> int:
        return len(self.roster) - (1 if self.cfg.exclude_poster and st.poster in self.roster else 0)

    def message_for(self, st: Status, key: str) -> str:
        total = self.expected_count(st)
        done = total - len(st.missing)
        link = f"<{st.permalink}|this announcement>" + (f" from <@{st.poster}>" if st.poster else "")
        quote = f"\n> {snippet(st.text)}" if snippet(st.text) else ""
        pings = " ".join(f"<@{uid}>" for uid in st.missing)
        left = fmt_duration(max(0.0, (self.deadline_of(st) - self.clock()) / 3600))
        n = len(st.missing)

        if key == "deadline":
            return (f":alarm_clock: *Time's up!* {n} {'person' if n == 1 else 'people'} never reacted "
                    f"with {self.emoji_str()} to {link} ({done}/{total} did).{quote}\n\n*Didn't react:* {pings}")
        if key == "halfway":
            head = f":bar_chart: *Halfway check:* {done}/{total} have reacted with {self.emoji_str()} to {link}. {left} left."
        elif key.startswith("warn:"):
            icon = ":rotating_light:" if float(key[5:]) <= 1 else ":warning:"
            head = f"{icon} *{left} left* to react with {self.emoji_str()} to {link} ({done}/{total} done)."
        else:  # manual /reactcheck remind
            head = f":mega: *Reminder:* react with {self.emoji_str()} to {link} ({done}/{total} done, {left} left)."
        return f"{head}{quote}\n\n*Still missing ({n}):* {pings}"

    def send(self, st: Status, key: str) -> None:
        self._post(self.reminder_channel, self.message_for(st, key))
        if self.cfg.dm_missing and key != "deadline":
            for uid in st.missing:
                self._post(uid, f"Hey! Please react with {self.emoji_str()} to <{st.permalink}|this announcement> "
                                f"so we know you saw it.")

    def run_cycle(self, force: bool = False) -> list[Status]:
        """Checks every open announcement and posts whatever is due. Returns the ones it posted about.

        If the bot was down and several checkpoints were missed, only the most recent one is posted.
        force=True posts a reminder for every open announcement right now (`/reactcheck remind`),
        without affecting the schedule.
        """
        with self._cycle_lock:
            return self._run_cycle(force)

    def _run_cycle(self, force: bool) -> list[Status]:
        now = self.clock()
        posted = []
        for msg in self.announcements():
            rec = self.store.get(self.watch_channel, msg["ts"])
            if rec.completed:
                continue
            posted_at = float(msg["ts"])
            due = [k for k, t in checkpoints(self.cfg, posted_at) if t <= now and k not in rec.sent]
            past_deadline = now >= posted_at + self.cfg.deadline_hours * 3600

            st = self.status_of(msg)
            if not st.missing:
                if self.cfg.announce_completion and rec.sent and not self.cfg.dry_run:
                    self._post(self.reminder_channel,
                               f":tada: Everyone reacted to <{st.permalink}|this announcement>. Thanks all!")
                if not self.cfg.dry_run:
                    self.store.mark_completed(self.watch_channel, msg["ts"])
                continue

            if force and not past_deadline:
                self.send(st, "manual")
                posted.append(st)
                if not self.cfg.dry_run:
                    self.store.mark_sent(self.watch_channel, msg["ts"], ["manual"])
            elif due:
                self.send(st, due[-1])
                posted.append(st)
                if not self.cfg.dry_run:
                    self.store.mark_sent(self.watch_channel, msg["ts"], due)

            if past_deadline and not self.cfg.dry_run:
                self.store.mark_completed(self.watch_channel, msg["ts"])
        return posted
