# ReactTracker

A Slack bot for the club. It watches an announcements channel for `@channel` posts, checks which people on your roster reacted with 😱 (`:scream:`), and pings the ones who didn't in `#slackers`.

```
🚨 3 people still haven't reacted with :scream: to this announcement from @Adi (21/24 done)
> GBM moved to 8pm tonight, Room 1311 EECS

@alex @jordan @sam
```

- The first reminder goes out 12h after the post, then another every 24h, and it stops after 72h. Nothing is sent overnight (11pm–9am). You can change all of these in `config.yaml`.
- Each reminder only pings the people who still haven't reacted. Whoever posted the announcement isn't nagged.
- Once everyone has reacted, the bot posts a 🎉 and stops checking that announcement.
- `/reactcheck` shows you who's missing without pinging anyone, and `/reactcheck remind` pings them right away.
- The bot runs in Socket Mode, so you don't need a public URL or web server. Any computer that stays on can run it.

## Setup (about 10 minutes)

### 1. Create the Slack app

1. Go to <https://api.slack.com/apps>, click **Create New App**, choose **From a manifest**, and pick your club workspace.
2. Paste in the contents of [`manifest.yaml`](manifest.yaml), then click **Create**.
3. Go to **Basic Information → App-Level Tokens → Generate Token**. Add the `connections:write` scope and copy the token (`xapp-…`).
4. Go to **Install App → Install to Workspace**, then copy the **Bot User OAuth Token** (`xoxb-…`).
   - If your workspace requires admin approval, a club admin has to approve the app first.
5. In Slack, invite the bot to both channels by running `/invite @ReactTracker` in the announcements channel and in `#slackers`.

### 2. Configure

```bash
cd slack-react-tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                 # paste both tokens in
cp config.example.yaml config.yaml   # set channels + members
```

To fill in `members`, print everyone in the workspace:

```bash
python -m bot.members
```

Copy the 24 people into `config.yaml`, using their names, emails, or IDs. Then check that all of them are recognized:

```bash
python -m bot.members --check
```

If two people have the same name, the bot won't guess which one you meant. Use their email or ID instead.

### 3. Test it

**Option A: see who's missing, sending nothing.** This needs at least one `@channel` post in the channel from the last 72h:

```bash
python -m bot.main --status
```

**Option B: dry run.** This prints the reminder the bot would send, without posting it:

```bash
DRY_RUN=1 python -m bot.main --once --force
```

**Option C: live test with fast timing.** Make a `#bot-test` channel, invite the bot, and then:

```bash
cp config.test.example.yaml config.test.yaml   # put your own name in members
python -m bot.main --config config.test.yaml
```

Post `@channel test` in `#bot-test`. Within about a minute the bot pings you, and it pings you again every 3 minutes. React with 😱, and within 3 minutes you get the 🎉 instead. You can also run `/reactcheck` in Slack.

### 4. Run it for real

```bash
python -m bot.main
```

The bot only works while this command is running. For 24/7 uptime, deploy it to a host (see below).

## Deploying

The bot is one long-running Python process, with no ports and no web server. Any of these hosts works:

| Where | Cost | Notes |
|---|---|---|
| **Railway** | ~$5/mo | Easiest. Push the repo to GitHub, create a Railway project from it, and it builds the `Dockerfile`. |
| **Fly.io** | ~free–$2/mo | `fly launch` (with no HTTP service) and `fly secrets set …` |
| A spare laptop / Raspberry Pi | free | Run `python -m bot.main` inside `tmux`, or as a `launchd`/`systemd` service |

On a host, set these environment variables instead of using files:

- `SLACK_BOT_TOKEN`
- `SLACK_APP_TOKEN`
- `CONFIG_YAML`: paste the **entire contents** of your `config.yaml` here. `config.yaml` is gitignored, so the roster never ends up on GitHub.

Reminder history is stored in `tracker.db` (SQLite). Hosts often wipe local files when they redeploy. If that happens, the worst case is one extra reminder after the redeploy. To avoid it, mount a volume and set `db_path` to a file on that volume.

## Config reference

See [`config.example.yaml`](config.example.yaml); every option is commented. The ones you'll most likely change:

- `emojis`: which reactions count. Use `[scream, astonished, open_mouth]` to accept any "shocked" face.
- `first_reminder_after_hours`, `reminder_interval_hours`, `stop_after_hours`: the reminder schedule.
- `dm_missing: true`: also DM each person who hasn't reacted.
- `mentions: [channel, here]`: also track `@here` posts.

## Development

```bash
pip install pytest
pytest
```

Code layout:

- `bot/tracker.py`: all the logic
- `bot/main.py`: Slack wiring and the command-line interface
- `bot/resolve.py`: turns names into Slack IDs
- `bot/store.py`: SQLite storage
