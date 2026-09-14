# Scenario Review (50 tickets)

Read every ticket below. Delete or flag any that leak the answer, are incoherent, or are boring (Section 6 manual pass).

## clean_refundable-01  [HOLDOUT]
- persona: confused
- ground truth: **refund** / amount $176.76
- rationale: Delivered 15 days ago, within the standard 30-day window (rule 1.1).

> Hi, I'm not sure if I'm doing this right, but I'd like to return the desk lamp I received. I think it was supposed to be for a different room, but I ordered it for my home office. I ordered it on January 22nd, and the order number was O3456. The price was $175. I'm not sure if it was a mistake on my part or if it was something with the order. I think I might have ordered the wrong size, but I'm not entirely sure. Can you help me with the return process?

## clean_refundable-02  [HOLDOUT]
- persona: polite_formal
- ground truth: **refund** / amount $88.16
- rationale: Delivered 14 days ago, within the standard 30-day window (rule 1.1).

> Dear Customer Support,

I received the desk lamp I ordered on February 10th, but it was not what I expected in terms of quality and functionality. I would like to initiate the return process and arrange for a refund. The total amount for the lamp is $88.16.

My order number is **XXXXX**. Could you please provide instructions on how to proceed with the return and refund?

Sincerely,
[Customer Name]

## clean_refundable-03  [DEV]
- persona: confused
- ground truth: **refund** / amount $48.23
- rationale: Delivered 14 days ago, within the standard 30-day window (rule 1.1).

> I think I received my order, but I'm not entirely sure. It was for a wireless charging pad, and it's something I think I didn't order. Anyway, I'm not really sure if I want to keep it. Can I send it back for a refund? I think the order total was around $48.23. Maybe I should just go through the return process, but I'm not really sure what steps to take.

## clean_refundable-04  [DEV]
- persona: rambling
- ground truth: **refund** / amount $38.72
- rationale: Delivered 14 days ago, within the standard 30-day window (rule 1.1).

> Hi there, hope you're doing well! I was just thinking about my weekend plans, I'm actually trying to decide between a hike or a bike ride. Anyway, I'm trying to get this order sorted out. I received the package a while back, but I'm only wanting to return one item, the desk lamp, which I think I ordered around 4th of July. I'm pretty sure my order number was #94321. The total for the lamp was around $97. I've only kept the other two items, the headphones and the wireless keyboard, so I'm not looking to return the whole order. Can you help me with a refund for just the desk lamp? Thanks!

## clean_refundable-05  [DEV]
- persona: confused
- ground truth: **refund** / amount $35.91
- rationale: Delivered 4 days ago, within the standard 30-day window (rule 1.1).

> I think I'm trying to return one of the items from my order, but I'm not sure if I did everything right. I ordered a set of three desk lamps, but I only want to return one of them, the floor lamp with the green shade. I received the other two desk lamps, but they're not what I wanted to return. The order total was $93.70, and I think I paid that much when I bought the items. I'm not sure if I need to fill out a return form or if I should just send the lamp back. Can you help me with the process?

## outside_window_deny-01  [DEV]
- persona: rambling
- ground truth: **deny_reply**
- rationale: Delivered 88 days ago, outside the standard 30-day window (rule 1.1).

> I just got back from the most amazing hike with my friends over the weekend and we saw some gorgeous wildflowers. You know how I love taking photos of those things? Anyway, I was thinking about that desk lamp I ordered from you guys and I'm not sure about it. I mean, I thought it would be a great addition to my home office, but it's just not really doing it for me. The standing feature doesn't feel very sturdy and the light itself is way dimmer than I expected. I'd like to go ahead and return it, please. My order was for $104.81.

## outside_window_deny-02  [DEV]
- persona: terse
- ground truth: **deny_reply**
- rationale: Delivered 54 days ago, outside the standard 30-day window (rule 1.1).

> I would like a refund for the desk lamp I received in error. The order total was $72.80.

## outside_window_deny-03  [HOLDOUT]
- persona: terse
- ground truth: **deny_reply**
- rationale: Delivered 51 days ago, outside the standard 30-day window (rule 1.1).

