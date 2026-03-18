# Downloads Context Organizer

A macOS background tool that organizes your Downloads folder based on what you were actually working on -- not just file types.

## How It Works

- **Activity Logger** runs every 60 seconds capturing modified files, frontmost app, browser URLs, Finder dirs, download sources, and mail/message context
- **Organizer** matches new downloads to active projects using time-proximity scoring, extension affinity, and directory-level frequency analysis
- **Screenshot Scanner** uses Apple Vision framework (on-device, no API) for OCR and image classification with xattr tagging

## Core Files

- `activity_logger.py` -- Background poller, captures work context every 60s
- `organizer.py` -- Matches downloads to projects and moves files
- `matcher.py` -- Scoring engine (recency + affinity + frequency, aggregated by directory)
- `mover.py` -- Safe file operations with collision handling
- `config.json` -- All configuration: app whitelist, extension affinities, junk domains, chat IDs

## Utilities

- `mail_cleaner.py` -- Mail.app inbox cleaner (junk/safe domains loaded from config.json)
- `mail_filer.applescript` -- File inbox messages into folders by sender patterns
- `mail_rules.applescript` -- Create Mail.app rules for auto-filing
- `messages_cleaner.applescript` -- Delete junk Messages conversations (IDs from config.json)
- `screenshot_scanner.py` -- OCR + classification via local Vision framework
- `cluster_cleanup.py` -- One-shot batch cleanup for existing downloads
- `status.py` -- Quick terminal summary of recent activity and moves

## Install

```bash
./install.sh
```

This sets up two macOS LaunchAgents:
- `com.brad.activity-logger` -- runs every 60 seconds (starts at login)
- `com.brad.organizer` -- runs every 6 hours

## Building the Screenshot Scanner Binary

The `screenshot_scanner.py` wrapper requires a compiled Swift binary (`screenshot_scanner_bin`).
Source is in the separate `ScreenshotScanner` Xcode project (`GIT/ScreenshotScanner/`).

```bash
# Open in Xcode
open ~/Library/Mobile\ Documents/com~apple~CloudDocs/GIT/ScreenshotScanner/ScreenshotScanner.xcodeproj

# Build via command line (Release, arm64)
xcodebuild -project ~/Library/Mobile\ Documents/com~apple~CloudDocs/GIT/ScreenshotScanner/ScreenshotScanner.xcodeproj \
  -scheme ScreenshotScanner -configuration Release build

# Copy the binary into this project
cp ~/Library/Developer/Xcode/DerivedData/ScreenshotScanner-*/Build/Products/Release/ScreenshotScanner \
  ./screenshot_scanner_bin
```

## Requirements

- macOS (uses Spotlight, AppleScript, Vision framework)
- Python 3
- Xcode (only for building the screenshot scanner binary)

## License

MIT
