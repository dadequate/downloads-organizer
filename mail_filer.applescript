-- mail_filer.applescript
-- Files inbox messages into folders based on sender patterns
-- Usage: osascript mail_filer.applescript <account>
-- Example: osascript mail_filer.applescript MPC
-- Example: osascript mail_filer.applescript iCloud
-- liveMode is hardcoded true — remove to dry run

on getFolder(senderAddr, accountName)
	set sl to senderAddr
	
	if accountName is "MPC" then
		-- Orders
		if sl contains "flow@shopify.com" or sl contains "faire.com" or sl contains "info@mainepottery.com" then
			return "Order Emails"
		end if
		-- Accounting
		if sl contains "squareup.com" or sl contains "key.com" or sl contains "chase.com" or sl contains "americanexpress.com" or sl contains "adp.com" or sl contains "efileservices.net" or sl contains "perkinsthompson.com" or sl contains "onerivercpas.com" or sl contains "safesendreturns.com" or sl contains "stripe.com" then
			return "accounting"
		end if
		-- Platforms
		if sl contains "klaviyo.com" or sl contains "brevo.com" or sl contains "shopify.com" or sl contains "googlealerts" or sl contains "figma.com" or sl contains "printify.com" or sl contains "google.com" then
			return "Misc"
		end if
	end if
	
	if accountName is "iCloud" then
		-- Finance
		if sl contains "pnc.com" or sl contains "wellsfargo.com" or sl contains "discover.com" or sl contains "paypal.com" or sl contains "applecard" or sl contains "citicards" or sl contains "bernstein" or sl contains "cointracker" or sl contains "monarchmoney" then
			return "Finance"
		end if
		-- Orders & Shipping
		if sl contains "shipment-tracking@amazon" or sl contains "auto-confirm@amazon" or sl contains "order-update@amazon" or sl contains "informeddelivery" or sl contains "fedex.com" or sl contains "orders@oe.target.com" or sl contains "ups.com" then
			return "Orders & Shipping"
		end if
		-- 3D & Creative
		if sl contains "bambulab" or sl contains "makerworld" or sl contains "bambu lab" then
			return "3D & Creative"
		end if
		-- Business
		if sl contains "edgecombpotters.com" or sl contains "mainepottery.com" then
			return "Business"
		end if
	end if
	
	return ""
end getFolder

on run argv
	set accountName to "MPC"
	set liveMode to true
	if (count of argv) >= 1 then set accountName to item 1 of argv
	
	log "=== Mail Filer — " & accountName & " ==="
	
	tell application "Mail"
		set acct to account accountName
		set mb to mailbox "INBOX" of acct
		
		-- Create iCloud folders if needed
		if accountName is "iCloud" then
			set folderNames to {"Finance", "Orders & Shipping", "3D & Creative", "Business"}
			repeat with fn in folderNames
				if not (exists mailbox fn of acct) then
					make new mailbox with properties {name:fn} in acct
					log "Created folder: " & fn
				end if
			end repeat
		end if
		
		log "Loading messages..."
		set allMsgs to get messages of mb
		set total to count of allMsgs
		log "Inbox: " & total & " messages — scanning..."
		
		set scanned to 0
		set movedCount to 0
		
		repeat with m in allMsgs
			set s to sender of m
			set targetFolder to my getFolder(s, accountName)
			
			if targetFolder is not "" then
				if liveMode then
					-- MPC: Order Emails and Payouts are under @ep mailbox
					if accountName is "MPC" and (targetFolder is "Order Emails" or targetFolder is "Payouts") then
						move m to mailbox targetFolder of mailbox "@ep" of acct
					else
						move m to mailbox targetFolder of acct
					end if
					set movedCount to movedCount + 1
				end if
			end if
			
			set scanned to scanned + 1
			if scanned mod 500 = 0 then
				log "  Scanned " & scanned & "/" & total & " — " & movedCount & " filed"
			end if
		end repeat
		
		log "=== Done: filed " & movedCount & " messages ==="
	end tell
end run