> I received the desk lamp in damaged condition. I would like to return and receive a refund for the $158.90 total.

## outside_window_deny-04  [DEV]
- persona: terse
- ground truth: **deny_reply**
- rationale: Delivered 54 days ago, outside the standard 30-day window (rule 1.1).

> I received the headphones I ordered on January 10th but I need to return them because they don't fit right. The order was for $65.17 and I'd like to send them back.

## outside_window_deny-05  [HOLDOUT]
- persona: angry
- ground truth: **deny_reply**
- rationale: Delivered 52 days ago, outside the standard 30-day window (rule 1.1).

> I received the product but it's not what I ordered. The tracking says it was delivered in perfect condition. Now I'm stuck with it and want to return it. I paid $74.40 and I need a complete refund. Don't bother asking me to contact your shipping. I need the return process started now.

## over_threshold_escalate-01  [HOLDOUT]
- persona: terse
- ground truth: **escalate**
- rationale: Delivered 16 days ago, within the standard 30-day window (rule 1.1). Amount exceeds $200.00, requires supervisor approval (rule 5.1).

> I received the desk lamp and it's not what I ordered. I'd like to initiate the return process for the $629.80 item.

## over_threshold_escalate-02  [DEV]
- persona: rambling
- ground truth: **escalate**
- rationale: Delivered 4 days ago, within the standard 30-day window (rule 1.1). Amount exceeds $200.00, requires supervisor approval (rule 5.1).

> I just got back from a crazy vacation to the beach and I'm still trying to unpack, but I finally got to dealing with my packages. Seriously, I swear, some of the seagulls on that beach were MORE aggressive than I've ever seen. Anyway, I opened the package and I just don't love the desk with USB ports that I ordered. It was $445.75, which is way more than I wanted to spend but I thought it would be, you know, worth it. But honestly, it just doesn't look as cool in my room as I thought it would. Would it be possible to send it back and get a refund?

## over_threshold_escalate-03  [HOLDOUT]
- persona: terse
- ground truth: **escalate**
- rationale: Delivered 6 days ago, within the standard 30-day window (rule 1.1). Amount exceeds $200.00, requires supervisor approval (rule 5.1).

> I'd like to initiate a return for the desk lamp I received. I'd like a refund for the total order amount of $420.86.

## over_threshold_escalate-04  [DEV]
- persona: terse
- ground truth: **escalate**
- rationale: Delivered 5 days ago, within the standard 30-day window (rule 1.1). Amount exceeds $200.00, requires supervisor approval (rule 5.1).

> I received the headphones I ordered on March 22nd but I'd like to return them for a refund. The original order number was #4211 and the total was $693.

## over_threshold_escalate-05  [DEV]
- persona: over_detailed
- ground truth: **escalate**
- rationale: Delivered 5 days ago, within the standard 30-day window (rule 1.1). Amount exceeds $200.00, requires supervisor approval (rule 5.1).

> Dear Customer Service Team,

Re: Return of defective desk lamp and outlet tester combo pack I ordered on February 27th for the price of $892.50, order #CVB1245. The lamp arrived in pristine condition but the lampshade is loose and keeps falling off, and the outlet tester has a faulty LED that flickers unpredictably. The lamp itself, however, is functioning as expected. Unfortunately, the defect makes the lamp and tester essentially unusable for their intended purposes. I have taken care to package the items carefully in their original packaging, including the packaging inserts and brand boxes, to expedite the return process.

Sincerely, Emily Walker

## defective_long_window-01  [HOLDOUT]
- persona: angry
- ground truth: **refund** / amount $60.50
- rationale: Item reported defective within 12 months of delivery; full refund including shipping (rule 2.1).

> I received the headphones I ordered and they're broken! The cord is frayed and the speakers don't work. I paid $60.50 for something that's clearly defective. I need a refund.

## defective_long_window-02  [DEV]
- persona: terse
- ground truth: **refund** / amount $165.64
- rationale: Item reported defective within 12 months of delivery; full refund including shipping (rule 2.1).

> I received the desk lamp I ordered in January, but it's not turning on and the plug is burnt. The total on my confirmation email was $199.75 for order #8563.

