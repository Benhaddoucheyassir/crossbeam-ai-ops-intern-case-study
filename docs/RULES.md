RULES.md: AI Ops Pipeline Business & Data Rules
This document outlines the deterministic rules governing the Crossbeam AI Ops pipeline, mapping each rule directly to its underlying SQL query and rationale.

1. Customer Universe Definition
- Rule: Define a Customer strictly from active subscriptions in billing_subscriptions.csv (status = 'active'), and report exact billing ARR ($492,099.96; ~$492,000 rounded to the nearest thousand) across the 17 active subscriptions.
- SQL Implementation: src/sql/01_billing_universe.sql.
- Rationale: Billing is the financial source of truth. CRM often includes prospects, canceled/former accounts (e.g., Pellucid Bank), deleted records, or unlinked records (e.g., Tessel Inc.).

2. Workspace & Domain Resolution
- Rule: Normalize billing and workspace domains and resolve a verified, non-dormant primary created by the snapshot. Break ties by newest creation date, then org ID. Keep pending, failed, and dormant workspaces as diagnostic evidence.
- SQL Implementation: src/sql/03_workspace_resolution.sql.
- Rationale: Multi-workspace accounts (such as Quillon Health with ORG-1003 vs. ORG-1031, or Marlowe Analytics with ORG-1041 vs. ORG-1004) distort health metrics if summed blindly.

3. Trust Hierarchy
- Rule: Resolve cross-system conflicts using Billing > CRM > Product / Activity.
- SQL Implementation: src/sql/02_crm_mapping.sql and src/sql/04_usage_and_contacts.sql.
- Rationale: CRM seat/ARR fields can lag behind Billing (e.g., Halcyon Travel with 30 seats / $2,000 MRR in Billing vs. 50 seats / $40,000 ARR in CRM).

4. Contact Hygiene, Backup Admins & Seat Demand Guardrails
- Rule: Exclude departed contacts (left_company = true) and bounced email addresses from recommended outreach, treat possible duplicate CRM contacts as cleanup checks rather than separate active contacts, flag accounts with < 2 active contacts, and separate internal support accounts (@crossbeam.example / "Crossbeam Support") when computing customer seat demand. Surface eligible active product admins as workspace backup contacts while separating product access from renewal decision authority.
- SQL Implementation: src/sql/04_usage_and_contacts.sql and pipeline enrichment.
- Rationale: Prevents outreach to bounced/departed contacts or misreading internal support seats as customer expansion demand, while preserving honest unknowns when data is missing or unverified.

5. Renewal Window, Usage Signals & Priority Scoring
- Rule:
  - CRITICAL: Renewal in 0–90 days with October monthly actives below 25% of purchased seats or a September-to-October drop greater than 20%.
  - HIGH (Renewal + Seat Mismatch): Imminent renewal (within 30 days) with a seat/ARR mismatch between Billing and CRM (e.g., Halcyon Travel).
  - HIGH (Expansion): Seat demand exceeds purchased seats.
  - HIGH (Contact Hygiene): Fewer than 2 active contacts.
- SQL Implementation: src/sql/05_priority_scoring.sql.
- Rationale: Prioritizes active churn risks and imminent quote blockers first, followed by expansion and contact-hygiene actions.
- Evaluation order in SQL: critical, expansion, renewal mismatch within 0–30 days, contact hygiene, usage decline greater than 10%, then low. The briefing orders commercial blockers ahead of expansion. Independent action signals still surface a quote blocker on an expansion-tier row.

6. Evidence and Handoffs

- In `06_action_evidence.sql`, a dated customer login gap of at least 21 days is a review signal. The CRM 45-day flag, monthly usage, and source rolling login counts describe different observations. A blank login date leaves age unknown. Monthly fields cover August through October 2026 because those are the columns supplied by this extract.
- A missing verified workspace at least 30 days after the CRM contract start triggers an onboarding check. A disconnected source with connected partners calls for source verification. Neither flag identifies a root cause.
- An exact normalized email on an active customer and an undeleted prospect triggers outreach review. A narrowly matched inbound list-removal request on that prospect triggers a same-day handoff. Candidate CRM links require a matching contact domain and compatible billing seats, ARR, and renewal date. Candidate evidence is kept separate from authoritative IDs and activities.
- `build_action_signals` in `src/run_pipeline.py` routes issues to Sam, CS, BD, or RevOps. Distinct eligible email count excludes bounced and departed contacts. Possible aliases remain a review item. Non-paying workspaces are outside the portfolio and only verified, active, unlinked free workspaces qualify for BD review.
