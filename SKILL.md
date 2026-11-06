---
name: log-to-daily
description: Log Claude Code activity inside a chosen time window, across all projects on this machine, to a chosen daily note on demand. Use when wrapping up work, capturing decisions, or documenting session outcomes. All sessions append to the same daily note with session numbering.
argument-hint: "[start YYYY-MM-DD HH:MM] [end YYYY-MM-DD HH:MM | now] [diary date YYYY-MM-DD]"
user-invocable: true
disable-model-invocation: true
---

<objective>
Append a structured summary of **every Claude Code message inside a time window** (start → end) to the daily note of a chosen date. Sessions are picked by message timestamps, not file modification dates, so work that runs past midnight is logged by when it happened, and sessions from every project on this machine land in the same note. Session extraction uses `collect-sessions.py` (wraps `extract-session.py`) to parse the JSONL session logs (stripping thinking/tool_use), then appends a synthesized summary with session numbers.
</objective>

<configuration>
Read the user's settings from a `## log-to-daily` section in `~/.claude/CLAUDE.md` (or the project's `CLAUDE.md`):

```markdown
## log-to-daily
- Daily note: /absolute/path/to/vault/Daily/{YYYY-MM-DD}.md
- Template: /absolute/path/to/vault/_Templates/Daily.md
```

| Setting | Meaning | If missing |
|---|---|---|
| `Daily note` | Where each day's note lives. `{YYYY-MM-DD}`, `{YYYY}`, `{MM}`, `{DD}`, `{YYYYMMDD}` are replaced by the diary date | Use the default below |
| `Template` | File used to create a note that doesn't exist yet. `{{date}}` in it is replaced by the diary date (Obsidian Templates syntax) | Create the note with minimal frontmatter (`date:` only) |

