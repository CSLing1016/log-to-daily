#!/usr/bin/env python3
"""
Extract essential conversation from Claude Code session JSONL files.

Usage: ./extract-session.py <session.jsonl>
Output: JSON to stdout with structure:
  {
    "file": "...",
    "message_count": N,
    "messages": [{type, content/ts/texts, ts}, ...]
  }

Handles JSONL files with embedded control characters that break jq on macOS.
Strips: thinking, tool_use, file-history-snapshot, queue-operation (~94% size reduction).
"""
import json
import re
import sys

def sanitize(text):
    """Remove control characters except newlines/tabs."""
    if isinstance(text, str):
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text

def extract_session(filepath):
    messages = []
    with open(filepath, 'r', errors='replace') as f:
        for line in f:
            line = sanitize(line.strip())
            if not line:
                continue
            try:
                obj = json.loads(line)
                msg_type = obj.get('type', '')
                ts = obj.get('timestamp', '')
                if msg_type == 'summary':
                    messages.append({'type': 'summary', 'summary': obj.get('summary', ''), 'ts': ts})
                elif msg_type == 'user':
                    content = obj.get('message', {}).get('content', '')
                    messages.append({'type': 'user', 'content': sanitize(content), 'ts': ts})
                elif msg_type == 'assistant':
                    texts = []
                    for c in obj.get('message', {}).get('content', []):
                        if isinstance(c, dict) and c.get('type') == 'text':
                            texts.append(sanitize(c.get('text', '')))
                    if texts:
                        messages.append({'type': 'assistant', 'texts': texts, 'ts': ts})
            except json.JSONDecodeError:
                pass
    return {'file': filepath, 'message_count': len(messages), 'messages': messages}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <session.jsonl>", file=sys.stderr)
        sys.exit(1)
    result = extract_session(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
