#!/usr/bin/env python3
"""
activity_logger.py — Full-context background poller.

Signals captured every tick:
  1. mdfind: project files modified in last 5 min
  2. Frontmost app + running apps
  3. Finder directory + browser URL
  4. Safari download history (source URLs mapped to filenames)
  5. Chrome download history (source URLs mapped to filenames)
  6. Mail.app: recent messages with attachments (sender + subject)
  7. Messages: recent attachments with sender info
"""

import json
import os
import subprocess
import datetime
import sqlite3
import shutil
import tempfile
import plistlib
from urllib.parse import urlparse
# No external dependencies beyond stdlib — uses macOS built-in xattr command

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
LOG_PATH = os.path.join(SCRIPT_DIR, "log", "activity.jsonl")
META_DB_PATH = os.path.join(SCRIPT_DIR, "log", "file_metadata.db")

MDFIND_WINDOW = 300  # 5 minutes
DOWNLOAD_HISTORY_WINDOW = 300  # 5 minutes

SEARCH_DIRS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Projects"),
    os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs"),
    os.path.expanduser("~/Library/CloudStorage"),
    os.path.expanduser("~/Library/Messages/Attachments"),
    os.path.expanduser("~/downloads-organizer"),
]

PROJECT_EXTENSIONS = {
    ".3mf", ".stl", ".gcode", ".blend", ".FCStd", ".scad", ".3dm",
    ".obj", ".fbx", ".step", ".iges", ".ctb",
    ".svg", ".psd", ".ai", ".afdesign", ".png", ".jpg", ".jpeg",
    ".tiff", ".raw", ".cr2", ".cr3", ".dng", ".heic", ".eps",
    ".mp4", ".mov", ".wav", ".mp3", ".aif", ".flac", ".als",
    ".logicx", ".band", ".fcpbundle", ".prproj",
    ".pdf", ".doc", ".docx", ".pages", ".numbers", ".xlsx", ".csv",
    ".md", ".txt", ".rtf",
    ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".sh",
    ".json", ".yaml", ".yml", ".swift", ".c", ".cpp", ".xml",
    ".zip", ".tar", ".gz",
}

# ── xattr keys for file tagging ──
XATTR_PREFIX = "com.organizer."
XATTR_RECEIVED_FROM = XATTR_PREFIX + "received_from"
XATTR_SENT_TO = XATTR_PREFIX + "sent_to"
XATTR_SOURCE_URL = XATTR_PREFIX + "source_url"
XATTR_SOURCE_DOMAIN = XATTR_PREFIX + "source_domain"
XATTR_MAIL_SUBJECT = XATTR_PREFIX + "mail_subject"
XATTR_CONTEXT = XATTR_PREFIX + "context"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def run_osascript(script):
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, Exception):
        return None


def is_app_running(app_name):
    result = run_osascript(
        f'tell application "System Events" to (name of processes) contains "{app_name}"'
    )
    return result == "true"


def get_frontmost_app():
    return run_osascript(
        'tell application "System Events" to get name of first process whose frontmost is true'
    )


def get_running_apps():
    result = run_osascript(
        'tell application "System Events" to get name of every process whose background only is false'
    )
    if result:
        return [a.strip() for a in result.split(",")]
    return []


# ── File metadata DB ──

