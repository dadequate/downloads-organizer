#!/usr/bin/env python3
"""
organizer.py — Orchestrator.
Scans Downloads for aged files, matches via activity log, moves to project dirs.
Tracks processed files in SQLite to prevent double-processing.
"""

import json
import os
import sqlite3
import hashlib
import datetime
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from matcher import find_best_match
from mover import safe_move

CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
DB_PATH = os.path.join(SCRIPT_DIR, "log", "processed.db")
MOVES_LOG = os.path.join(SCRIPT_DIR, "log", "moves.log")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            filepath TEXT,
            filehash TEXT,
            processed_at TEXT,
            destination TEXT,
            score REAL,
            PRIMARY KEY (filepath, filehash)
        )
    """)
    conn.commit()
    return conn

def file_hash(path):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return None

def is_processed(conn, filepath, fhash):
    cur = conn.execute(
        "SELECT 1 FROM processed WHERE filepath=? AND filehash=?",
        (filepath, fhash)
    )
    return cur.fetchone() is not None

def find_previous_destination(conn, filename):
    """Check if a file with this name was previously moved somewhere.
    Returns the destination directory, or None."""
    cur = conn.execute(
        "SELECT destination FROM processed WHERE filepath LIKE ? ORDER BY processed_at DESC LIMIT 1",
        (f"%/{filename}",)
    )
    row = cur.fetchone()
    if row and row[0]:
        dest_dir = os.path.dirname(row[0])
        if os.path.isdir(dest_dir):
            return dest_dir
    return None

def mark_processed(conn, filepath, fhash, destination, score):
    conn.execute(
        "INSERT OR REPLACE INTO processed VALUES (?, ?, ?, ?, ?)",
        (filepath, fhash, datetime.datetime.now().isoformat(), destination, score)
    )
    conn.commit()

def log_move(src, dest, score, dry_run):
    os.makedirs(os.path.dirname(MOVES_LOG), exist_ok=True)
    prefix = "[DRY RUN] " if dry_run else ""
    line = f"{prefix}{datetime.datetime.now().isoformat()} | {os.path.basename(src)} → {dest} (score: {score:.2f})\n"
    with open(MOVES_LOG, "a") as f:
        f.write(line)

def scan_downloads(config):
    dl_path = os.path.expanduser(config["downloads_path"])
    min_age = datetime.timedelta(hours=config.get("min_age_hours", 24))
    cutoff = datetime.datetime.now() - min_age
    ignore_ext = set(config.get("ignore_extensions", []))
    ignore_pre = config.get("ignore_prefixes", ["."])

    candidates = []
    if not os.path.isdir(dl_path):
        return candidates

    for fname in os.listdir(dl_path):
        fpath = os.path.join(dl_path, fname)
        if not os.path.isfile(fpath):
            continue
        if any(fname.startswith(p) for p in ignore_pre):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext in ignore_ext:
            continue
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            candidates.append((fpath, mtime))

    return candidates

def run():
    config = load_config()
    conn = init_db()
    dry_run = config.get("dry_run", True)
    symlink = config.get("symlink_originals", False)
    unsorted = os.path.expanduser(config.get("unsorted_path", "~/Downloads/_unsorted"))

    candidates = scan_downloads(config)
    moved = 0
    skipped = 0

    for fpath, mtime in candidates:
        fhash = file_hash(fpath)
        if fhash is None:
            continue
        if is_processed(conn, fpath, fhash):
            skipped += 1
            continue

        best_match, score = find_best_match(fpath, mtime, config)

        if best_match:
            dest_dir = os.path.dirname(best_match)
        else:
            # Check if we've seen this filename before
            prev = find_previous_destination(conn, os.path.basename(fpath))
            if prev:
                dest_dir = prev
                score = 0.01  # mark as history-matched
            else:
                # Unsorted, with date subfolder
                date_folder = mtime.strftime("%Y-%m-%d")
                dest_dir = os.path.join(unsorted, date_folder)

        final = safe_move(fpath, dest_dir, dry_run=dry_run, symlink=symlink)
        mark_processed(conn, fpath, fhash, final, score)
        log_move(fpath, final, score, dry_run)
        moved += 1

    conn.close()

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"[{mode}] Processed {moved} files, skipped {skipped} already-handled.")
    if dry_run and moved > 0:
        print(f"Review: {MOVES_LOG}")
        print("Set \"dry_run\": false in config.json to go live.")

if __name__ == "__main__":
    run()
