# AI Ops Intern Case: Sam's Monday Question

Reconcile messy CRM, Billing, and Product data to help an Account Manager (Sam Ortega) prioritize their week.

## Quick Start

### 1. Install Dependencies
Ensure you have Python 3.11+ installed, then run:
```bash
pip install duckdb pandas pytest
```

### 2. Run the Pipeline
Execute the data transformation and generate Sam's briefing for the current snapshot:
```bash
python src/run_pipeline.py --data-dir ./data --snapshot-date 2026-11-16 --output-dir ./output
```

### 3. Review Outputs
- **Sam's Briefing:** `output/monday_briefing.md`
- **RevOps Flags:** `output/revops_flags.csv`
- **Customer 360:** `output/customer_360.csv`

### 4. Run Tests
Verify the pipeline logic against key edge cases:
```bash
python -m pytest -v
```

## Documentation
- [RULES.md](docs/RULES.md): Data transformation and priority scoring logic.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): System design and test question mapping.
- [DECISION_LOG.md](docs/DECISION_LOG.md): Architectural trade-offs and corrections.
- [PROMPTS.md](docs/PROMPTS.md): LLM prompts and evidence citations.
- [SKILL.md](claude_skill/SKILL.md): Sam's Claude Assistant installation and usage.

## Core Priority Logic
- **CRITICAL**: Churn risk (Imminent renewal + Low usage).
- **HIGH (Renewal + Seat Mismatch)**: Commercial blocker (Renewal < 30 days + Data discrepancy).
- **HIGH (Expansion)**: Growth opportunity (Demand > Purchased Seats).
- **HIGH (Contact Hygiene)**: Relationship risk (< 2 active contacts).
