"""Turns human-friendly names in config (channel names, member names/emails) into Slack IDs."""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{6,}$")
CHANNEL_ID_RE = re.compile(r"^[CGD][A-Z0-9]{6,}$")


def _paginate(method, key: str, **kwargs):
    cursor = None
    while True:
        resp = method(cursor=cursor, limit=200, **kwargs)
        yield from resp[key]
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return


def all_users(client) -> list[dict]:
    return [
        u
        for u in _paginate(client.users_list, "members")
        if not u.get("deleted") and not u.get("is_bot") and u.get("id") != "USLACKBOT"
    ]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lstrip("@").lower())


def label_for(user: dict | None) -> str:
    if not user:
        return ""
    p = user.get("profile") or {}
    return p.get("display_name") or p.get("real_name") or user.get("name") or user["id"]


def resolve_members(client, entries: list[str]) -> tuple[dict[str, str], list[str]]:
    """Returns ({user_id: label}, [unresolved entries]).

    An entry matches a user by ID, email, display name, real name, or handle (case-insensitive).
    Ambiguous names (two people called "Alex") are reported as unresolved rather than guessed.
    """
    users = all_users(client)
    by_id = {u["id"]: u for u in users}
    index: dict[str, set[str]] = {}
    for u in users:
        p = u.get("profile") or {}
        for key in (p.get("email"), p.get("display_name"), p.get("real_name"), u.get("name")):
            if key:
                index.setdefault(_norm(key), set()).add(u["id"])

    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for entry in entries:
        ids = {entry} if USER_ID_RE.match(entry) else index.get(_norm(entry), set())
        if len(ids) == 1:
            uid = next(iter(ids))
            resolved[uid] = label_for(by_id.get(uid)) or entry
        else:
            if len(ids) > 1:
                log.warning("Roster entry %r matches %d people; use an email or ID", entry, len(ids))
            unresolved.append(entry)
    return resolved, unresolved


def resolve_channel(client, name_or_id: str) -> str:
    name = name_or_id.lstrip("#")
    if CHANNEL_ID_RE.match(name):
        return name
    for ch in _paginate(
        client.conversations_list, "channels",
        types="public_channel,private_channel", exclude_archived=True,
    ):
        if ch["name"] == name:
            return ch["id"]
    raise ValueError(
        f"Channel #{name} not found. If it's private, invite the bot to it first (/invite @Hannah Bot 3000)."
    )
