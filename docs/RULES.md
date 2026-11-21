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
- **Rationale:** CRM capacity (`seats_purchased`, `arr_usd`) frequently lags behind Billing updates (e.g., Halcyon Travel where Billing has 30 seats but CRM lists 50). Billing must govern revenue and seat counts.

## 4. Contact Hygiene & Safety Guardrails
- **Rule:** Never recommend contacting any individual where `left_company = true` or whose email appears in `activity.csv` with `bounced = true`. Every customer must have at least 2 active contacts.
- **SQL Implementation:** `src/sql/04_usage_and_contacts.sql` and `src/sql/05_priority_scoring.sql`.
- **Rationale:** Prevents embarrassing outreach to departed employees or nonexistent email addresses, while flagging accounts at risk of losing internal champions (`active_contacts_count < 2`).

## 5. Renewal Window & Priority Scoring
- **Rule:** The renewal window is anchored on `billing_subscriptions.current_period_end` relative to `--snapshot-date` (`0 <= days_to_renewal <= 90`). Priority is assigned deterministically (CRITICAL, HIGH - Expansion, HIGH - Contact Hygiene, MEDIUM, LOW).
- **SQL Implementation:** `src/sql/05_priority_scoring.sql`.
- **Rationale:** Aligns ASM attention on imminent renewals with low engagement, seat expansion opportunities, and vulnerable contact hygiene.
