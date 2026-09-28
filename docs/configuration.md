# Configuration reference

The bot looks for its settings in this order:

1. The `--config` flag: `python -m bot.main --config path/to/file.yaml`
2. The `CONFIG_YAML` environment variable, which holds the whole YAML file as text. Use this on hosting platforms.
3. The file named by the `CONFIG_PATH` environment variable.
4. `config.yaml` in the current directory.

Unknown keys are rejected at startup. A typo like `emoji:` instead of `emojis:` stops the bot with an error instead of being silently ignored.

## Channels and people

| Key | Default | Description |
|---|---|---|
| `watch_channel` | *(required)* | The channel with the `@channel` announcements. Use its name (`announcements` or `#announcements`) or its ID (`C0123ABCD`). |
| `reminder_channel` | *(required)* | Where the bot posts its updates. The example config uses `eta-slacker-alert`. |
| `members` | *(required)* | The people who must react. Each entry can be an email, a Slack user ID, a display name, a full name, or a username. Matching ignores upper/lowercase. |
| `exclude_poster` | `true` | Don't tag the person who posted the announcement. |

## What gets tracked

| Key | Default | Description |
|---|---|---|
| `emojis` | `[scream]` | Which reactions count, written without colons. Any one of them counts. Skin-tone variants are included automatically. |
| `mentions` | `[channel]` | Which broadcasts mark a post as an announcement: `channel`, `here`, `everyone`. |

## Schedule

| Key | Default | Description |
|---|---|---|
| `deadline_hours` | `24` | How long people have to react, counted from when the announcement was posted. Fractions work (`0.5` = 30 minutes). |
| `halfway_report` | `true` | Post a status update at the halfway point. |
| `warn_hours_before` | `[4, 1]` | Post a warning this many hours before the deadline. Add as many as you like, such as `[12, 4, 1]`, or use `[]` for none. A warning that would land before the post was made is skipped. |
| `final_report` | `true` | At the deadline, post a list of everyone who never reacted. |
| `check_interval_minutes` | `5` | How often the bot checks Slack. Messages can arrive up to this late. |

With the defaults, the schedule is:

| Hours after post | Message |
|---|---|
| 12 | Halfway check |
| 20 | 4 hours left |
| 23 | 1 hour left |
| 24 | Time's up |

## Other options

| Key | Default | Description |
|---|---|---|
| `dm_missing` | `false` | Also DM each missing person on every update except the final one. |
| `announce_completion` | `true` | Post 🎉 when everyone has reacted, but only if the bot already posted about that announcement. |
| `dry_run` | `false` | Log messages instead of posting them. You can also turn this on with the `DRY_RUN=1` environment variable. |
| `db_path` | `tracker.db` | SQLite file where the bot remembers which updates it already sent. |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | yes | The `xoxb-…` token from **Install App**. |
| `SLACK_APP_TOKEN` | yes, to run the bot continuously | The `xapp-…` token with the `connections:write` scope. It isn't needed for `--status`, `--once`, or `bot.members`. |
| `CONFIG_YAML` | no | The whole config file as text. |
| `CONFIG_PATH` | no | Path to the config file. |
| `DRY_RUN` | no | `1` to log messages instead of posting them. |

When running locally, put these in a `.env` file. They load automatically.

## Full example

```yaml
watch_channel: announcements
reminder_channel: eta-slacker-alert
emojis: [scream]
members:
  - alex@umich.edu
  - sam@umich.edu
mentions: [channel]
deadline_hours: 24
halfway_report: true
warn_hours_before: [4, 1]
final_report: true
check_interval_minutes: 5
exclude_poster: true
dm_missing: false
announce_completion: true
dry_run: false
db_path: tracker.db
```