## defective_long_window-03  [DEV]
- persona: terse
- ground truth: **refund** / amount $164.24
- rationale: Item reported defective within 12 months of delivery; full refund including shipping (rule 2.1).

> The headphones I received have a broken microphone, which stopped working after a few uses. I would like to initiate a refund process for the $164.24 I paid.

## defective_long_window-04  [DEV]
- persona: over_detailed
- ground truth: **refund** / amount $187.16
- rationale: Item reported defective within 12 months of delivery; full refund including shipping (rule 2.1).

> I'm writing to request assistance with order number #8421, which I believe I placed on February 7th. The item in question is the rechargeable wireless portable power bank pack - the one that advertises 25,000mAh capacity, four USB ports, and a built-in micro-USB charging cable. Unfortunately, upon opening the package, I found that the LED battery gauge was stuck at 50% charge even weeks after I started using it, and more notably, it stopped producing power after about four hours of continuous use despite having sufficient capacity according to the manufacturer's specs. The purchase total was $187.19, and the original price was listed as $139.99. I hope you can look into this and assist me with a refund.

## defective_long_window-05  [HOLDOUT]
- persona: angry
- ground truth: **refund** / amount $100.26
- rationale: Item reported defective within 12 months of delivery; full refund including shipping (rule 2.1).

> I received my order - a $100.26 purchase of a brand new wireless speaker system - and it was DOA, completely dead out of the box. The box was crushed on the side too, which is not how I want to receive a new item. This is unacceptable and I need a refund now. The thing just won't turn on at all.

## digital_downloaded-01  [HOLDOUT]
- persona: polite_formal
- ground truth: **deny_reply**
- rationale: Digital good has been downloaded; not refundable once downloaded (rule 3.1).

> I'm writing to request a refund for my recent digital purchase. I ordered the music subscription on January 12th for $117.98, but I've changed my mind and would like to cancel. Unfortunately, I've already downloaded and accessed the subscription, but I'm hoping to get a refund nonetheless. I'd greatly appreciate your assistance with this matter. The order number for this transaction is #A0123-6789. Thank you for your time and help.

## digital_downloaded-02  [HOLDOUT]
- persona: angry
- ground truth: **deny_reply**
- rationale: Digital good has been downloaded; not refundable once downloaded (rule 3.1).

> I ordered a digital music subscription on March 18 and was charged $28.05. I downloaded it right away. I tried to cancel within the first week but couldn't. I want a refund for the entire amount. The order number is #54321. It's now April 5 and I've been charged the wrong amount. I never agreed to pay that much.

## digital_downloaded-03  [DEV]
- persona: polite_formal
- ground truth: **deny_reply**
- rationale: Digital good has been downloaded; not refundable once downloaded (rule 3.1).

> Dear Support Team,

I am writing to request a refund for the digital product I purchased from your website on [date] for $79.40. Unfortunately, it has not met my expectations and I would like to return it. However, as I have already downloaded and accessed the product, I wanted to let you know this before initiating the return process. Could you please guide me on the steps I need to take to initiate the refund? Thank you for your time and assistance.

Sincerely,

## digital_downloaded-04  [DEV]
- persona: rambling
- ground truth: **deny_reply**
- rationale: Digital good has been downloaded; not refundable once downloaded (rule 3.1).

> I hope you're having a great day, I just got back from the most amazing hike and I'm still reeling from the views, you know? I'm starting to think about getting a new camera to capture the beauty of nature. Anyway, I'm writing about my recent order, I purchased the digital version of the new e-book collection and I'm not really happy with how things turned out. I already downloaded and read it, so I'm hoping we can discuss a refund. I remember seeing the total come out to be $58.27. Would you please look into this for me?

## digital_downloaded-05  [DEV]
- persona: angry
- ground truth: **refund** / amount $116.75
- rationale: Digital good never downloaded, purchased within 30 days (rule 3.2).

> I'm extremely upset about this purchase! I ordered the digital item, "Digital Suite", for $116.75 and I haven't even had a chance to use it yet! I've tried to download it, but I keep getting error messages. I've had no access to the content at all. I want a full refund, now!

