-- mail_rules.applescript — Create Mail.app rules for auto-filing
-- Usage: osascript mail_rules.applescript

tell application "Mail"

	-- Create iCloud folders if needed
	try
		if not (exists mailbox "Finance" of account "iCloud") then
			make new mailbox with properties {name:"Finance"} in account "iCloud"
		end if
	end try
	try
		if not (exists mailbox "Orders & Shipping" of account "iCloud") then
			make new mailbox with properties {name:"Orders & Shipping"} in account "iCloud"
		end if
	end try
	try
		if not (exists mailbox "3D & Creative" of account "iCloud") then
			make new mailbox with properties {name:"3D & Creative"} in account "iCloud"
		end if
	end try
	try
		if not (exists mailbox "Business" of account "iCloud") then
			make new mailbox with properties {name:"Business"} in account "iCloud"
		end if
	end try

	-- MPC: Orders → @ep/Order Emails
	set r1 to make new rule with properties {name:"MPC — Orders", enabled:true, all conditions must be met:false}
	tell r1
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"flow@shopify.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"faire.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"info@mainepottery.com"}
	end tell

	-- MPC: Accounting → accounting
	set r2 to make new rule with properties {name:"MPC — Accounting", enabled:true, all conditions must be met:false}
	tell r2
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"squareup.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"key.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"chase.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"americanexpress.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"adp.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"efileservices.net"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"perkinsthompson.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"onerivercpas.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"safesendreturns.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"stripe.com"}
	end tell

	-- MPC: Platforms → Misc
	set r3 to make new rule with properties {name:"MPC — Platforms", enabled:true, all conditions must be met:false}
	tell r3
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"klaviyo.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"brevo.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"shopify.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"googlealerts"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"figma.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"printify.com"}
	end tell

	-- iCloud: Finance
	set r4 to make new rule with properties {name:"iCloud — Finance", enabled:true, all conditions must be met:false}
	tell r4
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"pnc.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"wellsfargo.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"discover.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"paypal.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"applecard.apple"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"citicards"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"bernstein"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"cointracker"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"monarchmoney"}
	end tell

	-- iCloud: Orders & Shipping
	set r5 to make new rule with properties {name:"iCloud — Orders & Shipping", enabled:true, all conditions must be met:false}
	tell r5
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"shipment-tracking@amazon.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"auto-confirm@amazon.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"order-update@amazon.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"informeddelivery"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"fedex.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"orders@oe.target.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"ups.com"}
	end tell

	-- iCloud: 3D & Creative
	set r6 to make new rule with properties {name:"iCloud — 3D & Creative", enabled:true, all conditions must be met:false}
	tell r6
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"bambulab"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"makerworld"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"bambu lab"}
	end tell

	-- iCloud: Business
	set r7 to make new rule with properties {name:"iCloud — Business", enabled:true, all conditions must be met:false}
	tell r7
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"edgecombpotters.com"}
		make new rule condition with properties {rule type:from header, qualifier:does contain value, expression:"mainepottery.com"}
	end tell

	log "=== Done: 7 rules created ==="

end tell
