# log-to-daily

A Claude Code skill that logs what you did, across **every Claude Code session on your machine inside a time window**, into one daily note (Obsidian or any Markdown folder).

Forked from `log-to-daily` in [daily-patterns-pack](https://github.com/aplaceforallmystuff/daily-patterns-pack) by Jim Christian (MIT). The original logs the current session into today's note; this version changes how sessions are picked.

## What's different from the original

| | Original | This version |
|---|---|---|
| Which conversations | The current session | Every session (any project) with messages inside the window |
| Which day | Today | Picked by message timestamps; you choose the window and the note's date, so work past midnight lands where you want |
| Session numbers | — | Numbered per day, continuing across runs; remembers where the last log stopped |
| Duplicates | — | Subagent logs skipped; messages copied by `/branch` or `/resume` counted once |
| Where the note is | `00 Daily/YYYY/YYYYMMDD.md` relative to the vault you run Claude in | An absolute path set once in `CLAUDE.md`, so it works from any project; falls back to the original default |
| Parsing | Done by the model | Two small Python scripts (standard library only) strip thinking and tool calls first |

## Install

```bash
git clone https://github.com/CSLing1016/log-to-daily ~/.claude/skills/log-to-daily
```

Requires Python 3 (standard library only).

## Configure

Add this to `~/.claude/CLAUDE.md`:

```markdown
## log-to-daily
- Daily note: /absolute/path/to/vault/Daily/{YYYY-MM-DD}.md
- Template: /absolute/path/to/vault/_Templates/Daily.md
```

- `Daily note` accepts `{YYYY-MM-DD}`, `{YYYY}`, `{MM}`, `{DD}`, `{YYYYMMDD}`.
- `Template` is optional. It is used only when the day's note doesn't exist yet; `{{date}}` is replaced with the diary date.
- Without the section, the skill uses `00 Daily/{YYYY}/{YYYYMMDD}.md` in the current directory, and asks you if that folder doesn't exist.

## Use

```text
/log-to-daily <start> [end] [diary date]
```

```text
/log-to-daily 08:00 now
/log-to-daily 2026-11-06 10:00 now 2026-11-06
```

Leave out the start time or the diary date and the skill asks, offering "continue from where the last log stopped".

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The skill |
| `scripts/collect-sessions.py` | Finds messages inside the window across `~/.claude/projects/**/*.jsonl` |
| `scripts/extract-session.py` | Parses one session log, keeping only user and assistant text |

The session counter lives in `~/.claude/sessions/.session-count.json`.

## License

MIT. See [LICENSE](LICENSE).