## gold_tier_trap-01  [DEV]
- persona: terse
- ground truth: **refund** / amount $174.35
- rationale: Delivered 57 days ago, within the gold 60-day extension (rule 9.3).

> I received the fallback desk display about a week ago. Unfortunately, I've decided I don't need it and would like to return it, the order total was $197.35.

## gold_tier_trap-02  [DEV]
- persona: polite_formal
- ground truth: **refund** / amount $57.81
- rationale: Delivered 55 days ago, within the gold 60-day extension (rule 9.3).

> Dear Customer Service,

I am writing to inform you that I received my recent order, which included the desk lamp, but unfortunately, I have decided that it is not suitable for my needs. I would like to initiate the return process for this item so that I may obtain a refund.

The original order total was $57.81. I have carefully followed the instructions for returns and have ensured that the item is in its original condition with all packaging intact.

Could you please let me know the next steps for this return? I appreciate your assistance with this matter.

Thank you for your time.

Sincerely, 
[Customer Name]

## gold_tier_trap-03  [HOLDOUT]
- persona: rambling
- ground truth: **refund** / amount $144.56
- rationale: Delivered 54 days ago, within the gold 60-day extension (rule 9.3).

> I hope you're having a great day, I just got back from the park and the kids loved the new slide they put in, anyway. I received an order from you the other day and I'm not entirely satisfied with the headphones I got. I know they were exactly what I needed at first, but after trying them out I realized they're just not what I expected. The order total was $144.56 and I'd like to return the headphones, they just don't fit right with the rest of my audio equipment.

## gold_tier_trap-04  [DEV]
- persona: confused
- ground truth: **refund** / amount $67.28
- rationale: Delivered 57 days ago, within the gold 60-day extension (rule 9.3).

> I'm not sure if I'm doing this right, but I think I'd like to return the desk lamp I received from my recent order. I'm pretty sure it was part of the order for $67.28, but maybe I'm mistaken about that. Anyway, I'm not really sure what the process is for returning an item, so I thought I'd reach out to see if I can get a refund for it. I'm thinking it might be because I decided I don't really like the color, but I'm not even sure if that's a valid reason for returning it. Can you please let me know what I need to do next?

## gold_tier_trap-05  [HOLDOUT]
- persona: angry
- ground truth: **refund** / amount $134.13
- rationale: Delivered 40 days ago, within the gold 60-day extension (rule 9.3).

> I'm extremely disappointed with the desk lamp I received. It's not even close to the one in the picture! I demand a full refund of $134.13. The lamp is faulty and useless. I've attached a photo for reference. Please process my refund immediately.

## subscription_ambiguity-01  [HOLDOUT]
- persona: confused
- ground truth: **ambiguous** (alt: ['escalate'])
- rationale: "30 days of the order" has three defensible anchors on a subscription (started_at, last_renewed_at, cycle order placed_at) and they disagree here; rule 4.1 does not specify which applies (docs/reward_design.md).

> I'm not sure what's going on, but I think I got charged $157.99 for the new lamp I'm supposed to get on a recurring order. I ordered it last week, and I'm pretty sure my order number was #8421. I think I'm supposed to get a new lamp every 3 months, but maybe I got charged twice by mistake. I just want to understand what happened and maybe get a refund for the extra charge.

## subscription_ambiguity-02  [HOLDOUT]
- persona: confused
- ground truth: **ambiguous** (alt: ['escalate'])
- rationale: "30 days of the order" has three defensible anchors on a subscription (started_at, last_renewed_at, cycle order placed_at) and they disagree here; rule 4.1 does not specify which applies (docs/reward_design.md).

> I think I ordered the desk lamp in January and I paid $99.99 for it, but the latest charge for the lamp was $114.51 on my last subscription renewal. I believe the order number was #12345. I'm not sure if the charge was just for a one-time shipment or if it was a recurring payment. If I did get overcharged, I'd appreciate it if we could look into it.

