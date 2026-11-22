# Key Engineering Decisions & AI Guardrails (`DECISION_LOG.md`)

This log documents the architectural choices, raw-CSV comparisons, skill/pipeline iterations, and data-hygiene edge cases encountered while building Sam Ortega's Monday AI Ops assistant for the `2026-11-16` snapshot. Rather than hiding discrepancies or tuning scores around raw CSV text, each iteration keeps the deterministic SQL spine intact while tightening data grounding and surfacing edge cases cleanly.

---

## 1. Core Architecture & Commercial Grounding

### Decision 1: Customer Universe Anchored in Billing (`Billing > CRM > Product/Activity`)
- **Problem:** Starting from `crm_accounts.csv` pulls in prospects, duplicate/unlinked records, and churned accounts (such as Pellucid Bank, which is canceled in billing), while missing active billing subscriptions that lack a clean CRM link (such as Tessel Inc.).
- **Decision:** Anchor the active customer universe strictly to `billing_subscriptions.csv` (`17` active subscriptions totaling `$492,099.96` in exact billing ARR, or `~$492,000` rounded to the nearest thousand), left-joining CRM metadata and product/activity signals without letting unverified workspaces inflate active counts.

### Decision 2: Authoritative Renewal Dates via Billing
- **Problem:** CRM `renewal_date` fields can drift or go stale compared to actual subscription billing periods.
- **Decision:** Anchor renewal countdowns and windows (`days_to_renewal`) directly to `billing_subscriptions.current_period_end` relative to `--snapshot-date` (`2026-11-16`).

### Decision 3: Multi-Workspace Selection & Shadow Workspace Isolation
- **Problem:** Accounts with multiple workspaces (such as Quillon Health with verified `ORG-1003` vs. pending `ORG-1031`, or Marlowe Analytics with `ORG-1041` vs. legacy/deleted `ORG-1004`) distort health metrics if usage is summed blindly across every workspace.
- **Decision:** Use a deterministic window function in `src/sql/03_workspace_resolution.sql` to select a primary workspace (preferring verified, non-dormant workspaces) while isolating secondary/pending/unverified workspaces into diagnostic flags (`shadow_count` / workspace status metadata) for RevOps and AM review.

### Decision 4: Contact Hygiene & Halcyon Travel Renewal + Seat Mismatch
- **Problem:** Outbound renewal outreach breaks down when primary contacts bounce or have left (`left_company = true` or `bounced = true` in `activity.csv`), or when a renewal quote uses stale CRM seat/ARR figures. Specifically, **Halcyon Travel (`BIL-520`)** renews on `2026-11-30` (14 days from `2026-11-16`) with healthy usage, but Billing reflects `30` seats (`$2,000` MRR / `$24,000` ARR) while CRM still shows `50` seats (`$40,000` ARR)—a `20`-seat and `$16,000` ARR gap.
- **Decision:** Filter out bounced or departed contacts from active contact counts, flag accounts with fewer than two active contacts, and elevate **Halcyon Travel** to `HIGH (Renewal + Seat Mismatch)` right behind `CRITICAL` churn risks so commercial/quote discrepancies are fixed before renewal paperwork goes out.

---

## 2. Activity Context & Raw-CSV Comparison Iterations

### Iteration A: Attaching `recent_activities` Without Overriding Deterministic Scores
- **Difference Observed (Pipeline vs. Raw-CSV Run):** A direct pass over the raw CSVs surfaced rich narrative context from `activity.csv`—such as Ilse Brouwer's `2026-10-27` note on Halcyon's June downgrade, Gwen Ashby's `2026-07-18` partner-program pause at Brightpath, the `2026-10-30` CFO consolidation-review note at Brightpath, Eva Sorensen's `2026-01-05` post-busy-season note at Juniper Row, and Ama Owusu's `2026-10-08` unassigned call for Tessel—whereas an early pipeline draft only exposed aggregate counts and flags.
- **Improvement Made:** Attached `recent_activities` (up to five activities on or before `--snapshot-date`) to `customer_360.json`, matching by `crm_account_id` with a billing-domain fallback for unlinked records like Tessel Inc., while keeping priority tiers and scores deterministic in SQL rather than relying on fragile keyword rules.

### Iteration B: Skill & Grounding Upgrade (Preventing Raw-CSV Overclaims)
- **Difference Observed (Raw-CSV Prose vs. Skill-Governed Briefing):** When a raw-CSV pass wrote narrative prose directly, it occasionally over-interpreted evidence—for example, treating a bounced email as proof that Dana Okafor had left Sable Insurance, assuming Rafael Ibarra was confirmed as the named CFO in the note, or treating raw CSV observations with the same certainty as structured billing/product state.
- **Improvement Made:** Updated `claude_skill/SKILL.md` to enforce strict grounding rules:
  1. Pull all counts, MRR/ARR figures, renewal dates, and priority labels from structured JSON fields (`billing_mrr`, `billing_arr`, `billing_seats`, `current_period_end`, `days_to_renewal`, `priority_score`), explicitly labeling `crm_seats`, `crm_arr`, and `crm_renewal_date` when explaining mismatches.
  2. Attribute qualitative notes to `activity_id` and `activity_date`, treat `billing_domain` matches as contextual, and separate verified facts from unknowns or unverified claims.

