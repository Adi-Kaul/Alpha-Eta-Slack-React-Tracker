# ReactTracker 😱

A Slack bot that makes sure everyone actually reads `@channel` announcements.

When someone posts an `@channel` announcement, everyone on the roster has **24 hours** to react with 😱. The bot keeps track of who has, and posts countdown updates to **`#eta-slacker-alert`** that tag everyone who hasn't yet. When time runs out, it posts a list of anyone who never reacted.

| When | What gets posted in `#eta-slacker-alert` |
|---|---|
| Halfway (12h) | 📊 **Halfway check:** 18/24 have reacted. 12 hours left. **Still missing (6):** @alex @sam … |
| 4 hours left | ⚠️ **4 hours left** to react (21/24 done). **Still missing (3):** … |
| 1 hour left | 🚨 **1 hour left** to react (23/24 done). **Still missing (1):** … |
| Deadline | ⏰ **Time's up!** 1 person never reacted (23/24 did). **Didn't react:** @sam |
| Everyone reacted early | 🎉 Everyone reacted. Thanks all! |

It also adds two slash commands:
- `/reactcheck` shows who's missing and how much time is left. Only you can see the reply.
- `/reactcheck remind` tags everyone who's missing right away.

## Quick start

```bash
git clone https://github.com/Adi-Kaul/slack-react-tracker.git && cd slack-react-tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                 # add your Slack tokens
cp config.example.yaml config.yaml   # add channels + roster emails
python -m bot.members --check        # confirm everyone on the roster was found
python -m bot.main                   # run it
```

You'll need to create the Slack app first. It takes a few minutes with the included manifest. See the **[setup guide](docs/setup.md)**.

## Documentation

| Guide | For |
|---|---|
| **[Setup](docs/setup.md)** | Creating the Slack app, getting tokens, building the roster, testing it with a 15-minute schedule |
| **[Using the bot](docs/usage.md)** | How the bot behaves, the slash commands, and an FAQ for club members |
| **[Configuration](docs/configuration.md)** | Every setting: deadline, warning times, emoji, DMs, and more |
| **[Deployment](docs/deployment.md)** | Running it 24/7 on Railway, Fly.io, a Mac, a Raspberry Pi, or Docker |
| **[Troubleshooting](docs/troubleshooting.md)** | Error messages and what to do about them |
| **[How it works](docs/how-it-works.md)** | Architecture, code layout, tests, and ideas for extending it |

## Features

- **Countdown schedule.** Updates go out at the halfway point and at 4 hours and 1 hour before the deadline, followed by a final list of who never reacted. All of these can be changed.
- **Only tags people who haven't reacted.** Once you react, you won't be tagged again for that announcement.
- **Flexible roster.** List people by email, Slack name, or user ID. `python -m bot.members --check` catches typos and duplicate names before you go live.
- **Survives restarts.** It remembers which updates it already sent. If it was offline, it catches up without flooding the channel.
- **No web server.** It runs in Socket Mode, so it works on a laptop, a Raspberry Pi, or a ~$5/mo host.
- **Roster stays private.** `config.yaml` and `.env` are gitignored.

## Development

```bash
pip install pytest && pytest
```

The tests run without Slack, using a fake Slack client and a fake clock. See [how it works](docs/how-it-works.md).
