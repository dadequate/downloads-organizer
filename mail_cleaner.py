#!/usr/bin/env python3
"""
mail_cleaner.py — Mail.app inbox cleaner.
Moves junk/spam/noise to Deleted Messages via osascript.

Usage:
  python3 mail_cleaner.py                    # dry run, MPC account
  python3 mail_cleaner.py --live             # actually move to trash
  python3 mail_cleaner.py --account iCloud   # different account
  python3 mail_cleaner.py --stats            # summary only, no details
"""

import subprocess
import sys
import os
import json
import datetime
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "log", "mail_cleaner.log")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


_config = load_config()
JUNK_DOMAINS = _config.get("junk_domains", [])
SAFE_DOMAINS = _config.get("safe_domains", [])


def osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
    return (r.stdout.strip(), None) if r.returncode == 0 else (None, r.stderr.strip())


def inbox_count(account):
    out, _ = osa(f'tell application "Mail" to return count of messages of mailbox "INBOX" of account "{account}"')
    try:
        return int(out)
    except Exception:
        return 0


def get_batch(account, start, end):
    script = f"""tell application "Mail"
    set mb to mailbox "INBOX" of account "{account}"
    set output to ""
    repeat with m in (messages {start} through {end} of mb)
        set output to output & (message id of m) & "|||" & (sender of m) & "|||" & (subject of m) & "\n"
    end repeat
    return output
end tell"""
    out, _ = osa(script)
    if not out:
        return []
    results = []
    for line in out.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) == 3:
            results.append({"id": parts[0].strip(), "sender": parts[1].strip(), "subject": parts[2].strip()})
    return results


def is_junk(sender):
    sl = sender.lower()
    for s in SAFE_DOMAINS:
        if s in sl:
            return None
    for d in JUNK_DOMAINS:
        if d in sl:
            return d
    return None


def move_to_trash(account, message_id):
    safe_id = message_id.replace('"', '')
    script = f"""tell application "Mail"
    set mb to mailbox "INBOX" of account "{account}"
    set dMB to mailbox "Deleted Messages" of account "{account}"
    move (first message of mb whose message id is "{safe_id}") to dMB
end tell"""
    _, err = osa(script)
    return err is None


def log_action(action, sender, subject):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} | {action} | {sender} | {subject}\n")


def run(account="MPC", dry_run=True, stats_only=False, batch_size=25, max_scan=5000):
    print(f"\n=== Mail Cleaner — {account} ({'DRY RUN' if dry_run else 'LIVE'}) ===\n")
    total = inbox_count(account)
    print(f"Inbox: {total:,} messages")
    limit = min(total, max_scan)
    print(f"Scanning first {limit:,}...\n")

    junk = []
    scanned = 0
    for start in range(1, limit + 1, batch_size):
        end = min(start + batch_size - 1, limit)
        msgs = get_batch(account, start, end)
        if not msgs:
            break
        for m in msgs:
            match = is_junk(m["sender"])
            if match:
                junk.append({**m, "matched": match})
        scanned += len(msgs)
        print(f"  Scanned {scanned:,}/{limit:,} — {len(junk)} junk found", end="\r")

    print(f"\n\nFound {len(junk)} junk messages in {scanned:,} scanned.\n")

    counts = Counter(m["matched"] for m in junk)
    print("Breakdown by sender:")
    for domain, count in counts.most_common():
        print(f"  {count:>4}  {domain}")

    if stats_only or not junk:
        return

    if dry_run:
        print(f"\nSample (first 15):")
        for m in junk[:15]:
            print(f"  {m['sender'][:60]}")
            print(f"    {m['subject'][:65]}")
        if len(junk) > 15:
            print(f"  ... and {len(junk) - 15} more")
        print(f"\nRun with --live to execute.\n")
        return

    # Live mode
    print(f"\nMoving {len(junk)} messages to Deleted Messages...")
    moved, failed = 0, 0
    for i, m in enumerate(junk):
        if move_to_trash(account, m["id"]):
            moved += 1
            log_action("DELETED", m["sender"], m["subject"])
        else:
            failed += 1
            log_action("FAILED", m["sender"], m["subject"])
        print(f"  {i+1}/{len(junk)} — {moved} moved, {failed} failed", end="\r")

    print(f"\n\n=== Done ===")
    print(f"  Moved:  {moved}")
    print(f"  Failed: {failed}")
    print(f"  Log:    {LOG_PATH}")


if __name__ == "__main__":
    args = sys.argv[1:]
    account = "MPC"
    if "--account" in args:
        idx = args.index("--account")
        if idx + 1 < len(args):
            account = args[idx + 1]
    dry_run = "--live" not in args
    stats_only = "--stats" in args
    run(account=account, dry_run=dry_run, stats_only=stats_only)
