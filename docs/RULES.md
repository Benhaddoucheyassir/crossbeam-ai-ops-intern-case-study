RULES.md: AI Ops Pipeline Business & Data Rules
This document outlines the deterministic rules governing the Crossbeam AI Ops pipeline, mapping each rule directly to its underlying SQL query and rationale.

1. Customer Universe Definition
- Rule: Define a Customer strictly from active subscriptions in billing_subscriptions.csv (status = 'active'), and report exact billing ARR ($492,099.96; ~$492,000 rounded to the nearest thousand) across the 17 active subscriptions.
- SQL Implementation: src/sql/01_billing_universe.sql.
- Rationale: Billing is the financial source of truth. CRM often includes prospects, canceled/former accounts (e.g., Pellucid Bank), deleted records, or unlinked records (e.g., Tessel Inc.).

2. Workspace & Domain Resolution
- Rule: Resolve each active billing customer to a primary product workspace (org_id) via domain matching (billing_domain = workspaces.domain), prioritizing verified, non-dormant workspaces while isolating secondary, pending, or unverified workspaces as diagnostic context.
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
  - CRITICAL: Renewal within 90 days with low utilization or sharp usage drop (e.g., Brightpath Learning, Juniper Row).
  - HIGH (Renewal + Seat Mismatch): Imminent renewal (within 30 days) with a seat/ARR mismatch between Billing and CRM (e.g., Halcyon Travel).
  - HIGH (Expansion): Seat demand exceeds purchased seats.
  - HIGH (Contact Hygiene): Fewer than 2 active contacts.
- SQL Implementation: src/sql/05_priority_scoring.sql.
- Rationale: Prioritizes active churn risks and imminent quote blockers first, followed by expansion and contact-hygiene actions.
