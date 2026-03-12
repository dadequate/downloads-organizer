#!/usr/bin/env python3
"""
screenshot_scanner.py — Screenshot context scanner using local macOS Vision.

Uses the compiled Swift binary (screenshot_scanner_bin) for:
  - VNRecognizeTextRequest (OCR)
  - VNClassifyImageRequest (scene classification)

Tags results as macOS xattrs and stores in file_metadata.db.
Only processes each file once.

Usage:
  python3 screenshot_scanner.py                # scan new screenshots
  python3 screenshot_scanner.py --all          # scan ALL images, not just screenshots
  python3 screenshot_scanner.py --rescan       # rescan everything (ignore previous tags)
  python3 screenshot_scanner.py --dry-run      # show what would be scanned
  python3 screenshot_scanner.py --query "text" # search tagged screenshots
  python3 screenshot_scanner.py --stats        # show scan statistics
"""

import json
import os
import sys
import subprocess
import datetime
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
META_DB_PATH = os.path.join(SCRIPT_DIR, "log", "file_metadata.db")
LOG_PATH = os.path.join(SCRIPT_DIR, "log", "activity.jsonl")
SCANNER_BIN = os.path.join(SCRIPT_DIR, "screenshot_scanner_bin")

XATTR_PREFIX = "com.organizer."

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".heic", ".heif", ".tiff", ".bmp", ".webp"}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_screenshot_dirs(config):
    dirs = config.get("screenshot_dirs", [])
    if not dirs:
        try:
            r = subprocess.run(
                ["defaults", "read", "com.apple.screencapture", "location"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                dirs.append(r.stdout.strip())
        except Exception:
            pass
        dirs.append(os.path.expanduser("~/Desktop"))
        dirs.append(os.path.expanduser("~/Downloads"))
    return [os.path.expanduser(d) for d in dirs]


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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON file_meta(filename)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tag ON file_meta(tag_type, tag_value)")
    conn.commit()
    return conn


def is_scanned(conn, filepath):
    cur = conn.execute(
        "SELECT 1 FROM file_meta WHERE filepath=? AND tag_type='scanned'",
        (filepath,)
    )
    return cur.fetchone() is not None


def store_meta(conn, filepath, tag_type, tag_value, extra=None):
    filename = os.path.basename(filepath)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR REPLACE INTO file_meta VALUES (?, ?, ?, ?, ?, ?)",
        (filepath, filename, tag_type, tag_value, ts,
         json.dumps(extra) if extra else None)
    )
    conn.commit()
    # Write xattr
    try:
        xattr_key = XATTR_PREFIX + tag_type
        # Truncate value for xattr (max ~2KB is safe)
        val = tag_value[:2000] if tag_value else ""
        subprocess.run(
            ["xattr", "-w", xattr_key, val, filepath],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


def get_frontmost_at_time(filepath):
    """Check activity log for what app was frontmost when file was created."""
    if not os.path.exists(LOG_PATH):
        return None
    try:
        file_time = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
        window = datetime.timedelta(minutes=2)
        best_entry = None
        best_delta = None

        with open(LOG_PATH) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts = datetime.datetime.fromisoformat(entry["ts"])
                    delta = abs((ts - file_time).total_seconds())
                    if delta <= window.total_seconds():
                        if best_delta is None or delta < best_delta:
                            best_delta = delta
                            best_entry = entry
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        if best_entry:
            return best_entry.get("frontmost")
    except Exception:
        pass
    return None


def is_screenshot(filepath):
    name = os.path.basename(filepath).lower()
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SCREENSHOT_EXTENSIONS:
        return False
    if name.startswith("screenshot") or name.startswith("screen shot"):
        return True
    if name.startswith("cleanshot"):
        return True
    if "capture" in name and ext == ".png":
        return True
    try:
        r = subprocess.run(
            ["mdls", "-name", "kMDItemIsScreenCapture", filepath],
            capture_output=True, text=True, timeout=5
        )
        if "1" in r.stdout:
            return True
    except Exception:
        pass
    return False


def find_screenshots(dirs, include_all_images=False):
    files = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            fpath = os.path.join(d, fname)
            if not os.path.isfile(fpath):
                continue
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SCREENSHOT_EXTENSIONS:
                continue
            if include_all_images or is_screenshot(fpath):
                files.append(fpath)
    return sorted(files)


def run_swift_scanner(file_list):
    """Run the Swift binary on specific files via a temp directory of symlinks."""
    if not os.path.exists(SCANNER_BIN):
        print(f"ERROR: Scanner binary not found at {SCANNER_BIN}")
        print("Build it from the ScreenshotScanner Xcode project.")
        return []

    import tempfile

    # Create temp dir with symlinks to just the files we need
    tmp_dir = tempfile.mkdtemp(prefix="screenshot_scan_")
    try:
        for fpath in file_list:
            link_name = os.path.join(tmp_dir, os.path.basename(fpath))
            # Handle duplicate basenames
            counter = 2
            while os.path.exists(link_name):
                name, ext = os.path.splitext(os.path.basename(fpath))
                link_name = os.path.join(tmp_dir, f"{name}_{counter}{ext}")
                counter += 1
            os.symlink(fpath, link_name)

        timeout = max(60, len(file_list) * 15)  # 15 sec per file
        r = subprocess.run(
            [SCANNER_BIN, tmp_dir],
            capture_output=True, text=True, timeout=timeout
        )
        results = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Resolve symlink path back to real path
                scan_path = obj.get("filepath", "")
                real_path = os.path.realpath(scan_path)
                obj["filepath"] = real_path
                results.append(obj)
            except json.JSONDecodeError:
                continue
        return results
    except subprocess.TimeoutExpired:
        print(f"Scanner timed out ({len(file_list)} files)")
        return []
    except Exception as e:
        print(f"Scanner error: {e}")
        return []
    finally:
        # Clean up temp dir
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def generate_description(ocr_text, classification, frontmost_app):
    """Generate a short description from OCR + classification + app context."""
    parts = []

    if classification and classification != "(null)":
        parts.append(f"[{classification}]")

    if frontmost_app:
        parts.append(f"App: {frontmost_app}")

    if ocr_text:
        # First meaningful line of OCR as summary
        lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
        # Skip very short lines, grab first substantial one
        summary_lines = [l for l in lines if len(l) > 5][:3]
        if summary_lines:
            parts.append(" | ".join(summary_lines))

    return " — ".join(parts) if parts else "Unrecognized image"


# ── Search ──

def search_screenshots(query):
    if not os.path.exists(META_DB_PATH):
        print("No metadata database found.")
        return

    conn = sqlite3.connect(META_DB_PATH)
    rows = conn.execute(
        """SELECT DISTINCT filepath, tag_type, tag_value FROM file_meta
           WHERE tag_type IN ('description', 'ocr_text', 'classification')
           AND tag_value LIKE ?
           ORDER BY filepath""",
        (f"%{query}%",)
    ).fetchall()
    conn.close()

    if not rows:
        print(f"No screenshots matching '{query}'")
        return

    # Group by filepath
    grouped = {}
    for filepath, tag_type, tag_value in rows:
        if filepath not in grouped:
            grouped[filepath] = {}
        grouped[filepath][tag_type] = tag_value

    for filepath, tags in grouped.items():
        print(f"  {os.path.basename(filepath)}")
        print(f"    Path: {filepath}")
        if "classification" in tags:
            print(f"    Type: {tags['classification']}")
        if "description" in tags:
            print(f"    Description: {tags['description'][:120]}")
        if "ocr_text" in tags:
            preview = tags["ocr_text"][:100].replace("\n", " ")
            print(f"    OCR: {preview}...")
        print()


def show_stats():
    if not os.path.exists(META_DB_PATH):
        print("No metadata database found.")
        return

    conn = sqlite3.connect(META_DB_PATH)

    total = conn.execute(
        "SELECT COUNT(DISTINCT filepath) FROM file_meta WHERE tag_type='scanned'"
    ).fetchone()[0]

    with_ocr = conn.execute(
        "SELECT COUNT(DISTINCT filepath) FROM file_meta WHERE tag_type='ocr_text' AND tag_value != ''"
    ).fetchone()[0]

    classifications = conn.execute(
        "SELECT tag_value, COUNT(*) FROM file_meta WHERE tag_type='classification' GROUP BY tag_value ORDER BY COUNT(*) DESC LIMIT 10"
    ).fetchall()

    conn.close()

    print(f"=== Screenshot Scanner Stats ===\n")
    print(f"  Total scanned: {total}")
    print(f"  With OCR text: {with_ocr}")
    print(f"  Without text:  {total - with_ocr}")
    if classifications:
        print(f"\n  Classifications:")
        for cls, count in classifications:
            print(f"    {cls}: {count}")


# ── Main ──

def run(dry_run=False, rescan=False, query=None, scan_all_images=False):
    if query:
        search_screenshots(query)
        return

    config = load_config()
    screenshot_dirs = get_screenshot_dirs(config)
    conn = init_meta_db()

    print(f"Scanning: {', '.join(screenshot_dirs)}")

    # Find files to process
    screenshots = find_screenshots(screenshot_dirs, include_all_images=scan_all_images)
    print(f"Found {len(screenshots)} {'images' if scan_all_images else 'screenshots'}")

    if not rescan:
        screenshots = [f for f in screenshots if not is_scanned(conn, f)]
    print(f"{len(screenshots)} need scanning\n")

    if not screenshots:
        print("Nothing to scan.")
        conn.close()
        return

    if dry_run:
        for fpath in screenshots:
            frontmost = get_frontmost_at_time(fpath)
            ctx = f" (app: {frontmost})" if frontmost else ""
            print(f"  [DRY RUN] {os.path.basename(fpath)}{ctx}")
        print(f"\n  Would scan {len(screenshots)} files")
        conn.close()
        return

    # Run Swift binary on just the files we need
    print(f"Running Vision scanner on {len(screenshots)} files...\n")
    all_results = run_swift_scanner(screenshots)

    # Index results by filepath
    result_map = {r["filepath"]: r for r in all_results}

    tagged = 0
    for fpath in screenshots:
        result = result_map.get(fpath)
        if not result:
            # File wasn't in scanned dirs or binary skipped it
            store_meta(conn, fpath, "scanned", "skipped")
            continue

        ocr_text = result.get("ocr_text", "")
        classification = result.get("classification", "")
        frontmost = get_frontmost_at_time(fpath)

        # Store raw data
        if ocr_text:
            store_meta(conn, fpath, "ocr_text", ocr_text[:5000])
        if classification:
            store_meta(conn, fpath, "classification", classification)
        if frontmost:
            store_meta(conn, fpath, "frontmost_app", frontmost)

        # Generate and store description
        desc = generate_description(ocr_text, classification, frontmost)
        store_meta(conn, fpath, "description", desc)
        store_meta(conn, fpath, "scanned", "vision")

        # Print summary
        short_desc = desc[:100]
        print(f"  {os.path.basename(fpath)}")
        print(f"    {short_desc}")
        print()
        tagged += 1

    conn.close()

    print(f"=== Done: {tagged} files tagged ===")
    print(f"Search: python3 {__file__} --query \"search term\"")
    print(f"Stats:  python3 {__file__} --stats")


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    rescan = "--rescan" in args
    scan_all = "--all" in args

    query = None
    if "--query" in args:
        idx = args.index("--query")
        if idx + 1 < len(args):
            query = args[idx + 1]

    if "--stats" in args:
        show_stats()
    else:
        run(dry_run=dry_run, rescan=rescan, query=query, scan_all_images=scan_all)