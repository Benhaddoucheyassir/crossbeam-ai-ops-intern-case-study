# DECISION_LOG.md: Key Engineering Decisions & AI Guardrails

This log records major architectural decisions, edge cases encountered during data ingestion, and corrections made during development.

## Decision 1: Customer Universe Anchored in Billing (Not CRM)
- **Context:** The obvious approach is to start with `crm_accounts.csv`. However, CRM contains prospects, deleted accounts, and former customers (e.g., Pellucid Bank which is canceled in billing), while billing subscriptions represent active revenue.
- **Action:** Defined the customer universe strictly from `billing_subscriptions.csv` (`status = 'active'`), left-joining CRM metadata and handling unlinked billing records (e.g., Tessel Inc. with no `crm_account_id`).

## Decision 2: Multi-Workspace Verification Rule
- **Context:** Companies like Quillon Health have multiple workspaces (`ORG-1003` verified vs. `ORG-1031` pending). Blindly summing usage across all workspaces distorts customer health metrics.
- **Action:** Implemented a window function in `03_workspace_resolution.sql` prioritizing `verified` and non-dormant workspaces as the primary org, while aggregating pending/dormant orgs into a `shadow_count` diagnostic flag for RevOps.

## Decision 3: Renewal Window Anchor
- **Context:** CRM `renewal_date` can be stale or missing. Billing subscriptions contain the authoritative `current_period_end`.
- **Action:** Anchored the 90-day renewal window directly on `billing_subscriptions.current_period_end` relative to `--snapshot-date`.

## Decision 4: Contact Hygiene and Bounced Email Filtering
- **Context:** Account Managers waste time reaching out to contacts who have left the company or whose email addresses bounced.
- **Action:** Filtered out contacts where `left_company = true` or `bounced = true` (via `activity.csv`), and flagged accounts with `< 2` active contacts for priority outreach.

## Decision 5: Elevation of Halcyon Travel (Renewal + Seat Mismatch)
- **Context:** Halcyon Travel (`BIL-520`) has an imminent renewal in 14 days (2026-11-30). While usage is stable, there is a significant data discrepancy: Billing shows 30 seats ($2,000 MRR) but CRM shows 50 seats ($40,000 ARR). 
- **Action:** Elevated this to `HIGH (Renewal + Seat Mismatch)`. This is a "Commercial Blocker"—issuing a renewal quote with the wrong seat count or ARR will cause friction and delays. 
- **Product Judgment:** We chose to prioritize `CRITICAL` (active churn risks like Brightpath) at the very top, followed immediately by these "Commercial Blockers". This ensures Sam fixes the "paperwork" for imminent renewals before moving to broader engagement tasks.

## v1 Deterministic Pipeline vs. Raw-CSV Exploratory Pass (2026-11-21)

