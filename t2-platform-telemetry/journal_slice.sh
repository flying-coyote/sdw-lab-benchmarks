#!/usr/bin/env bash
# Re-slice journalctl -u ollama by the epoch window in <trialdir>/session.json (UTC-safe).
d="$1"
S=$(python3 -c "import json,datetime;d=json.load(open('$d/session.json'));print(int(datetime.datetime.fromisoformat(d['start_utc']).timestamp())-2)")
E=$(python3 -c "import json,datetime;d=json.load(open('$d/session.json'));print(int(datetime.datetime.fromisoformat(d['end_utc']).timestamp())+3)")
journalctl -u ollama --utc --since "@$S" --until "@$E" --no-pager -o short-iso > "$d/journal.txt"
echo "epoch window $S..$E ($(wc -l < "$d/journal.txt") lines)" > "$d/window.txt"
cat "$d/window.txt"
