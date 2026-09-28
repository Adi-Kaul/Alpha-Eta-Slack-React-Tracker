# Deployment

The bot is a single long-running Python process. It connects out to Slack over a WebSocket (Socket Mode), so it doesn't need an open port, a domain, or a web server. Anything that can keep one command running 24/7 can host it.

> **Run only one copy at a time.** If two copies of the bot run at once, every message gets posted twice. Some hosts start two copies by default; the Fly.io section below shows how to prevent that.

## Which option?

| Option | Cost | Effort | Good for |
|---|---|---|---|
| [Railway](#railway) | ~$5/mo | Easiest | Set up once and forget about it |
| [Fly.io](#flyio) | ~$0–2/mo | Command line | Cheap, if you're comfortable in a terminal |
| [Always-on Mac](#always-on-mac-launchd) | Free | Medium | A computer that never sleeps |
| [Raspberry Pi / Linux box](#linux--raspberry-pi-systemd) | Free | Medium | A spare Pi or server |

## Preparing your config for a host

On a hosting platform, don't upload `config.yaml`. It's gitignored so your roster stays off GitHub. Instead, set three environment variables:

| Variable | Value |
|---|---|
| `SLACK_BOT_TOKEN` | `xoxb-…` |
| `SLACK_APP_TOKEN` | `xapp-…` |
| `CONFIG_YAML` | The entire contents of your `config.yaml` |

If a host's settings page doesn't accept multi-line values, convert the config to a single line. This works because YAML also accepts JSON:

```bash
python -c "import yaml, json; print(json.dumps(yaml.safe_load(open('config.yaml'))))"
```

Paste the output as `CONFIG_YAML`.

### Keeping reminder history across redeploys

The bot records which updates it has already sent in a small SQLite file (`db_path`, which defaults to `tracker.db`). Most hosts erase local files on every redeploy. If that happens, the bot may send one duplicate update for any announcement that's in progress when it restarts.

If that's acceptable, you can skip this. Otherwise, attach a persistent volume (disk), mount it at `/data`, and add this to your config:

```yaml
db_path: /data/tracker.db
```

---

## Railway

1. Sign in at <https://railway.com> with GitHub.
2. Click **New Project** → **Deploy from GitHub repo**, then pick `slack-react-tracker`. Railway finds the `Dockerfile` and builds it.
3. Open the service's **Variables** tab and add `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and `CONFIG_YAML`.
4. *(Optional)* To keep reminder history, add a **Volume** mounted at `/data`, and add `db_path: /data/tracker.db` to `CONFIG_YAML`.
5. Railway redeploys. Open **Deployments** → **View logs** and look for:
   ```
   Watching announcements, reminding in eta-slacker-alert, roster of 24
   ⚡️ Bolt app is running!
   ```

To update the roster, edit `CONFIG_YAML` in Railway, and it restarts automatically. When you push new code to GitHub, Railway redeploys on its own.

## Fly.io

Install the CLI (`brew install flyctl`), then run `fly auth login`. From the repo folder:

```bash
fly launch --no-deploy
```

When `fly launch` asks about databases or other extras, say **no** to all of them. Then open the generated `fly.toml` and **delete the whole `[http_service]` section**, because the bot doesn't serve web traffic.

Set your secrets and deploy with a single machine:

```bash
fly secrets set SLACK_BOT_TOKEN=xoxb-... SLACK_APP_TOKEN=xapp-... CONFIG_YAML="$(cat config.yaml)"
fly deploy --ha=false
fly logs
```

*(Optional)* To keep reminder history:

```bash
fly volumes create data --size 1
```

Then add this to `fly.toml`:

```toml
[mounts]
  source = "data"
  destination = "/data"
```

Also set `db_path: /data/tracker.db` in your config, then run `fly secrets set CONFIG_YAML="$(cat config.yaml)"` again.

## Always-on Mac (launchd)

This runs the bot in the background, starts it when you log in, and restarts it if it crashes. First finish [setup.md](setup.md) so that `python -m bot.main` works in the repo folder.

Create `~/Library/LaunchAgents/com.eta.reacttracker.plist`, replacing `/Users/YOU/slack-react-tracker` with your actual path:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.eta.reacttracker</string>
  <key>WorkingDirectory</key><string>/Users/YOU/slack-react-tracker</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/slack-react-tracker/.venv/bin/python</string>
    <string>-m</string>
    <string>bot.main</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/YOU/slack-react-tracker/bot.log</string>
  <key>StandardErrorPath</key><string>/Users/YOU/slack-react-tracker/bot.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.eta.reacttracker.plist     # start
tail -f ~/slack-react-tracker/bot.log                                  # watch logs
launchctl unload ~/Library/LaunchAgents/com.eta.reacttracker.plist   # stop
```

To restart after editing `config.yaml`, run `unload` and then `load`.

The bot stops while your Mac is asleep. To keep it running, turn on **System Settings → Battery → Options → Prevent automatic sleeping when the display is off** (on a laptop, this only works while it's plugged in).

## Linux / Raspberry Pi (systemd)

After finishing [setup.md](setup.md) on the machine, create `/etc/systemd/system/reacttracker.service`:

```ini
[Unit]
Description=ReactTracker Slack bot
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/slack-react-tracker
ExecStart=/home/pi/slack-react-tracker/.venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now reacttracker   # start now and on every boot
journalctl -u reacttracker -f              # watch logs
sudo systemctl restart reacttracker        # after editing config.yaml
```

## Docker (any host)

```bash
docker build -t reacttracker .
docker run -d --restart unless-stopped --name reacttracker \
  -e SLACK_BOT_TOKEN=xoxb-... -e SLACK_APP_TOKEN=xapp-... \
  -e CONFIG_YAML="$(cat config.yaml)" \
  -v reacttracker-data:/data \
  reacttracker
```

If you use the volume, set `db_path: /data/tracker.db` in your config.
