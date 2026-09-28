# ReactTracker

A Slack bot for the club. It watches an announcements channel for `@channel` posts, checks which people on your roster have reacted with 😱 (`:scream:`), and calls out the people who haven't in `#eta-slacker-alert`.

Everyone has 24 hours from the post to react. During that time, the bot posts these to `#eta-slacker-alert`, each one tagging only the people who still haven't reacted:

| When | Message |
|---|---|
| Halfway (12h) | 📊 *Halfway check:* 18/24 have reacted to this announcement. 12 hours left. *Still missing (6):* @alex @sam … |
| 4 hours left | ⚠️ *4 hours left* to react (21/24 done). *Still missing (3):* … |
| 1 hour left | 🚨 *1 hour left* to react (23/24 done). *Still missing (1):* … |
| Deadline | ⏰ *Time's up!* 1 person never reacted (23/24 did). *Didn't react:* @sam |

Other behavior:

- If everyone reacts early, the bot posts a 🎉 and stops. It stays quiet if it hasn't sent a reminder yet.
- Whoever posted the announcement isn't nagged.
- `/reactcheck` shows who's missing and how long is left, without pinging anyone.
- `/reactcheck remind` pings the missing people right away.
- If the bot was offline and missed some checkpoints, it posts only the most recent one instead of all of them at once.
- The deadline, the warning times, and the emoji are all set in `config.yaml`.
- The bot runs in Socket Mode, so there's no web server or public URL. Any computer that stays on can run it.

## Setup (about 10 minutes)

### 1. Create the Slack app

1. Go to <https://api.slack.com/apps>, click **Create New App**, choose **From a manifest**, and pick your club workspace.
2. Paste in the contents of [`manifest.yaml`](manifest.yaml), then click **Create**.
3. Go to **Basic Information → App-Level Tokens → Generate Token**. Add the `connections:write` scope and copy the token (`xapp-…`).
4. Go to **Install App → Install to Workspace**, then copy the **Bot User OAuth Token** (`xoxb-…`).
   - If your workspace requires admin approval, a club admin has to approve the app first.
5. In Slack, invite the bot to both channels by running `/invite @ReactTracker` in the announcements channel and in `#eta-slacker-alert`.

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

**Option A: see who's missing, sending nothing.** This needs at least one `@channel` post in the channel from the last 24h:

```bash
python -m bot.main --status
```

**Option B: dry run.** This prints a reminder the bot would send, without posting it:

```bash
DRY_RUN=1 python -m bot.main --once --force
```

**Option C: live test of the whole schedule, squeezed into 15 minutes.** Make a `#bot-test` channel, invite the bot, and then:

```bash
cp config.test.example.yaml config.test.yaml   # put your own email in members
python -m bot.main --config config.test.yaml
```

Post `@channel test` in `#bot-test` and don't react to it. After about 7.5 minutes you get the halfway report, then warnings at 5 minutes and 2 minutes left, then the "Time's up" at 15 minutes. Do it again and react with 😱 partway through to see the 🎉.

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

- `deadline_hours`: how long people have to react (default 24).
- `warn_hours_before`: when to send the countdown warnings (default `[4, 1]`).
- `halfway_report`, `final_report`: turn those posts on or off.
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
