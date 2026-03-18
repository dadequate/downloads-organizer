-- messages_cleaner.applescript
-- Deletes junk conversations from Messages.app by chat identifier
-- Loads junk_chat_ids and junk_biz_prefixes from config.json
-- Usage: osascript messages_cleaner.applescript
-- Usage: osascript messages_cleaner.applescript --live

on run argv
	set liveMode to false
	if (count of argv) ≥ 1 then
		if item 1 of argv is "--live" then set liveMode to true
	end if

	-- Load junk IDs and prefixes from config.json
	set scriptDir to do shell script "cd \"$(dirname \"" & (POSIX path of (path to me)) & "\")\" && pwd"
	set configPath to scriptDir & "/config.json"
	set junkChats to paragraphs of (do shell script "/opt/homebrew/bin/python3 -c \"import json; c=json.load(open('" & configPath & "')); print('\\n'.join(c.get('junk_chat_ids',[])))\"")
	set junkPrefixes to paragraphs of (do shell script "/opt/homebrew/bin/python3 -c \"import json; c=json.load(open('" & configPath & "')); print('\\n'.join(c.get('junk_biz_prefixes',[])))\"")

	set modeLabel to "DRY RUN"
	if liveMode then set modeLabel to "LIVE"
	log "=== Messages Cleaner (" & modeLabel & ") ==="
	log "Loaded " & (count of junkChats) & " junk IDs, " & (count of junkPrefixes) & " biz prefixes from config.json"

	tell application "Messages"
		set allChats to every chat
		set total to count of allChats
		log "Total conversations: " & total

		set toDelete to {}

		repeat with c in allChats
			set cid to id of c
			set matched to false

			repeat with jid in junkChats
				if cid contains jid then
					set matched to true
					exit repeat
				end if
			end repeat

			if not matched then
				repeat with prefix in junkPrefixes
					if cid contains prefix then
						set matched to true
						exit repeat
					end if
				end repeat
			end if

			if matched then
				set end of toDelete to c
			end if
		end repeat

		set deleteCount to count of toDelete
		log "Found " & deleteCount & " junk conversations"

		if liveMode then
			set deleted to 0
			repeat with c in toDelete
				try
					set cid to id of c
					delete c
					set deleted to deleted + 1
					log "  Deleted: " & cid
				on error e
					log "  ERROR: " & e
				end try
			end repeat
			log "=== Done: deleted " & deleted & " conversations ==="
		else
			log "Would delete:"
			repeat with c in toDelete
				log "  " & id of c
			end repeat
			log "=== Dry run complete. Run with --live to execute. ==="
		end if
	end tell
end run
