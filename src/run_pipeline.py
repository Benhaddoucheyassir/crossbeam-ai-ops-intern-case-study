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
        '05_priority_scoring.sql',
        '06_action_evidence.sql'
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
    df = con.execute("""
        SELECT * FROM final_report ORDER BY (crm_account_id IS NULL), billing_customer_id
    """).df()
    if df['billing_customer_id'].isna().any() or not df['billing_customer_id'].is_unique:
        raise ValueError("Active billing customer IDs must be present and unique.")
    enrichment = {
        customer_id: json.loads(context)
        for customer_id, context in con.execute("SELECT * FROM customer_enrichment").fetchall()
    }
    action_evidence = {
        customer_id: json.loads(context)
        for customer_id, context in con.execute("SELECT * FROM customer_action_evidence").fetchall()
    }
    unrouted_workspaces = [
        json.loads(context)
        for (context,) in con.execute("SELECT * FROM workspace_routing_evidence").fetchall()
    ]

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

        rec.update(enrichment[rec['billing_customer_id']])
        rec.update(action_evidence[rec['billing_customer_id']])
        acc_id = rec.get('crm_account_id')
        billing_dom = str(rec.get('billing_domain', '')).strip().lower()
        
        account_acts = []
        if not act_df.empty:
            for _, act in act_df.iterrows():
                activity_date = act.get('activity_date')
                if pd.isna(activity_date) or activity_date > snapshot_date:
                    continue
                act_acc_id = act.get('account_id')
                act_email = str(act.get('contact_email', '')).strip().lower()
                act_domain = act_email.split('@')[-1] if '@' in act_email else ''
                
                if acc_id and pd.notna(act_acc_id) and str(act_acc_id).strip() == acc_id:
                    match_basis = 'crm_account_id'
                elif billing_dom and act_domain == billing_dom:
                    match_basis = 'billing_domain'
                else:
                    continue

                def activity_value(field):
                    value = act.get(field)
                    return None if pd.isna(value) else str(value)

                account_acts.append({
                    "activity_id": activity_value('activity_id'),
                    "activity_date": activity_date,
                    "channel": activity_value('source'),
                    "activity_type": activity_value('direction'),
                    "subject": activity_value('subject'),
                    "summary": activity_value('summary'),
                    "contact_email": activity_value('contact_email'),
                    "owner_name": activity_value('logged_by'),
                    "crm_account_id": activity_value('account_id'),
                    "match_basis": match_basis,
                    "bounced": None if pd.isna(act.get('bounced')) else str(act['bounced']).lower() == 'true',
                })
        
        # Sort by activity_date desc, activity_id desc and keep top 5
        account_acts.sort(key=lambda x: (x['activity_date'], x['activity_id'] or ''), reverse=True)
        rec['recent_activities'] = account_acts[:5]
        rec['action_signals'] = build_action_signals(rec)
        json_records.append(rec)

    # Save JSON version for Claude with recent_activities attached
    with open(os.path.join(output_dir, 'customer_360.json'), 'w') as f:
        json.dump(json_records, f, indent=2)

    # Generate Sam's Monday Briefing
    generate_monday_briefing(df, snapshot_date, output_dir, json_records, unrouted_workspaces)


