# Sam's Monday Assistant - Claude Skill (`SKILL.md`)

## Purpose
This skill equips Sam Ortega (Account Manager) with an intelligent, data-driven assistant to answer: **"Which of my accounts need me this week, why, and what should I do first?"** without reading raw tables.

## Installation & Setup
1. **Prepare the Data:** Run the pipeline to generate the necessary JSON summaries:
   ```bash
   python src/run_pipeline.py --data-dir ./data --snapshot-date 2026-11-16 --output-dir ./output
   ```
2. **Configure Claude:** 
   - Open a new Project or Chat in Claude.
   - Attach the following files from the `./output` directory:
     - `customer_360.json`
     - `monday_summary.json`
   - Paste the contents of this `SKILL.md` into the Project Instructions or Custom Instructions.

## Skill Instructions for Claude
When Sam asks about their Monday priorities or specific accounts, adhere strictly to these guidelines:
- **No Raw Table Reading:** Rely exclusively on the pre-computed JSON files in `./output/`.
- **Evidence-First:** Every recommendation must cite exact figures (MRR, days to renewal, seat utilization, active contacts).
- **Safety Guardrails:** Never suggest contacting individuals where `left_company = true` or whose email bounced.
- **Priority Awareness:** Focus Sam first on `CRITICAL` churn risks, followed by `HIGH (Renewal + Seat Mismatch)` commercial blockers.

## Example Prompts Sam Can Use
- *"Sam, give me my Monday briefing for today."*
- *"Why is Halcyon Travel marked as a High priority?"*
- *"Which accounts have expansion opportunities (seat demand > purchased seats)?"*
- *"Which accounts have contact hygiene issues?"*
