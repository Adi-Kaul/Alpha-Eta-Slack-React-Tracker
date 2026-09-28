# Using Hannah Bot 3000

This page is for club officers and members: how the bot behaves day to day, and how to use it.

## The short version

1. An officer posts in the announcements channel and includes **`@channel`**.
2. Everyone on the roster reacts to that post with **😱** within **24 hours**.
3. The bot posts updates to **`#eta-slacker-alert`** that tag anyone who hasn't reacted yet.

## The timeline

For an announcement posted at 12:00pm with the default 24-hour deadline:

```
12:00 pm  📣 @channel announcement posted
12:00 am  📊 Halfway check     (12h in)    — tags everyone still missing
 8:00 am  ⚠️  4 hours left                   — tags everyone still missing
11:00 am  🚨 1 hour left                    — tags everyone still missing
12:00 pm  ⏰ Time's up!                     — lists everyone who never reacted
```

The bot always posts on this schedule, including overnight, because the deadline is the deadline. You can change the timing in [configuration.md](configuration.md).

Each message only tags the people who **still** haven't reacted. After you react, you won't be tagged again for that announcement.

If **everyone** reacts before the deadline, the bot posts a 🎉 and stops tracking that announcement. It skips the 🎉 if it never had to post about that announcement in the first place.

### What the messages look like

> 📊 **Halfway check:** 18/24 have reacted with 😱 to [this announcement] from @president. 12 hours left.
> > GBM moved to 8pm tonight, Room 1311 EECS
>
> **Still missing (6):** @alex @sam @jordan @taylor @riley @casey

> ⏰ **Time's up!** 2 people never reacted with 😱 to [this announcement] from @president (22/24 did).
> > GBM moved to 8pm tonight, Room 1311 EECS
>
> **Didn't react:** @sam @riley

Each message links to the announcement and quotes its first line, so it's clear which post it means.

## Commands

Anyone in the workspace can use these commands in any channel. `/reactcheck full` and `/reactcheck remind` also work.

### `/reactcheck`

Shows every announcement from the last 24 hours and who hasn't reacted yet. **Only you** can see the reply, and it doesn't ping anyone.

```
GBM moved to 8pm tonight… — 20/24 reacted, 6 hours left
    Missing: Alex Chen, Sam Patel, Jordan Lee, Riley Kim
Dues are due Friday… — 24/24 reacted, 18 hours left ✅
```

### `/reactcheck-full`

The same, plus everyone who *has* reacted and when, earliest first. Also only visible to you.

```
GBM moved to 8pm tonight… — 20/24 reacted, 6 hours left
✅ Reacted (20):
      • Sam Patel — Today 2:14 PM
      • Alex Chen — Today 2:31 PM
      • …
❌ Not yet (4): Jordan Lee, Riley Kim, Casey Park, Taylor Wu
```

Times show in your own timezone. How they're recorded:
- **Exact time:** the bot saw the reaction as it happened.
- **"by 2:35 PM":** the bot missed the live event and noticed the reaction on its next check, so it happened at or shortly before that time.
- **"before the bot was watching":** the reaction was already there when the bot started up, for example right after a redeploy, so the time is unknown.

### `/reactcheck-remind`

Posts a reminder to `#eta-slacker-alert` **right now** for every open announcement, tagging whoever hasn't reacted. Use it when you don't want to wait for the next scheduled post. It doesn't change the regular schedule.

## FAQ

**What counts as an announcement?**
A message posted directly in the watched channel that contains `@channel`. Messages with `@here` or `@everyone` don't count unless you turn them on with `mentions` in the config.

**Does `@channel` in a thread reply count?**
Only if the reply was also sent to the channel (the "Also send to #channel" checkbox). Thread-only replies are ignored.

**Do other emoji count, like 😮 or 🤯?**
No, only 😱 (`:scream:`). You can allow more emoji with the `emojis` config option.

**I reacted and then removed my reaction.**
The bot counts you as missing again, and you'll be tagged in the next update.

**Does the person who posted the announcement have to react?**
No. The poster is never tagged about their own announcement. You can change this with `exclude_poster`.

**What happens with two announcements at once?**
Each one has its own deadline and gets its own messages.

**What if the announcement gets deleted?**
The bot stops tracking it.

**What if someone edits a message later to add `@channel`?**
The bot starts tracking it on its next check. The 24-hour clock still counts from when the message was *originally* posted.

**What if the bot was offline for a while?**
When it comes back, it catches up, but it only posts the **most recent** message it missed. For example, if it was down through both the halfway check and the 4-hour warning, it posts one "X hours left" message instead of two in a row.

**Does someone on the roster need to be in the announcements channel?**
The bot doesn't check. If someone on the roster isn't in the channel, they can't see the announcement and will show up as missing.

**How do I add or remove people?**
Edit `members` in `config.yaml` (or the `CONFIG_YAML` variable on your host), then restart the bot. Run `python -m bot.members --check` first to catch typos.
