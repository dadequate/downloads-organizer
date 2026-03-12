#!/usr/bin/env python3
"""
matcher.py — Core matching logic.
Given a downloaded file + its timestamp, scores activity log entries
to find the best project file association.
"""

import json
import os
import datetime
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "log", "activity.jsonl")

def load_log_entries(window_start, window_end):
    entries = []
    if not os.path.exists(LOG_PATH):
        return entries
    with open(LOG_PATH, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = datetime.datetime.fromisoformat(entry["ts"])
                if window_start <= ts <= window_end:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return entries

def score_candidates(download_ext, download_ts, entries, config):
    """
    Returns list of (project_file_path, score) sorted descending.
    Scoring:
      - recency: closer to download time = higher (max 1.0)
      - affinity: download ext has affinity to project file ext (0.5 bonus)
      - frequency: file appeared in more ticks = higher (max 0.5)
    """
    window_min = config.get("session_window_minutes", 90)
    affinity_map = config.get("extension_affinity", {})
    affinities = affinity_map.get(download_ext, [])

    # Count appearances of each recently modified file
    file_freq = Counter()
    file_timestamps = {}
    for entry in entries:
        ts = datetime.datetime.fromisoformat(entry["ts"])
        for fp in entry.get("modified_files", entry.get("open_files", [])):
            file_freq[fp] += 1
            # Track closest timestamp to download
            if fp not in file_timestamps:
                file_timestamps[fp] = ts
            else:
                if abs((ts - download_ts).total_seconds()) < abs((file_timestamps[fp] - download_ts).total_seconds()):
                    file_timestamps[fp] = ts

    if not file_freq:
        return []

    max_freq = max(file_freq.values())
    scores = []

    for fp, freq in file_freq.items():
        ext = os.path.splitext(fp)[1].lower()

        # Recency score (0-1): 1.0 = exact match, 0 = edge of window
        delta = abs((file_timestamps[fp] - download_ts).total_seconds())
        recency = max(0, 1.0 - (delta / (window_min * 60)))

        # Affinity score (0 or 0.5)
        affinity = 0.5 if ext in affinities else 0.0

        # Frequency score (0-0.5)
        frequency = 0.5 * (freq / max_freq) if max_freq > 0 else 0

        total = recency + affinity + frequency
        scores.append((fp, total))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores

def find_best_match(download_path, download_ts, config):
    """
    Returns (best_project_file_path, score) or (None, 0).
    """
    window_min = config.get("session_window_minutes", 90)
    window_start = download_ts - datetime.timedelta(minutes=window_min)
    window_end = download_ts + datetime.timedelta(minutes=window_min)

    entries = load_log_entries(window_start, window_end)
    if not entries:
        return None, 0

    download_ext = os.path.splitext(download_path)[1].lower()
    scored = score_candidates(download_ext, download_ts, entries, config)

    if not scored:
        return None, 0

    best_path, best_score = scored[0]
    threshold = config.get("confidence_threshold", 0.6)

    if best_score >= threshold:
        return best_path, best_score
    return None, best_score
