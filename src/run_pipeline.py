import duckdb
import argparse
import os
import json
import pandas as pd
from datetime import datetime

def run_pipeline(data_dir, snapshot_date, output_dir):
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Initialize DuckDB
    con = duckdb.connect(database=':memory:')

    # List of SQL files to run in order
    sql_files = [
        '01_billing_universe.sql',
        '02_crm_mapping.sql',
        '03_workspace_resolution.sql',
        '04_usage_and_contacts.sql',
        '05_priority_scoring.sql'
    ]

    for sql_file in sql_files:
        path = os.path.join('src', 'sql', sql_file)
        with open(path, 'r') as f:
            sql = f.read()
            # Handle template variables
            sql = sql.replace('{{data_dir}}', data_dir)
            sql = sql.replace('{{snapshot_date}}', snapshot_date)
            con.execute(sql)

    # Fetch final report
    df = con.execute("SELECT * FROM final_report").df()

    # Save outputs
    df.to_csv(os.path.join(output_dir, 'customer_360.csv'), index=False)
    
    # Save JSON version for Claude
    json_data = df.to_json(orient='records', indent=2)
    with open(os.path.join(output_dir, 'customer_360.json'), 'w') as f:
        f.write(json_data)

    # Generate RevOps Flags
    revops_df = df[df['revops_missing_crm_link'] | df['revops_shadow_workspaces'] | df['revops_data_mismatch']]
    revops_df.to_csv(os.path.join(output_dir, 'revops_flags.csv'), index=False)

    # Generate BD Flags
    bd_df = df[df['bd_no_contacts']]
    bd_df.to_csv(os.path.join(output_dir, 'bd_flags.csv'), index=False)

    # Generate Sam's Monday Briefing (NO LIMIT on briefing rows)
    generate_monday_briefing(df, snapshot_date, output_dir)

def generate_monday_briefing(df, snapshot_date, output_dir):
    # Sort by priority and days to renewal
    priority_order = {
        'CRITICAL': 0, 
        'HIGH (Renewal + Seat Mismatch)': 1, 
        'HIGH (Expansion)': 2, 
        'HIGH (Contact Hygiene)': 3, 
        'MEDIUM': 4, 
        'LOW': 5
    }
    df['priority_rank'] = df['priority_score'].map(priority_order)
    df = df.sort_values(by=['priority_rank', 'days_to_renewal'])

    briefing = f"# Sam's Monday Briefing - {snapshot_date}\n\n"
    briefing += "## All Priority Accounts Requiring Attention\n\n"

    for _, row in df.iterrows():
        if row['priority_score'] == 'LOW':
            continue
            
        briefing += f"### {row['billing_customer_name']} ({row['priority_score']})\n"
        briefing += f"- **Why:** "
        if row['priority_score'] == 'CRITICAL':
            briefing += f"Renewal in {row['days_to_renewal']} days with critical usage gap ({int(row['seat_utilization']*100)}% utilization)."
        elif row['priority_score'] == 'HIGH (Renewal + Seat Mismatch)':
            briefing += f"Imminent renewal in {row['days_to_renewal']} days (due {row['current_period_end']}) with Billing vs. CRM data mismatch (Billing: {row['billing_seats']} seats / ${row['billing_mrr']} MRR vs. CRM: {row['crm_seats']} seats / ${row['crm_arr']} ARR)."
        elif 'Expansion' in row['priority_score']:
            briefing += f"High seat demand ({row['total_demand']}) exceeding purchased seats ({row['billing_seats']})."
        elif 'Contact Hygiene' in row['priority_score']:
            briefing += f"Missing active contacts ({row['active_contacts_count']} found). Risk of losing thread with customer."
        elif row['priority_score'] == 'MEDIUM':
            briefing += f"Usage trend is declining ({int(row['usage_trend_pct']*100)}% month-over-month)."
        
        briefing += f"\n- **What to do:** "
        if row['priority_score'] == 'CRITICAL':
            briefing += "Schedule an executive review immediately to demonstrate value before the renewal deadline."
        elif row['priority_score'] == 'HIGH (Renewal + Seat Mismatch)':
            briefing += "Coordinate with RevOps to reconcile CRM quota/seat counts before issuing renewal paperwork."
        elif 'Expansion' in row['priority_score']:
            briefing += "Reach out to discuss increasing seat count for the new users."
        elif 'Contact Hygiene' in row['priority_score']:
            briefing += "Use LinkedIn or team intros to find two new primary contacts."
        else:
            briefing += "Check in with the primary contact to understand the usage drop."
        
        briefing += f"\n- **Details:** MRR: ${row['billing_mrr']}, Seats: {row['billing_seats']}, Primary Org: {row['primary_org_id']}\n\n"

    with open(os.path.join(output_dir, 'monday_briefing.md'), 'w') as f:
        f.write(briefing)

    # Save summary for Sam's Claude skill (listing ALL active priority accounts, no limit)
    summary = {
        "snapshot_date": snapshot_date,
        "total_active_customers": len(df),
        "critical_alerts": len(df[df['priority_score'] == 'CRITICAL']),
        "renewal_seat_mismatch_alerts": len(df[df['priority_score'] == 'HIGH (Renewal + Seat Mismatch)']),
        "expansion_opportunities": len(df[df['priority_score'].str.contains('Expansion')]),
        "priority_accounts": df[df['priority_score'] != 'LOW'][['billing_customer_name', 'priority_score', 'days_to_renewal', 'billing_mrr']].to_dict(orient='records')
    }
    with open(os.path.join(output_dir, 'monday_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--snapshot-date', default='2026-11-16')
    parser.add_argument('--output-dir', default='./output')
    args = parser.parse_args()

    run_pipeline(args.data_dir, args.snapshot_date, args.output_dir)
