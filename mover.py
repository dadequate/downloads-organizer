#!/usr/bin/env python3
"""
mover.py — Safe file operations.
Moves files, handles collisions, optional symlinks.
"""

import os
import shutil

def safe_move(src, dest_dir, dry_run=False, symlink=False):
    """
    Moves src into dest_dir. Returns final destination path.
    Handles collisions by appending _2, _3, etc.
    """
    os.makedirs(dest_dir, exist_ok=True)
    basename = os.path.basename(src)
    name, ext = os.path.splitext(basename)
    dest = os.path.join(dest_dir, basename)

    # Collision handling
    counter = 2
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{name}_{counter}{ext}")
        counter += 1

    if dry_run:
        return dest

    shutil.move(src, dest)

    if symlink:
        try:
            os.symlink(dest, src)
        except OSError:
            pass  # symlink failed, not critical

    return dest
