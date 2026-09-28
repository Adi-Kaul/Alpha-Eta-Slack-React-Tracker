from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bot.config import Config
from bot.resolve import resolve_channel, resolve_members
from bot.store import Store
from bot.tracker import Tracker, in_quiet_hours, is_announcement, reacted_users, reminder_due, snippet

HOUR = 3600
# A Wednesday at 2pm Detroit time, safely outside default quiet hours.
NOON = datetime(2026, 9, 30, 14, 0, tzinfo=ZoneInfo("America/Detroit")).timestamp()


class FakeClient:
    """Just enough of slack_sdk.WebClient for the tracker."""

    def __init__(self, messages=None, reactions=None, users=None, channels=None):
        self.messages = messages or []
        self.reactions = reactions or {}  # ts -> [{"name", "users"}]
        self.users = users or []
        self.channels = channels or []
        self.posted = []

    def conversations_history(self, channel, oldest, limit, cursor=None):
        return {"messages": [m for m in self.messages if float(m["ts"]) >= float(oldest)]}

    def reactions_get(self, channel, timestamp, full):
        return {"message": {"reactions": self.reactions.get(timestamp, [])}}

    def chat_getPermalink(self, channel, message_ts):
        return {"permalink": f"https://club.slack.com/archives/{channel}/p{message_ts.replace('.', '')}"}

    def chat_postMessage(self, channel, text, **_):
        self.posted.append((channel, text))

    def users_list(self, cursor=None, limit=200):
        return {"members": self.users}

    def conversations_list(self, cursor=None, limit=200, **_):
        return {"channels": self.channels}


def make_cfg(**kw):
    base = dict(watch_channel="C_ANN", reminder_channel="C_SLACK", members=["x"],
                quiet_hours_start=None, quiet_hours_end=None)
    base.update(kw)
    return Config(**base)


def make_tracker(client, now, roster=("U1", "U2", "U3"), **cfg_kw):
    cfg = make_cfg(**cfg_kw)
    return Tracker(client, cfg, Store(":memory:"), "C_ANN", "C_SLACK",
                   {u: u.lower() for u in roster}, clock=lambda: now[0])


def ann(ts, user="U9", text="<!channel> meeting tonight at 7"):
    return {"ts": f"{ts:.6f}", "user": user, "text": text}


# ---- pure helpers ----

@pytest.mark.parametrize("text,expected", [
    ("<!channel> hi", True),
    ("hey <!channel|@channel> hi", True),
    ("<!here> hi", False),
    ("no mention", False),
    ("<#C123|channel> is a channel link, not a broadcast", False),
])
def test_is_announcement(text, expected):
    assert is_announcement({"text": text}, ["channel"]) is expected


def test_join_messages_are_not_announcements():
    assert not is_announcement({"text": "<!channel>", "subtype": "channel_join"}, ["channel"])


def test_reacted_users_handles_skin_tones_and_multiple_emojis():
    reactions = [
        {"name": "scream", "users": ["U1"]},
        {"name": "scream::skin-tone-3", "users": ["U2"]},
        {"name": "thumbsup", "users": ["U3"]},
        {"name": "astonished", "users": ["U4"]},
    ]
    assert reacted_users(reactions, ["scream"]) == {"U1", "U2"}
    assert reacted_users(reactions, ["scream", "astonished"]) == {"U1", "U2", "U4"}


def test_snippet_strips_mention_and_truncates():
    assert snippet("<!channel>   dues are due\nfriday") == "dues are due friday"
    assert len(snippet("<!channel> " + "a" * 200)) == 90


def test_reminder_schedule():
    cfg = make_cfg(first_reminder_after_hours=12, reminder_interval_hours=24, stop_after_hours=72)
    t0 = 1_000_000.0
    assert not reminder_due(cfg, t0, None, t0 + 11 * HOUR)
    assert reminder_due(cfg, t0, None, t0 + 12 * HOUR)
    assert not reminder_due(cfg, t0, t0 + 12 * HOUR, t0 + 30 * HOUR)
    assert reminder_due(cfg, t0, t0 + 12 * HOUR, t0 + 36 * HOUR)
    assert not reminder_due(cfg, t0, t0 + 60 * HOUR, t0 + 90 * HOUR)  # past stop_after


def test_quiet_hours_wrap_midnight():
    cfg = make_cfg(quiet_hours_start=23, quiet_hours_end=9, timezone="America/Detroit")
    at = lambda h: datetime(2026, 9, 30, h, 30, tzinfo=ZoneInfo("America/Detroit")).timestamp()
    assert in_quiet_hours(cfg, at(23))
    assert in_quiet_hours(cfg, at(3))
    assert not in_quiet_hours(cfg, at(9))
    assert not in_quiet_hours(cfg, at(14))


# ---- full cycle ----

def test_reminds_only_missing_members_after_delay():
    posted_at = NOON - 13 * HOUR
    client = FakeClient(messages=[ann(posted_at), {"ts": f"{posted_at + 5:.6f}", "text": "normal msg"}],
                        reactions={f"{posted_at:.6f}": [{"name": "scream", "users": ["U1"]}]})
    now = [NOON]
    tr = make_tracker(client, now)

    tr.run_cycle()
    assert len(client.posted) == 1
    channel, text = client.posted[0]
    assert channel == "C_SLACK"
    assert "<@U2> <@U3>" in text and "<@U1>" not in text
    assert "(1/3 done)" in text
    assert "meeting tonight at 7" in text

    # Next check 15 min later: not due again yet.
    now[0] += 900
    tr.run_cycle()
    assert len(client.posted) == 1

    # A day later, U2 has reacted -> only U3 gets pinged.
    client.reactions[f"{posted_at:.6f}"].append({"name": "scream", "users": ["U2"]})
    now[0] += 24 * HOUR
    tr.run_cycle()
    assert len(client.posted) == 2
    assert "<@U3>" in client.posted[1][1] and "<@U2>" not in client.posted[1][1]


