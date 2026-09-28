"""Runs the bot: a background loop that checks announcements + a /reactcheck slash command.

    python -m bot.main            # run forever (Socket Mode)
    python -m bot.main --once     # run one check cycle and exit (good for testing)
    python -m bot.main --status   # print who's missing for recent announcements and exit
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import Config, load_config
from .resolve import resolve_channel, resolve_members
from .store import Store
from .tracker import Status, Tracker, snippet

log = logging.getLogger("reacttracker")


def build_tracker(cfg: Config, client: WebClient) -> Tracker:
    watch = resolve_channel(client, cfg.watch_channel)
    remind = resolve_channel(client, cfg.reminder_channel)
    roster, unresolved = resolve_members(client, cfg.members)
    log.info("Watching %s, reminding in %s, roster of %d", cfg.watch_channel, cfg.reminder_channel, len(roster))
    if unresolved:
        log.warning("Could not find these roster entries in Slack (skipping them): %s", ", ".join(unresolved))
    return Tracker(client, cfg, Store(cfg.db_path), watch, remind, roster)


def format_status(tracker: Tracker, statuses: list[Status]) -> str:
    if not statuses:
        return f"No @channel announcements in the last {tracker.cfg.stop_after_hours:g}h."
    lines = []
    for st in statuses:
        total = tracker.expected_count(st)
        head = f"*<{st.permalink}|{snippet(st.text, 60) or 'announcement'}>* — {total - len(st.missing)}/{total} reacted"
        if st.missing:
            names = ", ".join(tracker.roster[u] for u in st.missing)
            lines.append(f"{head}\n    Missing: {names}")
        else:
            lines.append(f"{head} :white_check_mark:")
    return "\n".join(lines)


def check_loop(tracker: Tracker, stop: threading.Event) -> None:
    interval = tracker.cfg.check_interval_minutes * 60
    while not stop.is_set():
        try:
            sent = tracker.run_cycle()
            if sent:
                log.info("Sent %d reminder(s)", len(sent))
        except SlackApiError as e:
            err = e.response.get("error")
            hint = " — invite the bot to the channel with /invite" if err == "not_in_channel" else ""
            log.error("Slack API error during check: %s%s", err, hint)
        except Exception:
            log.exception("Check cycle failed")
        stop.wait(interval)


def register_commands(app: App, tracker: Tracker) -> None:
    @app.command("/reactcheck")
    def reactcheck(ack, command, respond):
        ack()
        arg = (command.get("text") or "").strip().lower()
        try:
            if arg == "remind":
                sent = tracker.run_cycle(force=True)
                respond(f"Sent {len(sent)} reminder(s) to <#{tracker.reminder_channel}>." if sent
                        else "Nothing to remind — everyone's reacted (or there are no recent announcements).")
            elif arg in ("", "status"):
                respond(format_status(tracker, tracker.statuses()))
            else:
                respond("Usage: `/reactcheck` (see who's missing) or `/reactcheck remind` (ping them now)")
        except Exception as e:
            log.exception("/reactcheck failed")
            respond(f"Something went wrong: {e}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--once", action="store_true", help="run one check cycle and exit")
    parser.add_argument("--force", action="store_true", help="with --once: remind now, ignoring the schedule")
    parser.add_argument("--status", action="store_true", help="print status and exit")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    if not cfg.bot_token:
        sys.exit("SLACK_BOT_TOKEN is not set (put it in .env)")

    client = WebClient(token=cfg.bot_token)
    try:
        tracker = build_tracker(cfg, client)
    except SlackApiError as e:
        sys.exit(f"Slack rejected the startup checks: {e.response.get('error')} "
                 "(check SLACK_BOT_TOKEN and that the app is installed with the manifest's scopes)")
    except ValueError as e:
        sys.exit(str(e))

    if args.status:
        print(format_status(tracker, tracker.statuses()))
        return 0
    if args.once:
        sent = tracker.run_cycle(force=args.force)
        print(f"Sent {len(sent)} reminder(s){' (dry run)' if cfg.dry_run else ''}.")
        return 0

    if not cfg.app_token:
        sys.exit("SLACK_APP_TOKEN is not set (needed for Socket Mode; put it in .env)")
    app = App(token=cfg.bot_token)
    register_commands(app, tracker)

    stop = threading.Event()
    threading.Thread(target=check_loop, args=(tracker, stop), daemon=True).start()
    try:
        SocketModeHandler(app, cfg.app_token).start()
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
