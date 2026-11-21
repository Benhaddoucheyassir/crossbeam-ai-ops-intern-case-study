# ARCHITECTURE.md: Pipeline & Assistant Architecture

## Overview
The Crossbeam AI Ops pipeline bridges Billing, CRM, and Product usage data into an actionable, warehouse-ready DuckDB model. It empowers Account Manager Sam Ortega with a prioritized Monday briefing while surfacing diagnostic flags for RevOps and Business Development.

## Data Flow Diagram

```
[billing_subscriptions.csv] (SSOT: Active Customers, ARR, Seats)
          │
          ▼
   [01_billing_universe.sql]
          │
          ▼ (Left Join)
   [crm_accounts.csv] ──► [02_crm_mapping.sql] (Metadata & Gaps)
          │
          ▼
   [crossbeam_workspaces.csv] ──► [03_workspace_resolution.sql] (Primary Org & Shadow Detection)
          │
          ▼
   [crossbeam_users.csv] & [activity.csv] ──► [04_usage_and_contacts.sql] (Seat Demand & Contact Hygiene)
          │
          ▼
   [05_priority_scoring.sql] ──► Deterministic Priority & Diagnostic Flags
          │
          ├─────────────────────────┬──────────────────────────┐
          ▼                         ▼                          ▼
   [customer_360.csv/json]   [revops_flags.csv]         [bd_flags.csv]
          │                                                    │
          └─────────────────────────┬──────────────────────────┘
                                    ▼
                         [monday_briefing.md & json]
                                    │
                                    ▼
                         [Claude Skill Integration]
```

## Component Breakdown

1. **SQL Transformation Layer (`src/sql/`)**:
   - Modular, declarative DuckDB SQL files executed sequentially.
   - Designed to mirror Snowflake analytical patterns for seamless future migration.

2. **Python Orchestrator (`src/run_pipeline.py`)**:
   - Parameterized CLI accepting `--data-dir`, `--snapshot-date`, and `--output-dir`.
   - Automates DuckDB execution, compiles structured JSON/CSV outputs, and generates Sam's Monday briefing in Markdown.

3. **Testing Framework (`tests/test_snapshot.py`)**:
   - Automated `pytest` assertions verifying critical edge cases (e.g., Tessel's orphan billing, Marlowe Analytics workspace selection, Quillon Health shadow orgs, Sable Insurance contact hygiene).

4. **Claude Skill (`claude_skill/SKILL.md`)**:
   - Consumes `output/customer_360.json` and `output/monday_summary.json` to allow Sam to query specific accounts interactively without reading raw tables.
