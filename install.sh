#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=== Downloads Context Organizer — Install ==="

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install it first."
    exit 1
fi
echo "✓ Python 3 found: $(python3 --version)"

# Create log dir
mkdir -p "$PROJECT_DIR/log"

# Copy plists to LaunchAgents
mkdir -p "$AGENTS_DIR"
cp "$PROJECT_DIR/com.brad.activity-logger.plist" "$AGENTS_DIR/"
cp "$PROJECT_DIR/com.brad.organizer.plist" "$AGENTS_DIR/"
echo "✓ LaunchAgent plists copied"

# Unload if already loaded (ignore errors)
launchctl bootout gui/$(id -u)/com.brad.activity-logger 2>/dev/null || true
launchctl bootout gui/$(id -u)/com.brad.organizer 2>/dev/null || true

# Load agents
launchctl bootstrap gui/$(id -u) "$AGENTS_DIR/com.brad.activity-logger.plist"
launchctl bootstrap gui/$(id -u) "$AGENTS_DIR/com.brad.organizer.plist"
echo "✓ LaunchAgents loaded"

# Verify
echo ""
echo "=== Verification ==="
sleep 2

if launchctl print gui/$(id -u)/com.brad.activity-logger &>/dev/null; then
    echo "✓ Activity logger running"
else
    echo "✗ Activity logger not running — check log/logger-stderr.log"
fi

# Run organizer once in dry-run mode
echo ""
echo "=== Dry Run ==="
python3 "$PROJECT_DIR/organizer.py"

echo ""
echo "=== Done ==="
echo "Logger is writing to: $PROJECT_DIR/log/activity.jsonl"
echo "Organizer runs every 6 hours (dry_run=true by default)"
echo "Edit config.json to tune, then set dry_run to false when ready."
echo "Run 'python3 $PROJECT_DIR/status.py' anytime for a summary."
