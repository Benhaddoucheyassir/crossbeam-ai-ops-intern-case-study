-- 04_usage_and_contacts.sql
-- Calculate seat demand, usage trends, and contact health
CREATE OR REPLACE TABLE user_demand AS
SELECT 
    org_id,
    COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepted_seats,
    COUNT(CASE WHEN status = 'pending_invite' THEN 1 END) as pending_invites,
    COUNT(CASE WHEN status = 'seat_request' THEN 1 END) as seat_requests,
    COUNT(*) as total_demand
FROM read_csv_auto('{{data_dir}}/crossbeam_users.csv')
GROUP BY org_id;

CREATE OR REPLACE TABLE bounced_emails AS
SELECT DISTINCT contact_email
FROM read_csv_auto('{{data_dir}}/activity.csv')
WHERE bounced = true;

CREATE OR REPLACE TABLE contact_health AS
SELECT 
    account_id,
    COUNT(CASE WHEN left_company = false AND b.contact_email IS NULL THEN 1 END) as active_contacts_count
FROM read_csv_auto('{{data_dir}}/crm_contacts.csv') c
LEFT JOIN bounced_emails b ON c.email = b.contact_email
GROUP BY account_id;

CREATE OR REPLACE TABLE customer_360 AS
SELECT 
    rc.*,
    ud.accepted_seats,
    ud.pending_invites,
    ud.seat_requests,
    COALESCE(ud.total_demand, 0) as total_demand,
    ch.active_contacts_count,
    -- Renewal calculation based on current_period_end
    DATE_DIFF('day', CAST('{{snapshot_date}}' AS DATE), rc.current_period_end) as days_to_renewal,
    -- Usage trend: Oct vs Sep
    CASE 
        WHEN active_users_2026_09 > 0 THEN (CAST(active_users_2026_10 AS FLOAT) - active_users_2026_09) / active_users_2026_09
        ELSE NULL 
    END as usage_trend_pct,
    -- Seat coverage: MAU Oct / Billing Seats
    CASE 
        WHEN billing_seats > 0 THEN CAST(active_users_2026_10 AS FLOAT) / billing_seats
        ELSE 0 
    END as seat_utilization
FROM resolved_customers rc
LEFT JOIN user_demand ud ON rc.primary_org_id = ud.org_id
LEFT JOIN contact_health ch ON rc.crm_account_id = ch.account_id;
