# AI Ops Intern Case: Sam's Monday Question

## Overview
This project helps an Account Manager (Sam Ortega) answer: *"Which of my accounts need me this week, why, and what should I do first?"* by reconciling Billing, CRM, Product usage, and Activity data into a deterministic `customer_360` table plus RevOps/BD handoff flags.

## Environment & CLI Parameterization
- **Default Snapshot Date:** `2026-11-16`
- **Default Data Directory:** `./data`
- **CLI Arguments (Required):** Every run script must accept `--data-dir` and `--snapshot-date` (no hard-coded paths or dates).
- **Primary Engine:** DuckDB (SQL-first transformations) orchestrated via Python.

## Core Rules & Trust Hierarchy
1. **Customer Universe:** A **Customer** is a row in `billing_subscriptions.csv` with `status = 'active'` (17 active subscriptions in the `2026-11-16` snapshot). Left-join CRM and product data; never fail hard when a CRM link (`crm_account_id`) is missing or when CRM contains prospects, former customers, or `is_deleted = true` rows.
2. **Trust Hierarchy:** `Billing > CRM > Product/Activity` for commercial truth.
   - Use `billing_subscriptions.csv` as the source of truth for `plan`, `seats` purchased, `mrr_usd` (and `mrr_usd * 12` for ARR), and `current_period_end`.
   - Use `crm_accounts.csv` for relationship/ownership metadata (`owner`, `segment`, `parent_account_id`) and to flag stale fields (`seats_purchased`, `arr_usd`, `renewal_date`, missing `product_org_id`, or company rebrands).
3. **Workspace (`org_id`) Resolution:**
   - Prefer a `verified`, non-dormant workspace (`verification_status = 'verified'` and `is_dormant = false`) matching `product_org_id` (when valid) or matching domain (`billing_domain` / normalized CRM `website` domain).
   - Exclude `failed` or `is_dormant = true` workspaces from active usage metrics, and flag secondary/unverified/shadow workspaces (e.g., `pending` workspaces on the same domain) for RevOps visibility rather than silently treating them as verified primary orgs.
4. **Seat Demand & Renewal Window:**
   - **Seat Demand:** `accepted + pending_invite + seat_request` from `crossbeam_users.csv` for the resolved workspace.
   - **Renewal Window:** `current_period_end` within 90 days of `--snapshot-date` (`0 <= days_to_renewal <= 90`).
5. **Contact Hygiene & Quality Guardrails:**
   - Exclude CRM contacts on deleted CRM accounts (`is_deleted = true`).
   - Never recommend contacting anyone marked `left_company = true` or associated with `bounced = true` in `activity.csv`.
   - Flag every customer with `< 2` active, non-bounced contacts.
6. **Low Usage & Priority Ranking:**
   - Define **Low Usage** transparently in `RULES.md` and SQL (combining low active user coverage relative to seats, recent activity/login gaps, or sharp active-user declines across Aug–Oct).
   - Rank accounts deterministically for Sam with explicit evidence citations, and emit separate diagnostic flags for **RevOps** (never auto-merge or auto-relink CRM records) and **BD** (e.g., prospects or cold outreach hitting existing customers).

## Engineering & Red-Team Expectations
- Keep SQL queries clean, modular, and warehouse-friendly.
- Before finalizing any major step, briefly note any data traps, edge cases, or alternative approaches worth considering.
