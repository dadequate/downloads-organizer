-- messages_cleaner.applescript
-- Deletes junk conversations from Messages.app by chat identifier
-- Usage: osascript messages_cleaner.applescript
-- Usage: osascript messages_cleaner.applescript --live

property junkChats : {¬
	"61746", ¬
	"67587", ¬
	"72975", ¬
	"56699", ¬
	"262966", ¬
	"20333", ¬
	"98900", ¬
	"242733", ¬
	"88648", ¬
	"762265", ¬
	"347268", ¬
	"22000", ¬
	"49674", ¬
	"899000", ¬
	"729725", ¬
	"40158", ¬
	"42278", ¬
	"77223", ¬
	"86753", ¬
	"26459", ¬
	"22395", ¬
	"70924", ¬
	"30837", ¬
	"41842", ¬
	"57513", ¬
	"787473", ¬
	"96326", ¬
	"35097", ¬
	"95246", ¬
	"18889034449", ¬
	"57006", ¬
	"84285", ¬
	"76200", ¬
	"48267", ¬
	"32665", ¬
	"36397", ¬
	"43469", ¬
	"82008", ¬
	"86278", ¬
	"90347", ¬
	"24273", ¬
	"52927", ¬
	"97727", ¬
	"19877"}

property junkBizPrefixes : {¬
	"urn:biz:e3cfd0e4", ¬
	"urn:biz:a7697077", ¬
	"urn:biz:b15ed773", ¬
	"urn:biz:2f85cef6"}

on run argv
	set liveMode to false
	if (count of argv) ≥ 1 then
		if item 1 of argv is "--live" then set liveMode to true
	end if

	set modeLabel to "DRY RUN"
	if liveMode then set modeLabel to "LIVE"
	log "=== Messages Cleaner (" & modeLabel & ") ==="

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
				repeat with prefix in junkBizPrefixes
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
