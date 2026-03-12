# Downloads Context Organizer

A macOS background tool that organizes your Downloads folder based on what you were actually working on -- not just file types.

## How It Works

- Activity Logger runs every 60 seconds capturing modified files, frontmost app, browser URLs, Finder dirs, download sources, and mail/message context
- Organizer matches new downloads to active projects using time-proximity scoring, extension affinity, URL domain clustering, and Finder directory context
- Screenshot Scanner uses Apple Vision framework (on-device, no API) for OCR and image classification with xattr tagging

## Files

- activity_logger.py -- Background poller, captures work context every 60s
- organizer.py -- Matches downloads to projects and moves files
- matcher.py -- Scoring engine
- mover.py -- Safe file operations with collision handling
- screenshot_scanner.py -- OCR + classification via local Vision framework
- cluster_cleanup.py -- One-shot cleanup for existing downloads
- status.py -- Quick terminal summary
- config.json -- App whitelist, extension affinities, domain mappings
- install.sh -- Sets up macOS LaunchAgents

## Requirements

- macOS (uses Spotlight, AppleScript, Vision framework)
- Python 3
- Xcode (to build the Swift screenshot scanner binary)

## License

MIT
