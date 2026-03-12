#!/usr/bin/env python3
"""
cluster_cleanup.py — One-shot Downloads organizer.
Groups files by download-time proximity + extension affinity.
No activity log needed — just timestamps and file types.

Usage:
  python3 cluster_cleanup.py              # dry run (default)
  python3 cluster_cleanup.py --live       # actually move files
"""

import os
import sys
import json
import shutil
import datetime
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

# ── Clustering config ──
SESSION_GAP_HOURS = 3       # files within this gap = same session
AFFINITY_BONUS = True       # boost clusters where extensions are related

# ── Project type detection ──
# Extension combos → project type label
PROJECT_SIGNATURES = {
    "3D Print":     {".3mf", ".stl", ".gcode", ".ctb", ".obj", ".step"},
    "3D Model":     {".blend", ".FCStd", ".scad", ".3dm", ".fbx"},
    "Design":       {".psd", ".ai", ".afdesign", ".svg", ".eps"},
    "Photo":        {".jpg", ".jpeg", ".png", ".tiff", ".raw", ".cr2", ".cr3", ".dng", ".heic"},
    "Video":        {".mp4", ".mov", ".avi", ".mkv", ".fcpbundle", ".prproj"},
    "Audio":        {".wav", ".mp3", ".aif", ".flac", ".als", ".logicx", ".band"},
    "Document":     {".pdf", ".doc", ".docx", ".pages", ".numbers", ".xlsx", ".csv", ".md", ".txt"},
    "Web":          {".html", ".css", ".js", ".jsx", ".json"},
    "Code":         {".py", ".sh", ".yaml", ".yml", ".toml", ".swift", ".c", ".cpp"},
    "Archive":      {".zip", ".tar", ".gz", ".rar", ".7z", ".dmg"},
    "Font":         {".ttf", ".otf", ".woff", ".woff2"},
}

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def get_downloads(config):
    dl_path = os.path.expanduser(config["downloads_path"])
    ignore_ext = set(config.get("ignore_extensions", []))
    ignore_pre = config.get("ignore_prefixes", ["."])
    files = []
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
        files.append({"path": fpath, "name": fname, "ext": ext, "mtime": mtime})
    files.sort(key=lambda f: f["mtime"])
    return files

def cluster_by_time(files, gap_hours):
    """Group files into sessions based on time gaps."""
    if not files:
        return []
    clusters = []
    current = [files[0]]
    for f in files[1:]:
        delta = (f["mtime"] - current[-1]["mtime"]).total_seconds() / 3600
        if delta <= gap_hours:
            current.append(f)
        else:
            clusters.append(current)
            current = [f]
    clusters.append(current)
    return clusters

def detect_project_type(cluster):
    """Determine project type from extension mix in cluster."""
    exts = {f["ext"] for f in cluster}
    scores = {}
    for ptype, sig_exts in PROJECT_SIGNATURES.items():
        overlap = exts & sig_exts
        if overlap:
            scores[ptype] = len(overlap)
    if not scores:
        return "Mixed"
    # Return highest-scoring type
    return max(scores, key=scores.get)

def has_affinity(cluster, config):
    """Check if files in cluster have extension affinity with each other."""
    affinity_map = config.get("extension_affinity", {})
    exts = [f["ext"] for f in cluster]
    for ext in exts:
        affinities = set(affinity_map.get(ext, []))
        for other_ext in exts:
            if other_ext != ext and other_ext in affinities:
                return True
    return False

def generate_folder_name(cluster, project_type):
    """Create a descriptive folder name from the cluster."""
    # Use the earliest file's date
    date_str = cluster[0]["mtime"].strftime("%Y-%m-%d")

    # Try to find a meaningful name from filenames
    # Use the longest filename (minus ext) as the likely "main" file
    names = [(os.path.splitext(f["name"])[0], f) for f in cluster]
    names.sort(key=lambda x: len(x[0]), reverse=True)
    main_name = names[0][0]

    # Clean up the name
    main_name = main_name.replace("_", " ").replace("-", " ").strip()
    # Truncate if too long
    if len(main_name) > 40:
        main_name = main_name[:40].rsplit(" ", 1)[0]

    return f"{date_str} — {project_type} — {main_name}"

def run(live=False):
    config = load_config()
    files = get_downloads(config)
    print(f"Found {len(files)} files in Downloads\n")

    clusters = cluster_by_time(files, SESSION_GAP_HOURS)
    print(f"Formed {len(clusters)} time-based clusters\n")

    dest_base = os.path.expanduser(config.get("unsorted_path", "~/Downloads/_unsorted"))
    mode = "LIVE" if live else "DRY RUN"

    solo_count = 0
    cluster_count = 0
    moved_count = 0

    for cluster in clusters:
        project_type = detect_project_type(cluster)
        affinity = has_affinity(cluster, config)

        if len(cluster) == 1 and not affinity:
            # Solo file, no context — date folder
            f = cluster[0]
            date_folder = f["mtime"].strftime("%Y-%m-%d")
            dest_dir = os.path.join(dest_base, date_folder)
            dest = os.path.join(dest_dir, f["name"])

            if live:
                os.makedirs(dest_dir, exist_ok=True)
                if not os.path.exists(dest):
                    shutil.move(f["path"], dest)
                else:
                    name, ext = os.path.splitext(f["name"])
                    c = 2
                    while os.path.exists(dest):
                        dest = os.path.join(dest_dir, f"{name}_{c}{ext}")
                        c += 1
                    shutil.move(f["path"], dest)

            print(f"  [{mode}] SOLO: {f['name']}")
            print(f"         → {dest_dir}/")
            solo_count += 1
            moved_count += 1
            continue

        # Multi-file cluster or affinity match
        folder_name = generate_folder_name(cluster, project_type)
        dest_dir = os.path.join(dest_base, "_clusters", folder_name)

        print(f"  [{mode}] CLUSTER ({project_type}{'+ affinity' if affinity else ''}):")
        for f in cluster:
            dest = os.path.join(dest_dir, f["name"])
            print(f"         {f['name']}  ({f['mtime'].strftime('%m/%d %H:%M')})")

            if live:
                os.makedirs(dest_dir, exist_ok=True)
                if not os.path.exists(dest):
                    shutil.move(f["path"], dest)
                else:
                    name, ext = os.path.splitext(f["name"])
                    c = 2
                    while os.path.exists(dest):
                        dest = os.path.join(dest_dir, f"{name}_{c}{ext}")
                        c += 1
                    shutil.move(f["path"], dest)

            moved_count += 1

        print(f"         → {dest_dir}/")
        print()
        cluster_count += 1

    print(f"\n=== Summary ({mode}) ===")
    print(f"  {moved_count} files total")
    print(f"  {cluster_count} project clusters")
    print(f"  {solo_count} solo files → date folders")

    if not live:
        print(f"\nRun with --live to execute moves:")
        print(f"  python3 {os.path.abspath(__file__)} --live")

if __name__ == "__main__":
    live = "--live" in sys.argv
    run(live=live)
