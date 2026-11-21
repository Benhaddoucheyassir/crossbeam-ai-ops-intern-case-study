# Sam's Monday Question: Prompts & Evidence

This file records the prompts used to generate Sam's Monday assistant and the types of evidence it provides.

## Data Cleaning & Transformation Prompts
*"Build a DuckDB-powered pipeline that reconciles Billing as the source of truth for customers, then joins CRM and Product data. Filter out 'canceled' billing records and prioritize 'verified' workspaces for each domain. Flag any data mismatches between Billing (seats/ARR) and CRM."*

## Priority Scoring Prompts
*"Define CRITICAL as accounts with a renewal within 90 days and low usage (<25% seat utilization or -20% trend). Define HIGH (Renewal + Seat Mismatch) as accounts with a renewal within 30 days where Billing and CRM seat counts do not match. Surface expansion opportunities and contact hygiene issues as separate HIGH flags."*

## Briefing Generation Prompts
*"Generate a Markdown briefing for Sam Ortega that lists ALL priority accounts. Order them by severity: CRITICAL first, then Renewal Mismatches, then Expansion, then Contact Hygiene. For each account, provide a 'Why' (citing exact data points) and a 'What to do' (actionable next step)."*

## Representative Evidence Citations
- **Brightpath Learning:** "Renewal in 34 days with critical usage gap (13% utilization)."
- **Halcyon Travel:** "Imminent renewal in 14 days (due 2026-11-30) with Billing vs. CRM data mismatch (Billing: 30 seats / $2000.0 MRR vs. CRM: 50 seats / $40000.0 ARR)."
- **Halvorsen Freight:** "High seat demand (25) exceeding purchased seats (20)."
- **Sable Insurance:** "Missing active contacts (0 found). Risk of losing thread with customer."
