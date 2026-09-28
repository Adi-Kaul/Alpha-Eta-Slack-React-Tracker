from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bot.config import Config
from bot.resolve import resolve_channel, resolve_members
from bot.store import Store
from bot.tracker import Tracker, checkpoints, fmt_duration, is_announcement, reacted_users, snippet

HOUR = 3600
NOON = datetime(2026, 9, 30, 12, 0, tzinfo=ZoneInfo("America/Detroit")).timestamp()


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
    base = dict(watch_channel="C_ANN", reminder_channel="C_SLACK", members=["x"])
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


def test_checkpoints_default_schedule():
    cfg = make_cfg()  # 24h deadline, halfway, 4h + 1h warnings, final
    t0 = 1_000_000.0
    assert checkpoints(cfg, t0) == [
        ("halfway", t0 + 12 * HOUR), ("warn:4", t0 + 20 * HOUR),
        ("warn:1", t0 + 23 * HOUR), ("deadline", t0 + 24 * HOUR),
    ]


def test_checkpoints_drop_warnings_before_post():
    cfg = make_cfg(deadline_hours=3)  # 4h warning can't happen; 1h warning lands after halfway
    assert [k for k, _ in checkpoints(cfg, 0)] == ["halfway", "warn:1", "deadline"]


def test_fmt_duration():
    assert fmt_duration(4) == "4 hours"
    assert fmt_duration(1) == "1 hour"
    assert fmt_duration(1.5) == "1 hour 30 min"
    assert fmt_duration(0.25) == "15 min"


# ---- full cycle ----

def run_at(tr, now, t):
    now[0] = t
    return tr.run_cycle()


def test_full_schedule_pings_only_missing_people():
    t0 = NOON
    ts = f"{t0:.6f}"
    client = FakeClient(messages=[ann(t0), {"ts": f"{t0 + 5:.6f}", "text": "normal msg"}],
                        reactions={ts: [{"name": "scream", "users": ["U1"]}]})
    now = [t0]
    tr = make_tracker(client, now)

    run_at(tr, now, t0 + 1 * HOUR)
    assert client.posted == []  # nothing due yet

    run_at(tr, now, t0 + 12 * HOUR)
    ch, text = client.posted[-1]
    assert ch == "C_SLACK"
    assert "Halfway check" in text and "1/3" in text and "12 hours left" in text
    assert "*Still missing (2):* <@U2> <@U3>" in text
    assert "meeting tonight at 7" in text

    run_at(tr, now, t0 + 12.1 * HOUR)
    assert len(client.posted) == 1  # halfway not repeated

    client.reactions[ts].append({"name": "scream", "users": ["U2"]})
    run_at(tr, now, t0 + 20 * HOUR)
    assert ":warning: *4 hours left*" in client.posted[-1][1]
    assert "<@U3>" in client.posted[-1][1] and "<@U2>" not in client.posted[-1][1]

    run_at(tr, now, t0 + 23 * HOUR)
    assert ":rotating_light: *1 hour left*" in client.posted[-1][1]

    run_at(tr, now, t0 + 24 * HOUR)
    assert "Time's up!" in client.posted[-1][1]
    assert "*Didn't react:* <@U3>" in client.posted[-1][1]
    assert len(client.posted) == 4

    run_at(tr, now, t0 + 25 * HOUR)
    assert len(client.posted) == 4


def test_missed_checkpoints_only_post_latest():
    t0 = NOON
    client = FakeClient(messages=[ann(t0)])
    now = [t0]
    tr = make_tracker(client, now)
    run_at(tr, now, t0 + 21 * HOUR)  # bot was down through halfway and the 4h warning
    assert len(client.posted) == 1 and "4 hours" not in client.posted[0][1]
    assert "3 hours left" in client.posted[0][1]
    run_at(tr, now, t0 + 21.5 * HOUR)
    assert len(client.posted) == 1


def test_force_posts_now_without_touching_schedule():
    client = FakeClient(messages=[ann(NOON)])
    now = [NOON]
    tr = make_tracker(client, now)
    now[0] = NOON + 60
    assert len(tr.run_cycle(force=True)) == 1
    assert ":mega: *Reminder:*" in client.posted[0][1]
    run_at(tr, now, NOON + 12 * HOUR)
    assert "Halfway" in client.posted[-1][1]


def test_completion_celebrated_once_then_stops():
    ts = f"{NOON:.6f}"
    client = FakeClient(messages=[ann(NOON)], reactions={ts: []})
    now = [NOON]
    tr = make_tracker(client, now)
    run_at(tr, now, NOON + 12 * HOUR)  # halfway
    client.reactions[ts] = [{"name": "scream", "users": ["U1", "U2", "U3"]}]
    run_at(tr, now, NOON + 13 * HOUR)
    assert ":tada:" in client.posted[-1][1]
    run_at(tr, now, NOON + 23 * HOUR)
    assert len(client.posted) == 2


def test_no_celebration_if_nobody_was_reminded():
    ts = f"{NOON:.6f}"
    client = FakeClient(messages=[ann(NOON)], reactions={ts: [{"name": "scream", "users": ["U1", "U2", "U3"]}]})
    tr = make_tracker(client, [NOON + HOUR])
    tr.run_cycle()
    assert client.posted == []


def test_poster_is_not_nagged():
    client = FakeClient(messages=[ann(NOON, user="U1")])
    tr = make_tracker(client, [NOON + 12 * HOUR])
    tr.run_cycle()
    text = client.posted[0][1]
    assert "*Still missing (2):* <@U2> <@U3>" in text
    assert "0/2" in text


def test_dry_run_posts_nothing_and_records_nothing():
    client = FakeClient(messages=[ann(NOON)])
    tr = make_tracker(client, [NOON + 12 * HOUR], dry_run=True)
    assert len(tr.run_cycle()) == 1
    assert client.posted == []
    assert tr.store.get("C_ANN", f"{NOON:.6f}").sent == set()


def test_dm_missing():
    client = FakeClient(messages=[ann(NOON)])
    tr = make_tracker(client, [NOON + 12 * HOUR], dm_missing=True)
    tr.run_cycle()
    assert {c for c, _ in client.posted} == {"C_SLACK", "U1", "U2", "U3"}


def test_format_status_lists_missing_names():
    from bot.main import format_status
    posted_at = NOON - HOUR
    client = FakeClient(messages=[ann(posted_at), ann(posted_at + 60, text="<!channel> second")],
                        reactions={f"{posted_at + 60:.6f}": [{"name": "scream", "users": ["U1", "U2", "U3"]}]})
    tr = make_tracker(client, [NOON])
    out = format_status(tr, tr.statuses())
    assert "0/3 reacted, 23 hours left\n    Missing: u1, u2, u3" in out
    assert "3/3 reacted, 23 hours 1 min left :white_check_mark:" in out
    assert client.posted == []


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