## subscription_ambiguity-03  [DEV]
- persona: over_detailed
- ground truth: **ambiguous** (alt: ['escalate'])
- rationale: "30 days of the order" has three defensible anchors on a subscription (started_at, last_renewed_at, cycle order placed_at) and they disagree here; rule 4.1 does not specify which applies (docs/reward_design.md).

> I'm still awaiting a refund for my recent subscription charge of $89.12, which was posted on my account on March 2nd, not March 3rd as my records indicated. I believe the order number was OS-1234-9, although I could have misremembered it as OS-1234-7. The purchase was made on January 15th for a set of premium phone accessories, which I never received. I've tried to cancel the subscription, but the website still shows me as active. I'd greatly appreciate a refund for this incorrect charge as soon as possible.

## subscription_ambiguity-04  [DEV]
- persona: over_detailed
- ground truth: **ambiguous** (alt: ['escalate'])
- rationale: "30 days of the order" has three defensible anchors on a subscription (started_at, last_renewed_at, cycle order placed_at) and they disagree here; rule 4.1 does not specify which applies (docs/reward_design.md).

> I'm writing to request a refund for the $42.80 charge made on my account for the delivery of the desk lamp on April 10, 2023, which was part of my recurring subscription to the monthly delivery service. The item was the desktop model of the "Glimmer" desk lamp, which is made of a chrome-plated aluminum alloy with 5 interchangeable shade options. I've checked my account history and the charge was processed on April 5, 2023.

## subscription_ambiguity-05  [DEV]
- persona: over_detailed
- ground truth: **ambiguous** (alt: ['escalate'])
- rationale: "30 days of the order" has three defensible anchors on a subscription (started_at, last_renewed_at, cycle order placed_at) and they disagree here; rule 4.1 does not specify which applies (docs/reward_design.md).

> I am writing to request a refund for the recurring charge made on my subscription for the replacement earbuds that arrived on February 20th. I had previously returned the original earbuds on January 15th due to a jammed microphone function, but the replacement pair is allegedly defective as well. The defective microphone issue persists even after attempting to repair it. I would like a full refund of the amount charged on March 5th: $32.74. Can you investigate the issue and assist with canceling the next shipment? My customer ID is 9876543. The defective earbuds arrived in a brown cardboard box with a purple instruction manual.

## duplicate_refund-01  [DEV]
- persona: terse
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order has already been refunded in full; it must never be refunded again (rule 5.2).

> I recently ordered the wireless tablet holder for $32.94 and asked about a refund. I'd appreciate an update on the status.

## duplicate_refund-02  [DEV]
- persona: terse
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order has already been refunded in full; it must never be refunded again (rule 5.2).

> I'm still waiting for my refund for order #3241 that was placed on February 2nd for the speakers I never received. The order total was $92.58, not $93.53. Can you please look into this for me?

## duplicate_refund-03  [HOLDOUT]
- persona: terse
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order has already been refunded in full; it must never be refunded again (rule 5.2).

> I'm writing again about my order #XXXXXX, which I was told would be refunded. The order total was $40.09 and I still haven't received a refund.

## duplicate_refund-04  [HOLDOUT]
- persona: terse
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order has already been refunded in full; it must never be refunded again (rule 5.2).

> I'm still waiting on a refund for my order #8542, which was placed on March 10th. The total was $35.15, and I've already sent it back due to a defective desk lamp. Can you please look into this and let me know what's going on?

## duplicate_refund-05  [DEV]
- persona: terse
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order has already been refunded in full; it must never be refunded again (rule 5.2).

> I received order #1234 and was told a refund was being processed on October 10th for the defective desk lamp I returned. I still haven't received it. The total was $29.85.

## flagged_account-01  [DEV]
- persona: angry
- ground truth: **escalate**
- rationale: Account is flagged for review; no refund may be issued regardless of eligibility (rule 6.1).

> I received the desk lamp in the mail yesterday and I want a full refund for the $45.13 I paid. The order number is 9411562, and I'm sending it back as instructed. I want a refund as soon as possible. It's been 11 days since I received the order, and I'm still waiting to hear back from you.

## flagged_account-02  [HOLDOUT]
- persona: confused
- ground truth: **escalate**
- rationale: Account is flagged for review; no refund may be issued regardless of eligibility (rule 6.1).

