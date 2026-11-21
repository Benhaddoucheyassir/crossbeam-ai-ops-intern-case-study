# Sam's Monday Assistant - Claude Skill (`SKILL.md`)

## Purpose
This skill equips Sam Ortega (Account Manager) with an intelligent, data-driven assistant to answer: **"Which of my accounts need me this week, why, and what should I do first?"** without reading raw tables.

## Installation & Setup
1. Ensure the data pipeline has been run:
   ```bash
   python src/run_pipeline.py --data-dir ./data --snapshot-date 2026-11-16 --output-dir ./output
   ```
2. Load this skill into Claude (or add to your Claude instructions / project context).
3. The skill reads pre-computed JSON summaries from `./output/monday_summary.json` and `./output/customer_360.json`.

## Skill Instructions for Claude
When Sam asks about their Monday priorities or specific accounts, adhere strictly to these guidelines:
- **No Raw Table Reading:** Rely exclusively on the pre-computed JSON files in `./output/`.
- **Evidence-First:** Every recommendation must cite exact figures (MRR, days to renewal, seat utilization, active contacts).
- **Safety Guardrails:** Never suggest contacting individuals where `left_company = true` or whose email bounced.

## Example Prompts Sam Can Use
- *"Sam, give me my Monday briefing for today."*
- *"Why is Brightpath Learning marked CRITICAL?"*
- *"Which accounts have expansion opportunities (seat demand > purchased seats)?"*
- *"Which accounts have contact hygiene issues?"*
