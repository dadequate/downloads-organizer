#!/usr/bin/env python3
"""
status.py — Print a summary of recent activity and moves.
"""

import json
import os
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "log", "activity.jsonl")
MOVES_LOG = os.path.join(SCRIPT_DIR, "log", "moves.log")

def recent_activity(hours=6):
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
    entries = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    ts = datetime.datetime.fromisoformat(e["ts"])
                    if ts >= cutoff:
                        entries.append(e)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    return entries

def recent_moves(n=20):
    lines = []
    if os.path.exists(MOVES_LOG):
        with open(MOVES_LOG) as f:
            lines = f.readlines()
    return lines[-n:]

def main():
    print("=== Activity Logger Status ===\n")
    entries = recent_activity(6)
    if entries:
        apps = set()
        files = set()
        for e in entries:
            if e.get("frontmost"):
                apps.add(e["frontmost"])
            for fp in e.get("modified_files", []):
                files.add(os.path.basename(fp))
        print(f"Last 6 hours: {len(entries)} log ticks")
        print(f"Active apps: {', '.join(sorted(apps))}")
        if files:
            print(f"Recently modified project files: {', '.join(sorted(list(files)[:10]))}")
    else:
        print("No activity logged in last 6 hours.")
        print("Check: launchctl list | grep brad.activity")

    print("\n=== Recent Moves ===\n")
    moves = recent_moves(10)
    if moves:
        for m in moves:
            print(f"  {m.strip()}")
    else:
        print("No files moved yet.")

if __name__ == "__main__":
    main()