### Why v1 Kept Core Scoring Deterministic
- **Active universe (`17` accounts):** Anchored to active billing records in `billing_subscriptions.csv` rather than mixing in free/pending workspaces (`ORG-1030` Vantor Logistics, `ORG-1032` Jess's workspace) or separate subsidiary workspaces (`ORG-1007` Corvid Outdoor).
- **Avoided fragile free-text rules in SQL:** `activity.csv` contains rich narrative context (calls and emails), so v1 kept scoring and flags deterministic from structured billing, CRM, workspace, user, and activity counts rather than brittle keyword matching.

### Additional Signals Identified for v2
- **Unanswered / operational `activity.csv` threads:** Marlowe Analytics (`ACT-0005` contract question after `ORG-1004` deletion), Tessel (`ACT-0008` unassigned call with Ama Owusu), Brightpath Learning (`ACT-0003` CFO consolidation review by early December), and Gantry Cloud / Pinecrest Dental (`data_source_connected = false` resulting in `0` overlaps despite active partners).
- **CRM & contact hygiene anomalies:** Duplicate contact records for Priya Nair at Arbor Civic (`CON-1401` and `CON-1402`), stale domain email for Victor Albescu (`@tessellate.example` vs. `@tessel.example`), departed contact Morgan Lindqvist (`CON-0901` at Pellucid Bank), and BD cold-outreach overlap onto existing customer contacts at Corvid Retail (`ACC-008` vs. `ACC-006`).
- **User seat hygiene:** Filtering internal/support test accounts (such as any Crossbeam Support user in `ORG-1011` Kestrel Payments) when computing true customer seat utilization.

## Raw-CSV Comparison & Activity Context Enrichment (2026-11-21)

### What We Compared
- Compared the deterministic DuckDB/SQL pipeline (`17` active billing accounts, `Billing > CRM > Product/Activity` trust hierarchy) against a direct raw-CSV pass across `billing_subscriptions.csv`, `crm_accounts.csv`, `crm_contacts.csv`, `crossbeam_workspaces.csv`, `crossbeam_users.csv`, and `activity.csv`.

### Why Core Scoring Stayed Deterministic (and Why `17` vs. `18` Differed)
- Kept the active customer universe anchored to active billing subscriptions (`17` accounts) and kept priority scores/flags deterministic rather than inferring metrics or counts from raw CSV text or secondary/non-customer workspaces (`ORG-1007` Corvid Outdoor, `ORG-1030` Vantor Logistics, `ORG-1032` Jess's workspace).
- Avoided fragile keyword/text rules inside SQL for `activity.csv` notes.

### Improvement Added vs. Future v2 Scope
- **Added now:** Attached `recent_activities` context from `data/activity.csv` to `customer_360.json` (matched by `crm_account_id` with domain fallback for unlinked records like `Tessel Inc.`) and instructed `claude_skill/SKILL.md` to use those notes strictly as qualitative context without overriding structured metrics or priority scores.
- **Deferred to v2:** Filtering internal/support test accounts out of seat utilization (e.g., internal support account in `ORG-1011` Kestrel Payments), surfacing unconnected data sources with active partners (`ORG-1015` Gantry Cloud, `ORG-1018` Pinecrest Dental), flagging duplicate CRM contacts (`CON-1401`/`CON-1402` Priya Nair) or stale domain emails (`victor.albescu@tessellate.example`), and checking BD prospect outreach collisions against active customer contacts (`ACC-008` vs. `ACC-006` Corvid Retail).

## Snapshot enrichment for 2026-11-16

- **Source hierarchy.** Billing defines the 17 active subscriptions, $492,099.96 in exact billing ARR ($492,000 to the nearest thousand), purchased seats, and renewal dates. CRM supplies linked commercial and contact context. Product and activity supply workspace evidence and qualitative context. The CSV shape and SQL priority rules stay compatible. The JSON adds structured enrichment and the Monday summary adds exact `total_billing_arr`.
- **Seat hygiene.** Classify normalized `@crossbeam.example` emails and the exact normalized name “Crossbeam Support” as internal support. Kestrel’s `U-0267` counts in legacy demand and is excluded from customer demand and accepted customer seats. Compare adjusted demand directly to billing seats. Adjusted accepted-seat utilization uses customer accepted seats divided by billing seats. The monthly active-user counts are workspace aggregates without historical actor attribution, so retain the October MAU utilization as reported.
- **Backup contacts.** Include accepted customer admins with a recorded login by the snapshot and positive 30-day login days, excluding exact normalized addresses that bounced or belong to departed CRM contacts. Join non-dormant workspaces by billing domain and identify the primary workspace. Femi Adeyemi and Jules Lund are primary-workspace candidates. Harper Benn is a candidate for pending `ORG-1031`, which stays separate from Quillon’s primary usage metrics. Arbor’s `CON-1401` and `CON-1402` share a surname and first initial, so surface them as possible duplicates and give Sam Noor Garza as a distinct product admin candidate. Legacy CRM counts still count eligible rows.
- **Usage and connections.** An October halt means positive September usage followed by zero October usage. An October drop means a decline greater than 20%. The comparison has monthly resolution. A disconnected source with positive connected partners exposes the setup issue directly. Gantry and Pinecrest have zero overlapping partners, and Pinecrest’s meeting note reports a connection that Sam should verify against the product state.
- **Activity provenance.** Keep up to five activities on or before the snapshot and expose the original CRM account ID, match basis, and bounce status. Corvid’s `ACC-008` outreach is domain-matched context for `ACC-006`. Tessel’s `ACT-0008` attaches through its billing domain. The older Tessellate correspondence requires a verified alias or CRM link before attribution to Tessel. The pipeline leaves that alias unresolved.
