# RULES.md: AI Ops Pipeline Business & Data Rules

This document outlines the deterministic rules governing the Crossbeam AI Ops pipeline, mapping each rule directly to its underlying SQL query and rationale.

## 1. Customer Universe Definition
- **Rule:** A Customer is defined strictly as an account with an `active` subscription in `billing_subscriptions.csv`.
- **SQL Implementation:** `src/sql/01_billing_universe.sql` (`WHERE status = 'active'`).
- **Rationale:** Billing is the absolute financial source of truth. CRM often contains prospects, former/canceled accounts (e.g., Pellucid Bank), and deleted records (`is_deleted = true`).

## 2. Workspace & Domain Resolution
- **Rule:** For each active billing customer, resolve to a primary product workspace (`org_id`) using domain matching (`billing_domain` = `workspaces.domain`). Prioritize `verified` and non-dormant workspaces.
- **SQL Implementation:** `src/sql/03_workspace_resolution.sql` (Window function ranking by verification status, dormancy, and recency).
- **Rationale:** Companies may have multiple workspaces (e.g., Quillon Health verified vs. Quillon Marketing pending). We must never attribute unverified or shadow usage to the primary customer record.

## 3. Trust Hierarchy
- **Rule:** When data conflicts between systems, apply the hierarchy: `Billing > CRM > Product / Activity`.
- **SQL Implementation:** `src/sql/02_crm_mapping.sql` and `src/sql/04_usage_and_contacts.sql`.
- **Rationale:** CRM capacity (`seats_purchased`, `arr_usd`) frequently lags behind Billing updates (e.g., Halcyon Travel where Billing has 30 seats / $2,000 MRR but CRM lists 50 seats / $40,000 ARR). Billing must govern revenue and seat counts.

## 4. Contact Hygiene & Safety Guardrails
- **Rule:** Never recommend contacting any individual where `left_company = true` or whose email appears in `activity.csv` with `bounced = true`. Every customer must have at least 2 active contacts.
- **SQL Implementation:** `src/sql/04_usage_and_contacts.sql` and `src/sql/05_priority_scoring.sql`.
- **Rationale:** Prevents embarrassing outreach to departed employees or nonexistent email addresses, while flagging accounts at risk of losing internal champions (`active_contacts_count < 2`).

## 5. Renewal Window, Seat Mismatch & Priority Scoring
- **Rule:** 
  - **CRITICAL:** Imminent renewal within 90 days AND low usage/utilization (e.g., Brightpath Learning, Juniper Row).
  - **HIGH (Renewal + Seat Mismatch):** Imminent renewal within 30 days AND a data mismatch between Billing and CRM seat/ARR counts (e.g., Halcyon Travel).
  - **HIGH (Expansion):** Seat demand exceeds purchased seats.
  - **HIGH (Contact Hygiene):** Fewer than 2 active contacts.
- **SQL Implementation:** `src/sql/05_priority_scoring.sql`.
- **Rationale:** Ensures ASM attention targets active churn risks, commercial quote blockers (stale CRM data before renewal), expansion opportunities, and vulnerable contact hygiene without inflating raw renewal priority.
