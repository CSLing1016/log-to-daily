#!/usr/bin/env python3
"""
Collect every Claude Code session message that falls inside a time window.

Usage:
  collect-sessions.py --since "2026-11-06 08:00" [--until "2026-11-06 23:59" | --until now]

Times are local time (the machine's time zone). JSONL timestamps are UTC ISO
("2026-11-06T02:52:20.530Z") and are converted before comparing.

A session is kept when at least one of its messages falls in the window; only
the messages inside the window are returned, so a session that ran across
midnight is split by time, not by file modification date.

Output: JSON to stdout
  {"since": "...", "until": "...",
   "sessions": [{"file", "project", "start", "end", "message_count", "messages": [...]}, ...]}
sorted by first message time. start/end are local "HH:MM".
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module

extract_session = import_module("extract-session").extract_session  # noqa: E402

LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_local(s):
    if s == "now":
        return datetime.now(LOCAL_TZ)
    if len(s) == 5 and s[2] == ":":            # 只給 HH:MM → 今天
        s = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d ") + s
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            pass
    sys.exit(f"看不懂的時間：{s}（請用 YYYY-MM-DD HH:MM 或 now）")


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", default="now")
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    a = ap.parse_args()
    since, until = parse_local(a.since), parse_local(a.until)
    if since >= until:
        sys.exit("開始時間要早於結束時間")

    out = []
    for f in glob.glob(os.path.join(a.root, "**", "*.jsonl"), recursive=True):
        if os.sep + "subagents" + os.sep in f:
            continue    # 子代理的紀錄是主對話的一部分，不另外算一個 session
        # 最後寫入早於開始時間的檔案不可能有範圍內的訊息，先跳過（只是加速，不是判斷依據）
        if datetime.fromtimestamp(os.path.getmtime(f), LOCAL_TZ) < since:
            continue
        msgs = []
        for m in extract_session(f)["messages"]:
            t = parse_ts(m.get("ts"))
            if t and since <= t <= until:
                m["local_ts"] = t.strftime("%Y-%m-%d %H:%M")
                msgs.append(m)
        if not msgs:
            continue
        first, last = msgs[0]["local_ts"], msgs[-1]["local_ts"]
        out.append({"file": f, "project": os.path.basename(os.path.dirname(f)),
                    "start": first[11:], "end": last[11:], "first": first,
                    "message_count": len(msgs), "messages": msgs})
    # /branch、/resume 分出來的對話會複製原對話的訊息：同一則訊息只留一次，
    # 訊息多的那份先拿；複製出來的那份扣掉重複後沒剩東西就不列
    seen = set()
    kept = []
    for s in sorted(out, key=lambda x: -x["message_count"]):
        def key(m):
            body = m.get("content") if m["type"] == "user" else m.get("texts")
            return (m.get("ts"), m["type"], json.dumps(body, ensure_ascii=False)[:200])
        msgs = [m for m in s["messages"] if key(m) not in seen]
        seen.update(key(m) for m in s["messages"])
        if not msgs:
            continue
        s.update(messages=msgs, message_count=len(msgs), first=msgs[0]["local_ts"],
                 start=msgs[0]["local_ts"][11:], end=msgs[-1]["local_ts"][11:])
        kept.append(s)
    out = kept
    out.sort(key=lambda s: s["first"])
    print(json.dumps({"since": since.strftime("%Y-%m-%d %H:%M"),
                      "until": until.strftime("%Y-%m-%d %H:%M"),
                      "sessions": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