**Default when there is no `Daily note` setting:** `00 Daily/{YYYY}/{YYYYMMDD}.md` relative to the current directory (the original skill's convention, for people who run Claude Code inside their vault). Common alternatives: `daily/{YYYY-MM-DD}.md`, `Daily Notes/{YYYY}/{YYYYMMDD}.md`, `journals/{YYYY}/{MM}/{DD}.md`.

If neither the setting nor the default folder exists, ask the user for the path and suggest adding the section above to `~/.claude/CLAUDE.md`. Never guess a path.
</configuration>

<arguments>
The user may type up to three values after the command, in this order:

| # | Value | Format | If missing |
|---|---|---|---|
| 1 | Start time | `YYYY-MM-DD HH:MM` (a bare `HH:MM` means today) | Ask |
| 2 | End time | `YYYY-MM-DD HH:MM`, `HH:MM`, or `now` | `now` |
| 3 | Diary date | `YYYY-MM-DD` | Ask |

Examples: `/log-to-daily 2026-11-06 08:00 2026-11-06 23:59 2026-11-06`, `/log-to-daily 08:00 now`.

**When the start time or the diary date is missing, ask before collecting anything** — one AskUserQuestion call with two questions, in the user's language:

1. "From when should I log?" options: today 08:00 (Recommended) · continue from where the last log stopped (`last_until` in the counter file; omit this option if there is none) · yesterday 08:00. "Other" lets them type a time.
2. "Which day's note should it go into?" options: the start time's date (Recommended) · today. "Other" lets them type a date.

Never guess either value. A window that spans midnight still goes into the one note the user picked.
</arguments>

<when_to_use>

- End of a work session (before closing Claude)
- After completing a significant piece of work
- When important decisions were made that should be recorded
- When the user explicitly requests logging
- Mid-session when switching contexts

**NOT needed when:**

- Just chatting without meaningful work output
- Quick questions with no decisions or outcomes
</when_to_use>

<daily_note>
Resolve the path from `<configuration>` with the diary date.

- **The note exists** (for example, written by hand from a template): keep everything in it and append the new section at the end.
- **The note doesn't exist:** create it from the `Template` setting (replace `{{date}}` with the diary date), or with minimal frontmatter when there is no template:

```markdown
---
date: YYYY-MM-DD
---

```

Append the session blocks under a heading that records the window, so a later log of the same day stays separate:

```markdown
## Claude Code log (<start> – <end>)
```
</daily_note>

<session_counter>

**Counter file:** `~/.claude/sessions/.session-count.json`

```json
{ "last_date": "2026-05-11", "session_count": 3, "last_until": "2026-05-11 18:30" }
```

- `last_date` is the **diary date** written to, not the day the skill runs
- Reset `session_count` to 1 when `last_date` != the diary date
- Increment `session_count` for each session logged when `last_date` == the diary date
- `last_until` = the end of the window just logged; offered next time as "continue from where the last log stopped" so windows don't overlap or leave gaps
- Write the updated counter back after each log append

**Note:** This requires the session logs on the same machine. If sessions run on different machines, session numbers will be inconsistent.

</session_counter>

<log_format>
**Per-session block:**

```markdown
#### Session [N] | [PROJECT] | [START_TIME]–[END_TIME]

**Focus:** [1-2 sentence summary of main work]

- **Completed:** [Concrete outcome 1], [outcome 2]
- **Decisions:** [Decision] → [rationale]
- **Files:** [[filename]] - [what/why]
- **Next:** [ ] [follow-up if any]
```

**Time extraction:** Use `start`/`end` from `collect-sessions.py` (local time, already clipped to the window). A session that crosses the window edge shows only the part inside it.

**When multiple sessions found:** Append one block per session, oldest first.
</log_format>

<process>

1. **Settle the window and the diary date**
   Parse the arguments (see `<arguments>`). Read `~/.claude/sessions/.session-count.json` first so "continue from where the last log stopped" can be offered. If the start time or the diary date is missing, ask with AskUserQuestion and wait for the answer.

2. **Resolve the daily note path** from `<configuration>`. If it can't be resolved, ask before collecting anything.

3. **Collect the messages in the window**
   ```bash
   python3 ${baseDir}/scripts/collect-sessions.py --since "<start>" --until "<end>"
   ```
   Output: JSON with `since`, `until`, and `sessions[]` (each: `project`, `start`, `end`, `message_count`, `messages[]` with `type`, `texts[]`/`content`, `local_ts`), oldest first. Times are local. Subagent logs are left out and messages copied by `/branch` or `/resume` are counted once. It needs only the Python standard library.
   If the default `python3` fails, try another Python 3 on the machine (on macOS, `/usr/bin/python3`).

4. **Skip empty/synthetic sessions**
   - Discard if: only system messages, or user content < 20 chars, or no assistant text responses
   - Keep if: at least one substantive user message (>20 chars) OR at least one assistant text response
   - Count discarded sessions separately for reporting

5. **Synthesize per session**
   For each kept session:
   - Identify main topics/tasks from user+assistant text
   - Identify concrete outputs (files created, code written, research)
   - Identify decisions and rationale
   - Identify outstanding next steps

6. **Determine session numbers**
   - If `last_date` != the diary date: start at 1
   - If `last_date` == the diary date: continue from `session_count` + 1
   - Write the updated counter back, with `last_date` = the diary date, `session_count` = the last number used and `last_until` = the window end

7. **Create or open the daily note** (see `<daily_note>`)

8. **Append session logs**
   - Insert `---` separator before each new entry
   - One block per session (oldest first)
   - Be specific about outcomes, not activities
   - Link created files with `[[wikilinks]]`

9. **Confirm** the window (start → end), the note path, session count, kept vs discarded count, and what was logged

</process>

<quality_guidelines>
**Good entries:**

- "Created YouTube analytics inbox item with 3 integration options"
- "Refactored authentication to use JWT instead of sessions"
- "Decision: Use Postgres over SQLite (need concurrent writes)"

**Bad entries:**

- "Worked on stuff"
- "Had a conversation about the project"
- "Did some research"

**Be specific.** Capture what was DONE, not what was discussed.

**Why this matters:** vault-analyst (from the original pack) reads these logs to find patterns. Vague entries = weak pattern detection. Specific entries = actionable automation recommendations.
</quality_guidelines>

<example_output>

```markdown
## Claude Code log (2026-05-11 09:00 – 2026-05-11 18:00)

---

#### Session 1 | my-project | 09:30–09:58

**Focus:** Set up log-to-daily cross-session skill

- **Completed:** Modified skill for cross-session logging; sessions numbered within each day; all sessions append to same daily note
- **Decisions:** Central log = daily note → all sessions share same file; session counter resets on date change → fresh count each day
- **Files:** [[log-to-daily/SKILL.md]] - Added cross-session support
- **Next:** [ ] Test with second session to verify numbering

---

#### Session 2 | api-service | 14:15–14:47

**Focus:** Fix authentication bug in API routes

- **Completed:** Identified token expiry race condition; fixed with proper async/await ordering
- **Decisions:** Reorder await chain → race condition caused intermittent 401s
- **Files:** [[api/auth.ts]] - Fixed race condition
- **Next:** [ ] Add integration test for auth flow
```

</example_output>

<success_criteria>

- [ ] Start time and diary date came from the arguments or the user's answer, never guessed
- [ ] The note path came from the `## log-to-daily` setting, the default, or the user's answer, never guessed
- [ ] Sessions picked by message timestamps inside the window (`collect-sessions.py`), not by file mtime
- [ ] Each session extracted via `extract-session.py` (text only, no thinking/tool_use)
- [ ] Session counter tracks the Nth session of the diary date, and `last_until` is saved
- [ ] Session counter resets when the diary date changes
- [ ] Each session appended with a unique session number
- [ ] User informed of the note path, session count and what was logged

</success_criteria>

<related_resources>
- **`${baseDir}/scripts/collect-sessions.py`** - picks messages inside a time window across all sessions (skips subagents, de-duplicates /branch and /resume copies)
- **`${baseDir}/scripts/extract-session.py`** - Python JSONL parser (handles control characters that break jq)
</related_resources>
