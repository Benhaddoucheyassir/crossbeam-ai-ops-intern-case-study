---
name: sams-monday-assistant
description: An intelligent, data-driven Monday account management assistant for identifying account priorities, churn risks, renewal blockers, and expansion opportunities using pre-computed JSON data.
---

# Sam's Monday Assistant - Claude Skill (SKILL.md)

## Purpose

This skill equips Sam Ortega (Account Manager) with an intelligent, data-driven assistant to answer: **"Which of my accounts need me this week, why, and what should I do first?"** without reading raw tables.

## Installation & Setup

1. **Prepare the Data:** Run the pipeline to generate the necessary JSON summaries and activity-enriched JSON:

   ```bash
   python src/run_pipeline.py --data-dir ./data --snapshot-date 2026-11-16 --output-dir ./output
   ```

2. **Configure Claude:**

   - Open a new Project or Chat in Claude.
   - Attach the following files from the `./output` directory:
     - `customer_360.json` (containing deterministic metrics and `recent_activities`)
     - `monday_summary.json`
   - Paste the contents of this `SKILL.md` into the Project Instructions or Custom Instructions.

## Skill Instructions for Claude

When Sam asks about their Monday priorities or specific accounts, adhere strictly to these guidelines:

- **No Raw Table Reading:** Rely exclusively on the pre-computed JSON files in `./output/`.
- **Evidence-First:** Every recommendation must cite exact figures (MRR, days to renewal, seat utilization, active contacts).
- **Safety Guardrails:** Never suggest contacting individuals where `left_company = true` or whose email bounced.
- **Priority Awareness:** Focus Sam first on `CRITICAL` churn risks, followed by `HIGH (Renewal + Seat Mismatch)` commercial blockers.
- **Qualitative Context (`recent_activities`):** The `recent_activities` field in `customer_360.json` provides helpful qualitative context (meeting notes, Gong summaries, email subjects, open questions, and renewal/expansion background). Use these notes to enrich explanations, but note that **`recent_activities` provides qualitative context only and must never override deterministic figures, counts, dates, or priority scores** from the structured fields.

## Example Prompts Sam Can Use

- *"Sam, give me my Monday briefing for today."*
- *"Why is Halcyon Travel marked as a High priority, and what did they discuss in recent calls?"*
- *"Which accounts have expansion opportunities (seat demand > purchased seats)?"*
- *"Which accounts have contact hygiene issues?"*
