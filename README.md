# AI Ops Intern Case: Sam's Monday Question

Reconcile messy Billing, CRM, Product workspace/user, and Activity data into a deterministic, auditable dataset and Claude skill so Account Manager **Sam Ortega** knows which accounts need attention this week, why, and what to do first.

## What We Built

- **Deterministic SQL / DuckDB Pipeline (`src/run_pipeline.py`, `src/sql/01–06`):** Applies `Billing > CRM > Product/Activity` across 17 active subscriptions and $492,099.96 exact billing ARR on 2026-11-16. JSON includes adjusted seat demand, backup admins, usage and connection signals, activity provenance, and evidence-backed handoffs. The CSV exports retain their legacy schemas.
- **Monday Assistant Skill & Sample Output (`claude_skill/SKILL.md`, `output/assistant_sample_response.md`):** Grounds Sam's weekly briefing strictly in pre-computed JSON (`output/customer_360.json`, `output/monday_summary.json`) and activity records while separating verified facts from unknowns or unverified claims.
- **Verification & Documentation:** `tests/test_snapshot.py` covers the billing baseline, edge cases, and reproducible outputs. See `docs/RULES.md`, `docs/ARCHITECTURE.md`, and `docs/DECISION_LOG.md` for rules, validation questions, and trade-offs.

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

- **RevOps:** Review the JSON action queue for billing mismatches, stale or missing workspace links, candidate CRM aliases, and duplicate-contact evidence before changing records.
- **Business Development (BD):** Use the JSON action queue to suppress prospect outreach collisions such as Corvid’s `ACC-008`. The summary also identifies verified free workspaces such as Vantor for qualification.
- **CS / Account Leadership:** Review `output/monday_summary.json` and `output/customer_360.json` for portfolio-level ARR, churn exposure, expansion pipeline, and weekly team capacity.

## What We Would Do Next

- Store confirmed CRM aliases in a reviewed mapping and ingest product login events for finer usage-gap investigation.
- Wire the pipeline and `SKILL.md` into scheduled weekly snapshots and Slack/CRM alerts with human-in-the-loop review before external outreach.

**AI prompt summary.** AI was asked to build the SQL-backed Monday briefing, compare skill and raw-CSV answers against the case brief, then implement approved evidence and handoff changes while preserving the billing totals and existing tests.
