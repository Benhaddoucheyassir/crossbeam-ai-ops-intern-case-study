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
   - Automated `pytest` assertions verifying critical edge cases.

## Test Questions & Expected Answers (Validation Suite)

| Question / Case | Expected Outcome | Rationale |
| :--- | :--- | :--- |
| **How is Tessel handled?** | Present in Customer 360, `revops_missing_crm_link = true`. | Tessel has an active subscription but no linked CRM ID. We preserve the revenue record. |
| **Which org is used for Marlowe?** | `ORG-1041` (Verified). | `ORG-1004` is failed/dormant. The pipeline must select the verified, active workspace. |
| **Why is Brightpath CRITICAL?** | Renewal <= 90 days AND 13% seat utilization. | Classic churn risk: imminent renewal with low product adoption. |
| **What about Halcyon Travel?** | `HIGH (Renewal + Seat Mismatch)`. | Renewal in 14 days with 30 vs 50 seat discrepancy between systems. |
| **Should BD contact Corvid through ACC-008, and did October usage halt?** | Suppress the prospect sequence and acknowledge ACT-0012. October monthly usage was flat. The latest recorded customer login was 23 days before the snapshot. | Exact-email matches and recorded activity support the handoff. The later login gap needs investigation before assigning a cause. |

4. **Claude Skill (`claude_skill/SKILL.md`)**:
   - Consumes `output/customer_360.json` and `output/monday_summary.json`. The JSON adds evidence and handoffs from `06_action_evidence.sql` and the Python routing rules. Use the five questions above for the assistant check after attaching the generated JSON. Verify that it also keeps unsupported departures, account merges, and login-gap causes out of its recommendations.
