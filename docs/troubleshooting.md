# Troubleshooting

Start with the bot's logs. Locally, they're in the terminal where the bot is running. On a host, check its log viewer (see [deployment.md](deployment.md)). Most problems show up there with a clear error.

## Startup errors

**`SLACK_BOT_TOKEN is not set`**
The bot didn't find a `.env` file in the folder you ran it from, or the variable isn't set on your host. Run the bot from the repo folder, or set the variable.

**`Slack rejected the startup checks: invalid_auth`**
The bot token is wrong or was revoked. Copy the token again from **Install App** in your app's settings. Make sure you used the `xoxb-` token there, not the `xapp-` one.

**`Slack rejected the startup checks: missing_scope`**
The app is missing a permission. Usually the manifest was changed after the app was installed. Go to **Install App** → **Reinstall to Workspace**.

**`Channel #something not found`**
- Check the spelling of `watch_channel` / `reminder_channel`. Leave out the `#`, or keep it; both work.
- For **private** channels, the bot has to be invited before it can see them. Run `/invite @ReactTracker` in the channel.
- If you still can't find the problem, use the channel ID instead. In Slack, open the channel details and the ID (`C…`) is at the bottom.

**`Unknown keys in config.yaml: ...`**
There's a typo in a setting name. Compare against [configuration.md](configuration.md).

**`Could not find these roster entries in Slack (skipping them): ...`**
Those people won't be tracked. Run `python -m bot.members --check` to see which entries are the problem. The usual causes:
- They use a different email for Slack than the one you have.
- Two people share that name.
- They haven't joined the workspace yet.

Use their email or user ID from `python -m bot.members` instead.

## Runtime problems

**`Slack API error during check: not_in_channel`**
The bot isn't a member of the announcements channel. Run `/invite @ReactTracker` there.

**The bot never posts anything**
Check each of these in order:
1. Is it running? Look for `Bolt app is running!` in the logs.
2. Did the announcement actually contain `@channel`? `@here` and `@everyone` don't count unless you add them to `mentions`.
3. Is it too early? The first update comes at the **halfway** point, which is 12 hours after the post by default. Run `/reactcheck` to see the countdown.
4. Has everyone already reacted? Then there's nothing to post.
5. Was the announcement posted inside a thread? Thread-only replies are ignored.
6. Is `dry_run` on? If so, messages go to the logs instead of Slack.
7. Is the bot a member of `#eta-slacker-alert`? It has to be invited there too.

**Every message is posted twice**
Two copies of the bot are running. Examples: your laptop and a host at the same time, or a host running two instances. Stop one. On Fly.io, run `fly scale count 1`.

**`/reactcheck` says "dispatch_failed" or "didn't respond"**
The bot isn't running, or it's connected with an `xapp-` token from a different app. Start the bot and check that `SLACK_APP_TOKEN` belongs to this app.

**Someone reacted but still gets tagged**
- Check that they used 😱 `:scream:`, not a lookalike such as 😨 `:fearful:` or 😮 `:open_mouth:`. You can accept more emoji with `emojis`.
- Check that they reacted to the announcement itself, not to a reply in its thread.
- Make sure the roster entry resolved to the right person with `python -m bot.members --check`. Two people with similar names could be swapped.

**Someone got a duplicate update after a restart**
The bot's history file was wiped. This is normal on hosts without a volume. See "Keeping reminder history across redeploys" in [deployment.md](deployment.md).

## Still stuck?

Run a single check with full output:

```bash
python -m bot.main --status
DRY_RUN=1 python -m bot.main --once --force
```

The first command shows exactly what the bot sees. The second shows exactly what it would post.
