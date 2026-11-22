# Pipeline and assistant architecture

## Overview

The Crossbeam AI Ops pipeline uses DuckDB to produce one customer record per active billing subscription. Billing anchors the portfolio, purchased seats, recurring revenue, and renewal dates. CRM, product, and activity data supply relationship and usage evidence. Sam Ortega uses the resulting snapshot for Monday planning, with specific follow-up routed to Sam, CS, RevOps, or Business Development.

## Data flow

```text
Billing subscriptions ─────────► 01  Define the active billing portfolio
                                     │
CRM accounts ──────────────────► 02  Attach CRM metadata
                                     │
Product workspaces ────────────► 03  Resolve primary and shadow workspaces
                                     │
Product users, CRM contacts,
and activity ──────────────────► 04  Calculate usage, seat demand, and contact health
                                     │
                                 05  Assign priority tiers and diagnostic flags
                                     │
                                     ├──► Customer 360, RevOps, and BD CSVs
                                     │
                                 06  Add cross-table evidence
                                     │
                                     ▼
                              Python routing and export
                                     │
                                     ├──► monday_briefing.md
                                     │
                                     └──► customer_360.json + monday_summary.json
                                                       │
                                                       ▼
                                                  Claude skill
```

## Components

- **SQL transformations (`src/sql/01–05`).** Build the billing-led customer record, resolve the primary workspace, calculate usage and contact metrics, and apply deterministic priority rules.
- **Action evidence (`src/sql/06_action_evidence.sql`).** Adds cross-table evidence for workspace and CRM link reviews, contact collisions, onboarding checks, and recent login gaps. Candidate links and identities remain separate from confirmed records. Login recency is reported separately from monthly active users.
- **Python orchestration and routing (`src/run_pipeline.py`).** Runs the SQL using the input directory and snapshot date, joins activity context with match provenance, and assigns evidence-backed actions to the appropriate owner. Writes the CSV exports, the Markdown briefing, and the JSON evidence and action queue.
- **Claude skill (`claude_skill/SKILL.md`).** Uses `customer_360.json` and `monday_summary.json` to explain priorities and recommend next steps. Structured fields determine figures, dates, and tiers. Activity notes supply attributed context, and unresolved links, identities, and causes remain open for verification.
- **Snapshot tests (`tests/test_snapshot.py`).** Verify billing totals, key joins, action evidence, and repeatable output.