def test_no_reminder_before_first_delay():
    client = FakeClient(messages=[ann(NOON - 2 * HOUR)])
    tr = make_tracker(client, [NOON])
    tr.run_cycle()
    assert client.posted == []


def test_force_ignores_schedule():
    client = FakeClient(messages=[ann(NOON - 60)])
    tr = make_tracker(client, [NOON])
    assert len(tr.run_cycle(force=True)) == 1
    assert len(client.posted) == 1


def test_completion_announced_once_then_stops_checking():
    posted_at = NOON - 13 * HOUR
    ts = f"{posted_at:.6f}"
    client = FakeClient(messages=[ann(posted_at)], reactions={ts: []})
    now = [NOON]
    tr = make_tracker(client, now)
    tr.run_cycle()  # reminder
    client.reactions[ts] = [{"name": "scream", "users": ["U1", "U2", "U3"]}]
    now[0] += 25 * HOUR
    tr.run_cycle()
    assert ":tada:" in client.posted[-1][1]
    now[0] += 25 * HOUR
    tr.run_cycle()
    assert len(client.posted) == 2


def test_poster_is_not_nagged():
    posted_at = NOON - 13 * HOUR
    client = FakeClient(messages=[ann(posted_at, user="U1")])
    tr = make_tracker(client, [NOON])
    tr.run_cycle()
    text = client.posted[0][1]
    assert "<@U1>" not in text.split("\n\n")[-1]
    assert "(0/2 done)" in text


def test_quiet_hours_delay_reminder():
    night = datetime(2026, 9, 30, 2, 0, tzinfo=ZoneInfo("America/Detroit")).timestamp()
    client = FakeClient(messages=[ann(night - 13 * HOUR)])
    now = [night]
    tr = make_tracker(client, now, quiet_hours_start=23, quiet_hours_end=9)
    tr.run_cycle()
    assert client.posted == []
    now[0] += 7 * HOUR  # 9am
    tr.run_cycle()
    assert len(client.posted) == 1


def test_dry_run_posts_nothing_and_records_nothing():
    client = FakeClient(messages=[ann(NOON - 13 * HOUR)])
    tr = make_tracker(client, [NOON], dry_run=True)
    assert len(tr.run_cycle()) == 1
    assert client.posted == []
    assert tr.store.get("C_ANN", f"{NOON - 13 * HOUR:.6f}").reminders_sent == 0


def test_dm_missing():
    client = FakeClient(messages=[ann(NOON - 13 * HOUR)])
    tr = make_tracker(client, [NOON], dm_missing=True)
    tr.run_cycle()
    assert {c for c, _ in client.posted} == {"C_SLACK", "U1", "U2", "U3"}


# ---- resolving names ----

def test_resolve_members_by_name_email_and_id():
    users = [
        {"id": "UAAAAAAA1", "name": "akaul", "profile": {"email": "adi@umich.edu", "display_name": "Adi", "real_name": "Adi Kaul"}},
        {"id": "UAAAAAAA2", "name": "bsmith", "profile": {"email": "b@umich.edu", "display_name": "", "real_name": "Ben Smith"}},
        {"id": "UAAAAAAA3", "name": "alex1", "profile": {"real_name": "Alex"}},
        {"id": "UAAAAAAA4", "name": "alex2", "profile": {"real_name": "Alex"}},
        {"id": "UBOT00001", "name": "bot", "is_bot": True, "profile": {"real_name": "Bot"}},
    ]
    resolved, unresolved = resolve_members(
        FakeClient(users=users),
        ["adi kaul", "B@UMICH.EDU", "@bsmith", "UAAAAAAA3", "Alex", "Nobody", "Bot"],
    )
    assert resolved == {"UAAAAAAA1": "Adi", "UAAAAAAA2": "Ben Smith", "UAAAAAAA3": "Alex"}
    assert unresolved == ["Alex", "Nobody", "Bot"]


def test_resolve_channel():
    client = FakeClient(channels=[{"id": "C0SLACKERS", "name": "slackers"}])
    assert resolve_channel(client, "#slackers") == "C0SLACKERS"
    assert resolve_channel(client, "C0ABCDEFG") == "C0ABCDEFG"
    with pytest.raises(ValueError):
        resolve_channel(client, "nope")


def test_format_status_lists_missing_names():
    from bot.main import format_status
    posted_at = NOON - HOUR
    client = FakeClient(messages=[ann(posted_at), ann(posted_at + 60, text="<!channel> second")],
                        reactions={f"{posted_at + 60:.6f}": [{"name": "scream", "users": ["U1", "U2", "U3"]}]})
    tr = make_tracker(client, [NOON])
    out = format_status(tr, tr.statuses())
    assert "0/3 reacted\n    Missing: u1, u2, u3" in out
    assert "3/3 reacted :white_check_mark:" in out
    assert client.posted == []
