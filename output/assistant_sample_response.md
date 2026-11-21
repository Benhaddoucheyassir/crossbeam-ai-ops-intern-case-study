# Monday briefing (snapshot 2026-11-16)

> The snapshot is 5 days old. Days-to-renewal figures below are as of Nov 16, so each deadline is now 5 days closer.

## A. Executive summary
- Six of your 17 active accounts need attention, with $15,625 of MRR involved. Two are CRITICAL, one is HIGH (Renewal + Seat Mismatch), two are HIGH (Expansion) and one is HIGH (Contact Hygiene).
- Biggest risks: Brightpath Learning ($3,000 MRR) and Juniper Row ($625 MRR) have collapsing or zero usage ahead of renewal. Halcyon Travel ($2,000 MRR) renews on Nov 30 with conflicting seat and ARR figures between billing and CRM.
- Best expansion: Halvorsen Freight and Kestrel Payments both have seat demand above purchased seats, with real signals behind it.
- Contact gap: Sable Insurance has no active contacts.

## B. Priority accounts

### 1. Brightpath Learning Inc: CRITICAL
- MRR: $3,000. Renewal: 34 days (about Dec 20).
- Seats: 30 purchased, 28 accepted, but only 4 active users in Oct. That is 13% utilization.
- Usage: active users fell 11 -> 7 -> 4 (-43%). The product-qualified account (PQA) score is 22 and there are no add-seat clicks.
- Contacts: 2 active.
- Why it matters: this is the fastest-declining usage in the book, with a renewal close enough that a downgrade or cancellation decision is likely already forming.
- Next action: reach out to one of the 2 active contacts this week. Open with an adoption review: why did usage fall, and what would get the other 24 or so accepted seats active?

### 2. Juniper Row: CRITICAL
- MRR: $625. Renewal: 50 days (about Jan 5).
- Seats: 5 purchased and 5 accepted, with 0 active users in Aug, Sep and Oct. That is 0% utilization.
- Contacts: only 1 active, so there is no backup.
- Read: the seats were accepted but never used. This looks like an onboarding failure rather than a decline.
- Next action: contact the one active contact to find the blocker and offer an onboarding session. In the same conversation, ask who else should be involved.

### 3. Halcyon Travel: HIGH (Renewal + Seat Mismatch)
- MRR: $2,000. Renewal: 14 days at snapshot (Nov 30), now about 9 days away.
- Seats: billing shows 30, CRM shows 50, accepted seats are 18, and 16 users are active. That is 53% utilization.
- ARR conflict: billing shows $24,000 and CRM shows $40,000, a $16,000 gap. The data-mismatch flag is set.
- Contacts: 2 active.
- Why it matters: the renewal is imminent, and the CRM appears to overstate the account.
- Read: the customer is paying for roughly 12 more seats than the 18 it uses, so expect right-sizing pressure.
- Next action: confirm the correct seat count and ARR with RevOps before you quote. Then contact the renewal owner on the customer side with a right-sized proposal.

### 4. Halvorsen Freight AS: HIGH (Expansion)
- MRR: $4,000. Renewal: 105 days.
- Seats: 20 purchased and 20 accepted, with 3 pending invites and 2 seat requests. Total demand is 25, so the gap is 5 seats. Utilization is 90% and usage is up 6%.
- Signals: 5 add-seat clicks in 90 days and a PQA score of 88.
- Contacts: 2 active.
- Next action: propose a 5-seat expansion. At the current $200 per seat per month, that is roughly $1,000 of added MRR. This is my estimate from the account's own price per seat, not a quoted figure.

### 5. Kestrel Payments: HIGH (Expansion)
- MRR: $3,500. Renewal: 258 days.
- Seats: 25 purchased and 24 accepted, with 6 pending invites and 4 seat requests. Total demand is 34, so the gap is 9 seats. Utilization is 84%.
- Signals: 9 add-seat clicks in 90 days and a PQA score of 79.
- Contacts: 2 active.
- Next action: propose a 9-seat expansion. At $140 per seat per month, that is roughly $1,260 of added MRR (same estimating method as above). There is no renewal pressure, so this can wait until after the urgent items.

### 6. Sable Insurance: HIGH (Contact Hygiene)
- MRR: $2,500. Renewal: 124 days.
- Seats: 20 purchased and 16 accepted, which is 60% utilization.
- Usage: a slight dip from 13 to 12 active users (-7.7%).
- Contacts: 0 active, and the no-contacts flag is set.
- Next action: identify a valid alternative contact through the account's other channels, such as the customer's own users or your internal relationship notes.
- Not available: the data doesn't say why there are no active contacts. A departed employee or a bounced email are possible, but I can't tell which. I'm not suggesting any outreach to specific people.

## C. Action plan

### Do today
- Halcyon: ask RevOps to reconcile seats (30 vs 50) and ARR ($24K vs $40K). Outcome: you quote the renewal on correct numbers.
- Brightpath: contact an active contact to schedule an adoption review. Outcome: you learn why usage fell while there are still about 4 weeks to act.
- Juniper Row: contact the single active contact about the zero usage. Outcome: you find out whether this is a blocker you can fix.

### Do this week
- Halcyon: send the right-sized renewal proposal. Outcome: the renewal is secured before Nov 30 on seat counts the customer will accept.
- Sable: find a valid alternative contact. Outcome: you re-establish a relationship before the 124-day renewal window gets close.
- Halvorsen and Kestrel: send expansion proposals (+5 and +9 seats). Outcome: roughly $2,260 of estimated added MRR, with both customers already showing demand.

### Monitor
- Quillon Health: it has the largest MRR in the book at $7,500 and renews in 91 days. A shadow workspace (ORG-1031) is flagged, and priority is LOW. Outcome: an early check on whether the shadow workspace affects the renewal.
- Arbor Civic: 4 of 10 seats are accepted and flat usage means 30% utilization, with renewal in 104 days. Outcome: you spot downsell risk before the renewal talk.
- Brisk Mobility: 3 of 10 seats are accepted, with 4 invites pending and first activity only in Oct. Outcome: you see whether adoption is really starting.

## D. Data quality warnings
- Contact detail gaps: customer_360.json has no former-employee or bounced-email fields. I can only see the active-contact count, so I can't tell whether any named person has left or bounced. Sable is the one account with a contact-hygiene flag.
- Tessel Inc. ($2,500 MRR, renews in 91 days): it has no CRM link, so CRM seats, ARR and renewal date are all empty. Active-contact count and the no-contacts flag are also missing. Contact status is unknown and needs fixing.
- Halcyon Travel: CRM and billing disagree on seats and ARR, as noted above.
- Marlowe Analytics ($2,000 MRR): the CRM links to ORG-1004, but the primary org is ORG-1041, and ORG-1004 is listed as the shadow workspace. The two look swapped.
- Ostrava Robotics ($1,000 MRR): the CRM has no product org ID, although billing maps it to ORG-1010.
- Fenwick Labs ($800 MRR): there is no product-usage data at all (no primary org, verification status, seats or user counts), so its health can't be assessed.
- Quillon Health: has an unresolved shadow workspace, as noted above.