def build_action_signals(record):
    signals = []

    def add(code, owner, next_step, source_ids=(), same_day=False):
        signals.append({
            'code': code, 'owner': owner, 'next_step': next_step, 'same_day': same_day,
            'source_ids': list(dict.fromkeys(source_id for source_id in source_ids if source_id)),
        })

    status = record['crm_workspace_link_status']
    crm_id = record['crm_account_id']
    org_id = record['primary_org_id']
    if status == 'unknown_crm_link':
        add('review_crm_link', 'RevOps', 'Verify the billing-to-CRM link and account ownership.',
            [crm_id, *(c['crm_account_id'] for c in record['crm_link_candidates'])])
    elif status != 'matches_primary':
        add('review_workspace_link', 'RevOps', 'Verify the CRM pointer against the workspace evidence before relinking.',
            [crm_id, record['crm_product_org_id'], org_id])
    if record['revops_shadow_workspaces']:
        add('review_shadow_workspaces', 'RevOps', 'Validate workspace ownership and verification.',
            [crm_id, *(org['org_id'] for org in record['related_workspaces'] if not org['is_primary_workspace'])])
    if record['revops_data_mismatch']:
        imminent = 0 <= record['days_to_renewal'] <= 30
        add('reconcile_commercial_mismatch', 'RevOps', 'Reconcile CRM and renewal quote values against billing.',
            [crm_id], same_day=imminent)
    if record['onboarding_workspace_missing']:
        add('verify_onboarding', 'Sam / CS', 'Verify provisioning and kickoff status with an eligible CRM contact.', [crm_id])
    if (record['login_evidence'] or {}).get('recent_login_gap'):
        add('verify_recent_login_gap', 'Sam / CS', 'Validate the last-login gap with the customer and product telemetry.', [org_id])
    if record['data_source_disconnected_with_partners']:
        add('verify_data_source', 'Sam / CS', 'Verify the intended source and its connection state.', [org_id])
    if record['active_billing_children']:
        add('review_paid_subsidiary', 'Sam', 'Confirm whether the planned rollout affects the subsidiary’s own subscription.',
            [child['billing_customer_id'] for child in record['active_billing_children']])

    contacts = record['crm_contact_hygiene']
    eligible = [c for c in contacts if c['left_company'] is False and not c['email_bounced'] and c['email']]
    distinct_emails = {c['email'].strip().lower() for c in eligible if c['email'].strip()}
    record['eligible_crm_email_count'] = None if record['revops_missing_crm_link'] else len(distinct_emails)
    if record['eligible_crm_email_count'] is not None and len(distinct_emails) < 2:
        add('add_contact_coverage', 'Sam', 'Identify eligible contacts or request an introduction from a product admin.',
            [c['contact_id'] for c in contacts])
    eligible_ids = {c['contact_id'] for c in eligible}
    possible_duplicates = [
        c['contact_id'] for c in eligible if eligible_ids.intersection(c['possible_duplicate_contact_ids'])
    ]
    if possible_duplicates:
        add('review_contact_aliases', 'RevOps', 'Verify whether the contact records represent distinct people.',
            possible_duplicates)
    if record['cross_workspace_identity_candidates']:
        add('verify_cross_workspace_identity', 'RevOps', 'Review the identity clue without assuming a departure or job move.',
            [user_id for candidate in record['cross_workspace_identity_candidates']
             for user_id in (candidate['current_user_id'], candidate['other_user_id'])])

    collisions = record['prospect_contact_collisions']
    if collisions:
        removal_ids = [activity_id for c in collisions for activity_id in c['removal_request_activity_ids']]
        collision_ids = [source_id for c in collisions for source_id in (
            c['prospect_account_id'], c['prospect_contact_id'], c['customer_contact_id'], *c['outbound_activity_ids']
        )]
        add('suppress_prospect_outreach', 'BD', 'Suppress prospect outreach to these existing customer addresses.',
            [*collision_ids, *removal_ids], same_day=bool(removal_ids))
        add('review_prospect_collision', 'RevOps', 'Review the overlapping customer and prospect records.',
            [crm_id, *collision_ids])
        if removal_ids:
            add('acknowledge_removal_request', 'Sam', 'Acknowledge the customer’s recorded removal request.',
                removal_ids, same_day=True)
    return signals


def generate_monday_briefing(df, snapshot_date, output_dir, records, unrouted_workspaces):
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
    df = df.sort_values(by=['priority_rank', 'days_to_renewal', 'billing_customer_id'])

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
        "total_billing_arr": round(float(df['billing_arr'].sum()), 2),
        "critical_alerts": len(df[df['priority_score'] == 'CRITICAL']),
        "renewal_seat_mismatch_alerts": len(df[df['priority_score'] == 'HIGH (Renewal + Seat Mismatch)']),
        "expansion_opportunities": len(df[df['priority_score'].str.contains('Expansion')]),
        "priority_accounts": df[df['priority_score'] != 'LOW'][['billing_customer_name', 'priority_score', 'days_to_renewal', 'billing_mrr']].to_dict(orient='records'),
        "monthly_usage_periods": ["2026-08", "2026-09", "2026-10"],
        "action_queue": sorted(
            [
                {"billing_customer_id": record['billing_customer_id'], **signal}
                for record in records for signal in record['action_signals']
            ],
            key=lambda signal: (not signal['same_day'], signal['billing_customer_id'], signal['code']),
        ),
        "workspaces_outside_active_book": [
            {
                **workspace,
                "routing": (
                    "bd_qualification_candidate"
                    if workspace['verification_status'] == 'verified' and not workspace['is_dormant']
                    and workspace['plan_tier'] == 'free'
                    and (workspace['active_users_2026_10'] or 0) > 0
                    and not workspace['crm_account_ids'] and not workspace['billing_subscriptions']
                    else "outside_active_book"
                ),
            }
            for workspace in unrouted_workspaces
        ],
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
