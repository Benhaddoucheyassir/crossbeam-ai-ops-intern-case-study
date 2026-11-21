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

    # Save CSV version (strictly preserved schema)
    df.to_csv(os.path.join(output_dir, 'customer_360.csv'), index=False)

    # Generate RevOps Flags
    revops_df = df[df['revops_missing_crm_link'] | df['revops_shadow_workspaces'] | df['revops_data_mismatch']]
    revops_df.to_csv(os.path.join(output_dir, 'revops_flags.csv'), index=False)

    # Generate BD Flags
    bd_df = df[df['bd_no_contacts']]
    bd_df.to_csv(os.path.join(output_dir, 'bd_flags.csv'), index=False)

    # Load activities for JSON enhancement
    act_df = pd.DataFrame()
    activity_path = os.path.join(data_dir, 'activity.csv')
    if os.path.exists(activity_path):
        act_df = pd.read_csv(activity_path)

    json_records = []
    for _, row in df.iterrows():
        rec = {}
        for k, v in row.to_dict().items():
            if pd.isna(v):
                rec[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                rec[k] = str(v.date() if hasattr(v, 'date') else v)
            elif hasattr(v, 'tolist'): # handle numpy arrays/lists if any
                rec[k] = v.tolist()
            else:
                rec[k] = v

        acc_id = rec.get('crm_account_id')
        billing_dom = str(rec.get('billing_domain', '')).strip().lower()
        
        account_acts = []
        if not act_df.empty:
            for _, act in act_df.iterrows():
                act_acc_id = act.get('account_id')
                act_email = str(act.get('contact_email', '')).strip().lower()
                act_domain = act_email.split('@')[-1] if '@' in act_email else ''
                
                matched = False
                if pd.notna(acc_id) and str(acc_id).strip() != '' and pd.notna(act_acc_id) and str(act_acc_id).strip() == str(acc_id).strip():
                    matched = True
                elif billing_dom and act_domain and act_domain == billing_dom:
                    matched = True
                
                if matched:
                    account_acts.append({
                        "activity_id": str(act.get('activity_id', '')),
                        "activity_date": str(act.get('activity_date', '')),
                        "channel": str(act.get('source', '')),
                        "activity_type": str(act.get('direction', '')),
                        "subject": str(act.get('subject', '')),
                        "summary": str(act.get('summary', '')),
                        "contact_email": str(act.get('contact_email', '')),
                        "owner_name": str(act.get('logged_by', ''))
                    })
        
        # Sort by activity_date desc, activity_id desc and keep top 5
        account_acts.sort(key=lambda x: (x['activity_date'], x['activity_id']), reverse=True)
        rec['recent_activities'] = account_acts[:5]
        json_records.append(rec)

    # Save JSON version for Claude with recent_activities attached
    with open(os.path.join(output_dir, 'customer_360.json'), 'w') as f:
        json.dump(json_records, f, indent=2)

    # Generate Sam's Monday Briefing
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

    # Save summary for Sam's Claude skill
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
