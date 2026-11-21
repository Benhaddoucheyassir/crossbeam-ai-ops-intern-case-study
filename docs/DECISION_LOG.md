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
