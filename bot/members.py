"""Prints every human in the workspace so you can build the roster, and checks config.yaml's roster.

    python -m bot.members           # list everyone
    python -m bot.members --check   # show which config.yaml entries resolve and which don't
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from slack_sdk import WebClient

from .config import load_config
from .resolve import all_users, label_for, resolve_members


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)

    load_dotenv()
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("SLACK_BOT_TOKEN is not set (put it in .env)")
    client = WebClient(token=token)

    if args.check:
        cfg = load_config(args.config)
        resolved, unresolved = resolve_members(client, cfg.members)
        print(f"{len(resolved)} of {len(cfg.members)} roster entries found:")
        for uid, label in resolved.items():
            print(f"  ✓ {label:<30} {uid}")
        for entry in unresolved:
            print(f"  ✗ {entry}  (not found, or matches more than one person — try their email)")
        return 1 if unresolved else 0

    users = sorted(all_users(client), key=lambda u: label_for(u).lower())
    print(f"{'NAME':<30} {'EMAIL':<35} ID")
    for u in users:
        print(f"{label_for(u):<30} {(u.get('profile') or {}).get('email', ''):<35} {u['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
