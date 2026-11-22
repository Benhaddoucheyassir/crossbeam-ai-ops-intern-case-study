# AI Ops Intern Case: Sam's Monday Question

Reconcile messy Billing, CRM, Product workspace/user, and Activity data into a deterministic, auditable dataset and Claude skill so Account Manager **Sam Ortega** knows which accounts need attention this week, why, and what to do first.

## What We Built

- **Deterministic SQL / DuckDB Pipeline (`src/run_pipeline.py`, `src/sql/01–05`):** Enforces a `Billing > CRM > Product/Activity` trust hierarchy across `17` active billing subscriptions (`$492,099.96` exact billing ARR, `~$492,000` rounded to the nearest thousand as of `2026-11-16`), resolves primary vs. shadow/unverified workspaces, separates internal support seats (`@crossbeam.example` / `"Crossbeam Support"`), surfaces eligible active product admins as backup contacts, flags usage drops/halts and disconnected data sources with active partners, and attaches `recent_activities` with match provenance.
- **Monday Assistant Skill & Sample Output (`claude_skill/SKILL.md`, `output/assistant_sample_response.md`):** Grounds Sam's weekly briefing strictly in pre-computed JSON (`output/customer_360.json`, `output/monday_summary.json`) and activity records while separating verified facts from unknowns or unverified claims.
- **Verification & Documentation (`tests/test_snapshot.py`, `docs/RULES.md`, `docs/ARCHITECTURE.md`, `docs/DECISION_LOG.md`):** `13` passing pytest snapshot tests plus documentation of business rules, architecture, trade-offs, and raw-CSV comparisons.

## How to Run It

1. **Install dependencies (Python 3.11+):** `pip install duckdb pandas pytest`
2. **Run the pipeline for a snapshot:** `python src/run_pipeline.py --data-dir ./data --snapshot-date 2026-11-16 --output-dir ./output`
3. **Run the test suite:** `python -m pytest -v`
4. **Use the Monday Assistant:** Load `claude_skill/SKILL.md` into Claude and attach `output/customer_360.json` and `output/monday_summary.json` (see `output/assistant_sample_response.md` for a sample `2026-11-16` briefing).

## Core Rules & Guardrails

- **Billing > CRM > Product/Activity:** Active subscriptions in `billing_subscriptions.csv` anchor the customer universe, ARR, seat counts, and `current_period_end` renewal windows; CRM and workspace/activity records enrich context and flag mismatches (such as Halcyon Travel's `30` billing seats vs. `50` CRM seats).
- **Priority Tiers:** `CRITICAL` for imminent renewals with low utilization or sharp usage drops (greater than 20% decline); `HIGH (Renewal + Seat Mismatch)` for renewals within 30 days with Billing vs. CRM discrepancies; `HIGH (Expansion)` when seat demand exceeds purchased seats; `HIGH (Contact Hygiene)` when active contacts are fewer than two.
- **Hygiene & Honest Uncertainty:** Exclude departed or bounced addresses from outreach recommendations, treat possible duplicate CRM records as cleanup checks, isolate internal support seats from customer expansion demand, surface active product admins without conflating product usage with renewal authority, and keep unknown or unverified fields explicit rather than guessing.

## Who Else Can Use This & How

- **RevOps:** Use `output/revops_flags.csv` and workspace/billing mismatch signals to reconcile CRM seat/ARR drift (Halcyon Travel), relink workspaces (`Marlowe`, `Tessel`, `Ostrava`), deduplicate CRM contacts/accounts, and audit shadow workspaces (`Quillon ORG-1031`).
- **Business Development (BD):** Check `output/bd_flags.csv` and customer/domain linkages to avoid cold-emailing existing customer contacts (such as Corvid Retail Group via `ACC-008`), protect active expansion motions (`Corvid Outdoor`), and follow up on unlinked PLG workspaces (`Vantor Logistics`).
- **CS / Account Leadership:** Review `output/monday_summary.json` and `output/customer_360.json` for portfolio-level ARR, churn exposure, expansion pipeline, and weekly team capacity.

## What We Would Do Next

- Add automated checks for BD prospect-to-customer outreach collisions and post-contract onboarding stalls (such as Fenwick Labs).
- Introduce a verified company-domain alias mapping table (e.g., `tessellate.example` to `tessel.example`) and actor-level product login timestamps for finer usage-halt attribution.
- Wire the pipeline and `SKILL.md` into scheduled weekly snapshots and Slack/CRM alerts with human-in-the-loop review before external outreach.