def init_meta_db():
    os.makedirs(os.path.dirname(META_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(META_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_meta (
            filepath TEXT,
            filename TEXT,
            tag_type TEXT,
            tag_value TEXT,
            timestamp TEXT,
            extra TEXT,
            PRIMARY KEY (filepath, tag_type)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_filename ON file_meta(filename)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag ON file_meta(tag_type, tag_value)
    """)
    conn.commit()
    return conn


def store_file_meta(conn, filepath, tag_type, tag_value, extra=None):
    """Store metadata in both SQLite and xattr."""
    filename = os.path.basename(filepath)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR REPLACE INTO file_meta VALUES (?, ?, ?, ?, ?, ?)",
        (filepath, filename, tag_type, tag_value, ts, json.dumps(extra) if extra else None)
    )
    conn.commit()

    # Write xattr if file exists (using macOS built-in xattr command)
    if os.path.exists(filepath):
        try:
            xattr_key = XATTR_PREFIX + tag_type
            subprocess.run(
                ["xattr", "-w", xattr_key, tag_value, filepath],
                capture_output=True, timeout=5
            )
        except (subprocess.TimeoutExpired, Exception):
            pass


def has_meta(conn, filepath, tag_type):
    cur = conn.execute(
        "SELECT 1 FROM file_meta WHERE filepath=? AND tag_type=?",
        (filepath, tag_type)
    )
    return cur.fetchone() is not None


# ── mdfind ──

def get_recently_modified_files(window_seconds=MDFIND_WINDOW):
    results = []
    for search_dir in SEARCH_DIRS:
        if not os.path.isdir(search_dir):
            continue
        try:
            r = subprocess.run(
                ["mdfind", "-onlyin", search_dir,
                 f"kMDItemFSContentChangeDate >= $time.now(-{window_seconds})"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    p = line.strip()
                    if not p:
                        continue
                    ext = os.path.splitext(p)[1].lower()
                    if ext in PROJECT_EXTENSIONS:
                        results.append(p)
        except (subprocess.TimeoutExpired, Exception):
            continue
    return list(set(results))


# ── Finder + Browser ──

def get_finder_target():
    if not is_app_running("Finder"):
        return None
    return run_osascript(
        'tell application "Finder" to get POSIX path of (target of front window as alias)'
    )


def get_browser_url():
    for browser, script in [
        ("Safari", 'tell application "Safari" to get URL of current tab of front window'),
        ("Google Chrome", 'tell application "Google Chrome" to get URL of active tab of front window'),
    ]:
        if is_app_running(browser):
            result = run_osascript(script)
            if result:
                return {"browser": browser, "url": result}
    return None


# ── Safari download history ──

def get_safari_downloads(conn, window_seconds=DOWNLOAD_HISTORY_WINDOW):
    """Parse Safari's Downloads.plist for recent downloads with source URLs."""
    plist_path = os.path.expanduser("~/Library/Safari/Downloads.plist")
    if not os.path.exists(plist_path):
        return []

    try:
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)
    except Exception:
        return []

    downloads = []
    cutoff = datetime.datetime.now() - datetime.timedelta(seconds=window_seconds)

    for item in data.get("DownloadHistory", []):
        url = item.get("DownloadEntryURL", "")
        path = item.get("DownloadEntryPath", "")
        identifier = item.get("DownloadEntryIdentifier", "")

        if not path or not url:
            continue

        path = os.path.expanduser(path)
        filename = os.path.basename(path)

        # Tag the file if it exists and hasn't been tagged yet
        if os.path.exists(path) and not has_meta(conn, path, "source_url"):
            domain = extract_domain(url)
            store_file_meta(conn, path, "source_url", url, {"domain": domain})
            store_file_meta(conn, path, "source_domain", domain)
            downloads.append({"filename": filename, "url": url, "domain": domain, "path": path})

    return downloads


# ── Chrome download history ──

def get_chrome_downloads(conn, window_seconds=DOWNLOAD_HISTORY_WINDOW):
    """Read Chrome's History SQLite for recent downloads with source URLs."""
    history_path = os.path.expanduser(
        "~/Library/Application Support/Google Chrome/Default/History"
    )
    if not os.path.exists(history_path):
        return []

    # Chrome locks the db — copy it first
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        shutil.copy2(history_path, tmp.name)

        db = sqlite3.connect(tmp.name)
        # Chrome stores timestamps as microseconds since 1601-01-01
        # Convert our cutoff to Chrome epoch
        cutoff_seconds = window_seconds
        # Just grab last N entries and filter by recency another way
        rows = db.execute("""
            SELECT target_path, tab_url, end_time
            FROM downloads
            WHERE state = 1
            ORDER BY end_time DESC
            LIMIT 50
        """).fetchall()
        db.close()
    except Exception:
        return []
    finally:
        if tmp and os.path.exists(tmp.name):
            os.unlink(tmp.name)

    downloads = []
    for target_path, tab_url, end_time in rows:
        if not target_path or not tab_url:
            continue
        filename = os.path.basename(target_path)

        if os.path.exists(target_path) and not has_meta(conn, target_path, "source_url"):
            domain = extract_domain(tab_url)
            store_file_meta(conn, target_path, "source_url", tab_url, {"domain": domain})
            store_file_meta(conn, target_path, "source_domain", domain)
            downloads.append({"filename": filename, "url": tab_url, "domain": domain, "path": target_path})

    return downloads


# ── Mail.app ──

def get_recent_mail_attachments(conn):
    """Query Mail.app for recent messages with attachments."""
    if not is_app_running("Mail"):
        return []

    script = '''
    tell application "Mail"
        set output to ""
        set msgs to (messages of inbox whose date received > (current date) - 300 and mail attachments is not {})
        repeat with msg in msgs
            set sender_addr to sender of msg
            set subj to subject of msg
            repeat with att in mail attachments of msg
                set att_name to name of att
                set output to output & sender_addr & "|||" & subj & "|||" & att_name & "\\n"
            end repeat
        end repeat
        return output
    end tell
    '''
    result = run_osascript(script)
    if not result:
        return []

    attachments = []
    dl_path = os.path.expanduser("~/Downloads")

    for line in result.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) != 3:
            continue
        sender, subject, att_name = [p.strip() for p in parts]

        # Check if attachment landed in Downloads
        att_path = os.path.join(dl_path, att_name)
        if os.path.exists(att_path) and not has_meta(conn, att_path, "received_from"):
            store_file_meta(conn, att_path, "received_from", sender,
                          {"subject": subject, "filename": att_name})
            store_file_meta(conn, att_path, "mail_subject", subject)

            # Also write mail subject xattr
            try:
                subprocess.run(
                    ["xattr", "-w", XATTR_MAIL_SUBJECT, subject, att_path],
                    capture_output=True, timeout=5
                )
            except (subprocess.TimeoutExpired, Exception):
                pass

            attachments.append({
                "filename": att_name,
                "from": sender,
                "subject": subject,
                "path": att_path
            })

    return attachments


# ── Messages (iMessage) ──

def get_recent_message_attachments(conn):
    """Find recently modified files in Messages attachments directory."""
    att_dir = os.path.expanduser("~/Library/Messages/Attachments")
    if not os.path.isdir(att_dir):
        return []

    cutoff = datetime.datetime.now() - datetime.timedelta(seconds=300)
    attachments = []

    # Use mdfind for speed instead of walking the tree
    try:
        r = subprocess.run(
            ["mdfind", "-onlyin", att_dir,
             "kMDItemFSContentChangeDate >= $time.now(-300)"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return []

        for line in r.stdout.splitlines():
            p = line.strip()
            if not p or not os.path.isfile(p):
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext in PROJECT_EXTENSIONS:
                filename = os.path.basename(p)
                if not has_meta(conn, p, "received_from"):
                    store_file_meta(conn, p, "received_from", "iMessage",
                                  {"filename": filename, "source": "Messages"})
                    attachments.append({"filename": filename, "path": p, "source": "Messages"})
    except (subprocess.TimeoutExpired, Exception):
        pass

    return attachments


# ── Sent file detection ──

def detect_sent_files(conn, frontmost_app, modified_files):
    """
    Heuristic: if Mail or Messages is frontmost and a file was recently modified
    in their attachment staging areas, mark it as sent.
    """
    sent = []
    if frontmost_app not in ("Mail", "Messages"):
        return sent

    for fp in modified_files:
        # Files being composed in Mail go through a temp staging path
        if "/Mail/" in fp or "/Messages/" in fp:
            filename = os.path.basename(fp)
            if not has_meta(conn, fp, "sent_to"):
                store_file_meta(conn, fp, "sent_to", f"via {frontmost_app}",
                              {"filename": filename})
                sent.append({"filename": filename, "via": frontmost_app, "path": fp})

    return sent


# ── Utility ──

def extract_domain(url):
    """Pull domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Strip www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def trim_old_entries(config):
    retention = config.get("log_retention_days", 30)
    cutoff = datetime.datetime.now() - datetime.timedelta(days=retention)
    if not os.path.exists(LOG_PATH):
        return
    try:
        with open(LOG_PATH, "r") as f:
            lines = f.readlines()
        kept = []
        for line in lines:
            try:
                entry = json.loads(line)
                ts = datetime.datetime.fromisoformat(entry["ts"])
                if ts >= cutoff:
                    kept.append(line)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        with open(LOG_PATH, "w") as f:
            f.writelines(kept)
    except Exception:
        pass


# ── Main tick ──

def tick(config):
    conn = init_meta_db()

    modified = get_recently_modified_files()
    frontmost = get_frontmost_app()
    running = get_running_apps()
    finder_dir = get_finder_target()
    browser = get_browser_url()

    # Gather download + messaging context
    safari_dl = get_safari_downloads(conn)
    chrome_dl = get_chrome_downloads(conn)
    mail_att = get_recent_mail_attachments(conn)
    msg_att = get_recent_message_attachments(conn)
    sent = detect_sent_files(conn, frontmost, modified)

    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "frontmost": frontmost,
        "modified_files": modified,
        "running": running,
    }

    if finder_dir:
        entry["finder_dir"] = finder_dir
    if browser:
        entry["browser"] = browser
    if safari_dl:
        entry["safari_downloads"] = safari_dl
    if chrome_dl:
        entry["chrome_downloads"] = chrome_dl
    if mail_att:
        entry["mail_attachments"] = mail_att
    if msg_att:
        entry["message_attachments"] = msg_att
    if sent:
        entry["sent_files"] = sent

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    conn.close()


def main():
    config = load_config()
    trim_old_entries(config)
    tick(config)


if __name__ == "__main__":
    main()