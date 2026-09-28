# Setup guide

This guide takes you from nothing to a working bot in your Slack. It takes about 15 minutes.

**What you need**
- A Mac, Linux, or Windows computer with **Python 3.10 or newer**. Check with `python3 --version`.
- Permission to install apps in your Slack workspace. If you don't have it, a workspace admin can approve the app for you.
- The emails of the people who need to react.

---

## 1. Create the Slack app

1. Open <https://api.slack.com/apps> and click **Create New App** → **From a manifest**.
2. Pick your club's workspace and click **Next**.
3. Choose the **YAML** tab. Delete what's there and paste in the entire contents of [`manifest.yaml`](../manifest.yaml).
4. Click **Next**, then **Create**.

The manifest sets up everything the bot needs: its name, the `/reactcheck` command, Socket Mode, and these permissions:

| Permission | Why the bot needs it |
|---|---|
| `channels:history`, `groups:history` | To read `@channel` posts in the announcements channel |
| `channels:read`, `groups:read` | To find channels by name |
| `reactions:read` | To see who reacted with 😱 |
| `chat:write` | To post reminders |
| `users:read`, `users:read.email` | To match the emails in your roster to Slack accounts |
| `im:write` | To send DMs, which are optional and off by default |
| `commands` | For `/reactcheck` |

## 2. Get the two tokens

The bot needs two secret tokens. Treat them like passwords, and never commit them or paste them in Slack.

**App token (`xapp-…`)**
1. In your app's settings, go to **Basic Information**, scroll to **App-Level Tokens**, and click **Generate Token and Scopes**.
2. Name it anything (for example, `socket`), add the `connections:write` scope, and click **Generate**.
3. Copy the token.

**Bot token (`xoxb-…`)**
1. Go to **Install App** → **Install to Workspace** → **Allow**.
   - If Slack says the app needs approval, ask a workspace admin to approve it, then come back to this step.
2. Copy the **Bot User OAuth Token**.

## 3. Invite the bot to your channels

In Slack, run this in **both** the announcements channel and `#eta-slacker-alert`:

```
/invite @ReactTracker
```

The bot can only read the announcements channel and post in the alert channel if it's a member of both.

## 4. Install the code

```bash
git clone https://github.com/Adi-Kaul/slack-react-tracker.git
cd slack-react-tracker

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Next, save your tokens:

```bash
cp .env.example .env
```

Open `.env` and paste in your tokens:

```
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token
```

`.env` is gitignored, so it won't be committed.

## 5. Configure the roster and channels

```bash
cp config.example.yaml config.yaml
```

Open `config.yaml` and set these three things:

```yaml
watch_channel: announcements        # where the @channel posts go
reminder_channel: eta-slacker-alert  # where the bot posts callouts
members:                            # everyone who must react
  - alex@umich.edu
  - sam@umich.edu
  # ...
```

For `members`, emails work best. You can also use someone's Slack name or their user ID (like `U0123ABCD`).

If you don't know people's emails or IDs, print everyone in the workspace:

```bash
python -m bot.members
```

```
NAME                           EMAIL                               ID
Alex Chen                      alex@umich.edu                      U01ABCDEF
Sam Patel                      sam@umich.edu                       U01GHIJKL
...
```

Then check that every entry in your roster matches exactly one person:

```bash
python -m bot.members --check
```

```
23 of 24 roster entries found:
  ✓ Alex Chen                      U01ABCDEF
  ...
  ✗ jordan@gmail.com  (not found, or matches more than one person — try their email)
```

Fix any line marked ✗ before going live. The usual causes are:
- A typo.
- The person signed up for Slack with a different email.
- Two people have the same name.

The bot skips entries it can't match, so a ✗ person won't be tracked.

`config.yaml` is gitignored, so your roster never ends up on GitHub.

## 6. Test it

Pick whichever test you like. None of them bother anyone except Option C, which only pings you.

### Option A: status check (sends nothing)

This shows who has and hasn't reacted to `@channel` posts from the last 24 hours:

```bash
python -m bot.main --status
```

### Option B: dry run (sends nothing)

This prints the reminder the bot *would* post right now:

```bash
DRY_RUN=1 python -m bot.main --once --force
```

### Option C: the full schedule in 15 minutes

This is the best way to see exactly what everyone will get.

1. Create a channel called `#bot-test` and `/invite @ReactTracker` to it.
2. Make the test config:
   ```bash
   cp config.test.example.yaml config.test.yaml
   ```
   Open `config.test.yaml` and put **your own email** under `members`.
3. Run the bot with it:
   ```bash
   python -m bot.main --config config.test.yaml
   ```
4. In `#bot-test`, post `@channel test` and **don't react**.

What you'll see in `#bot-test`:

| Time after post | Message |
|---|---|
| ~7.5 min | 📊 Halfway check |
| ~10 min | ⚠️ 5 min left |
| ~13 min | 🚨 2 min left |
| 15 min | ⏰ Time's up! |

Post another `@channel test`, wait for the halfway check, and then react with 😱. Within 30 seconds you should get a 🎉.

Press `Ctrl+C` to stop the bot.

## 7. Go live

```bash
python -m bot.main
```

The bot works for as long as this command keeps running. If you close the terminal or your laptop goes to sleep, the bot stops. To keep it running all the time, see [deployment.md](deployment.md).