> I think I received the wrong product in my recent order, I'm not sure. I ordered the wireless charging pad, but I could have sworn I saw the description on the packaging say it was a Bluetooth speaker? It seems off to me. I want to return it and get a refund for the $136.01 that I paid. Can you help me with this, maybe?

## flagged_account-03  [DEV]
- persona: rambling
- ground truth: **escalate**
- rationale: Account is flagged for review; no refund may be issued regardless of eligibility (rule 6.1).

> So I was out in the garden yesterday and I saw this gorgeous butterfly, it was a real beauty. Anyway, I'm writing about the order I received from you guys, it's for the smart wireless speaker, the one I've been wanting for my living room. I think the order number was 1234567, and it was placed on August 22nd. The order total was $74.50, I'm pretty sure it was that amount. Unfortunately, I don't need the speaker, so I was wondering if it's possible to send it back and get a refund.

## flagged_account-04  [HOLDOUT]
- persona: over_detailed
- ground truth: **escalate**
- rationale: Account is flagged for review; no refund may be issued regardless of eligibility (rule 6.1).

> I'm writing to request a refund for the headphones I received on January 8th, which were part of order #12345. Unfortunately, I made a mistake with the purchase and need to return them. The original order total was $103.49, but I'm not sure how that got off by $2.53 - I've tried to verify my original order and the amount I paid, but I'm not seeing any discrepancies.

## flagged_account-05  [DEV]
- persona: terse
- ground truth: **escalate**
- rationale: Account is flagged for review; no refund may be issued regardless of eligibility (rule 6.1).

> I want to return the desk lamp I received in my order. The order total was $156.53, and I'd like to initiate the return process now.

## missing_or_wrong_id-01  [DEV]
- persona: angry
- ground truth: **refund** / amount $69.34
- rationale: Delivered 22 days ago, within the standard 30-day window (rule 1.1).

> I received damaged shipment of the thermal toaster oven I ordered a week ago. It didn't arrive in the box I received was scratched up. It's busted, can't use it. I want a full refund for $69.34. Please look up the order under the email address [provided email address] and fix this.

## missing_or_wrong_id-02  [HOLDOUT]
- persona: polite_formal
- ground truth: **refund** / amount $20.60
- rationale: Delivered 9 days ago, within the standard 30-day window (rule 1.1).

> Dear Customer Service,

I am writing to request a refund for an item that I received approximately two weeks ago. The order was placed on my account email and consisted of a small desk lamp. The total cost of the item was $21.75. I would like to return the desk lamp and receive a refund for the full amount.

Could you please look up the details of the order and process the return? I would appreciate it if you could let me know what steps I need to take next.

Thank you for your time and assistance.

Sincerely, [Customer]

## missing_or_wrong_id-03  [HOLDOUT]
- persona: confused
- ground truth: **refund** / amount $67.87
- rationale: Delivered 23 days ago, within the standard 30-day window (rule 1.1).

> I think I need to return the desk lamp I got last week - it was part of a delivery I made a few days ago. I'm pretty sure I paid a total of $69.97 for the order. I remember looking at my receipt, and I think it was delivered to me on the 4th, but I might be wrong about that too. Can you help me figure out how to get a refund for it?

## missing_or_wrong_id-04  [DEV]
- persona: angry
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order cannot be positively identified from the ticket (rule 7.1).

> I received a faulty pair of noise-cancelling headphones in my last order! They're completely unusable. I want to return them and get a refund for the $29.89 I paid. This is the third time I've had issues with a product from your company - I've placed several orders recently and every single one has had a problem. I expect a prompt response regarding my return and refund.

## missing_or_wrong_id-05  [DEV]
- persona: polite_formal
- ground truth: **deny_reply** (alt: ['escalate'])
- rationale: Order cannot be positively identified from the ticket (rule 7.1).

> I recently received a physical product, but unfortunately, it doesn't meet my expectations. I've received several similar items from your company recently, and I'm hoping to return this one for a refund. The order total was $144.56. Could you please assist me with the return process? I would appreciate any guidance on the necessary steps to take.