---

## 3. Cross-Table Hygiene Enrichment & Second Rerun (`2026-11-16`)

Comparing the structured briefing against the raw-CSV pass highlighted specific cross-table signals that needed first-class fields in `customer_360.json` and `monday_summary.json` so the assistant could surface them deterministically:

1. **Internal Support Seat Isolation (`cs-support@crossbeam.example` / `U-0267`):**
   - **Difference Observed:** At Kestrel Payments, raw seat counts (`25` seats; `34` total demand across `24` accepted, `6` pending invites, and `4` seat requests) included an internal Crossbeam Support account (`U-0267` / `cs-support@crossbeam.example`).
   - **Improvement Made:** Added support-seat classification (`@crossbeam.example` and normalized `"Crossbeam Support"`) to compute `total_demand`, `customer_total_demand`, `internal_support_demand`, `customer_expansion_demand`, and `customer_accepted_seat_utilization` alongside raw counts, while keeping workspace-level October MAU utilization as reported because monthly active-user counts lack historical actor attribution.
2. **Backup Product Admins by Workspace:**
   - **Difference Observed:** The raw-CSV pass identified active product admins from `crossbeam_users.csv` when CRM contacts bounced, were duplicated, or were missing—such as **Femi Adeyemi** at Sable Insurance (where Dana Okafor's emails bounced), **Jules Lund** at Brightpath Learning, **Harper Benn** on Quillon Health's `ORG-1031` workspace, and **Noor Garza** at Arbor Civic.
   - **Improvement Made:** Surfacing eligible product admins per workspace (with workspace ID, verification status, and activity recency) in `customer_360.json`, while instructing `SKILL.md` that product admin access proves product usage—not renewal decision-making authority—and that possible duplicate CRM contacts (such as Arbor's `CON-1401` and `CON-1402`) must be verified rather than counted as separate outreach coverage.
3. **Usage Drops/Halts, Disconnected Data Sources & Activity Provenance:**
   - **Difference Observed:** A broken `no_logins_last_45_days` flag was misleading, sudden activity drops/halts needed explicit monthly trend context, unconnected data sources with active partners explained "0 overlaps" complaints (Gantry Cloud and Pinecrest Dental), and unlinked/alias records needed transparent provenance.
   - **Improvement Made:** Added structured `october_usage_drop` / `october_usage_halt` signals (based on monthly counts and `usage_trend_pct`, leaving null when unknown rather than guessing), `data_source_disconnected_with_partners` alongside `partners_connected` and `partners_with_overlaps`, `total_billing_arr` in `monday_summary.json`, and `match_basis` / `original_crm_account_id` / bounce flags on `recent_activities`. All `13` snapshot tests in `tests/test_snapshot.py` pass after regenerating `./output` for `2026-11-16`.

---

## 4. Uncaught Easter Eggs (Watch-Outs) & Next Steps (`v2`)

Even with deterministic enrichment in place, a few cross-table easter eggs and ambiguities warrant explicit operational care or future pipeline work:

- **Corvid Retail Group (`ACC-006`) vs. Duplicate Prospect `ACC-008` & Corvid Outdoor (`ORG-1007`):** BD cold-outreach activity (`ACT-0011`–`ACT-0013`) hit existing customer contacts (Carmen Velasco and Ian Whitlock) via duplicate prospect record `ACC-008`, alongside an `october_usage_halt` signal and potential expansion interest toward separate customer **Corvid Outdoor LLC** (`ORG-1007`). Requires BD suppression, RevOps deduplication/hygiene check, and AM follow-up.
- **Fenwick Labs Onboarding Stall:** Contracted for `2026-10-01` (8 seats) with no linked workspace, usage data, or logged kickoff by `2026-11-16`.
- **Unresolved Domain Alias & Duplicate CRM Records:** Older `@tessellate.example` correspondence for **Tessel Inc.** requires a verified alias or CRM link before attribution to Tessel, and **Arbor Civic** duplicate contacts (`CON-1401` / `CON-1402`) still require CRM cleanup confirmation.
- **Next Steps (`v2`):**
  1. Add automated pipeline checks/flags for BD prospect-to-customer email/account collisions (`ACC-008` vs. active customer accounts) and stalled post-start onboarding (such as Fenwick Labs).
  2. Maintain a verified company-domain alias mapping table (e.g., `tessellate.example` -> `tessel.example`) so historical correspondence can be linked with explicit provenance.
  3. Add actor-level login/activity timestamps in upstream product data so sudden login halts can distinguish true usage stops from reporting lags.
