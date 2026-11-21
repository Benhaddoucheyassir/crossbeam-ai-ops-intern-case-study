-- 04_usage_and_contacts.sql
-- Calculate seat demand, usage trends, and contact health
CREATE OR REPLACE TABLE product_users AS
SELECT *,
    COALESCE(ends_with(lower(trim(email)), '@crossbeam.example'), false)
        OR COALESCE(lower(trim(full_name)) = 'crossbeam support', false) AS is_internal_support
FROM read_csv_auto('{{data_dir}}/crossbeam_users.csv');

CREATE OR REPLACE TABLE user_demand AS
SELECT 
    org_id,
    COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepted_seats,
    COUNT(CASE WHEN status = 'pending_invite' THEN 1 END) as pending_invites,
    COUNT(CASE WHEN status = 'seat_request' THEN 1 END) as seat_requests,
    COUNT(*) as total_demand,
    COUNT(*) FILTER (WHERE is_internal_support) AS internal_support_demand,
    COUNT(*) FILTER (WHERE status = 'accepted' AND NOT is_internal_support) AS customer_accepted_seats,
    COUNT(*) FILTER (WHERE NOT is_internal_support) AS customer_total_demand
FROM product_users
GROUP BY org_id;

CREATE OR REPLACE TABLE bounced_emails AS
SELECT DISTINCT lower(trim(contact_email)) AS contact_email
FROM read_csv_auto('{{data_dir}}/activity.csv')
WHERE bounced = true AND activity_date <= CAST('{{snapshot_date}}' AS DATE);

CREATE OR REPLACE TABLE crm_contact_details AS
SELECT c.*, lower(trim(c.email)) AS normalized_email,
    b.contact_email IS NOT NULL AS email_bounced
FROM read_csv_auto('{{data_dir}}/crm_contacts.csv') c
LEFT JOIN bounced_emails b ON lower(trim(c.email)) = b.contact_email;

CREATE OR REPLACE TABLE contact_health AS
SELECT 
    account_id,
    COUNT(CASE WHEN left_company = false AND NOT email_bounced THEN 1 END) as active_contacts_count
FROM crm_contact_details
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

CREATE OR REPLACE VIEW customer_enrichment AS
SELECT rc.billing_customer_id,
    to_json(struct_pack(
        internal_support_demand := COALESCE(ud.internal_support_demand, 0),
        customer_accepted_seats := COALESCE(ud.customer_accepted_seats, 0),
        customer_total_demand := COALESCE(ud.customer_total_demand, 0),
        customer_accepted_seat_utilization := ud.customer_accepted_seats::DOUBLE / NULLIF(rc.billing_seats, 0),
        customer_expansion_demand := COALESCE(ud.customer_total_demand > rc.billing_seats, false),
        october_usage_halt := rc.active_users_2026_09 > 0 AND rc.active_users_2026_10 = 0,
        october_usage_drop := rc.usage_trend_pct < -0.20,
        data_source_disconnected_with_partners := rc.data_source_connected = false AND rc.partners_connected > 0,
        active_product_admins := ARRAY(
            SELECT struct_pack(user_id := u.user_id, org_id := w.org_id, full_name := u.full_name,
                email := u.email, verification_status := w.verification_status,
                is_primary_workspace := w.org_id = rc.primary_org_id,
                last_login_date := u.last_login_date, login_days_30d := u.login_days_30d)
            FROM workspaces w
            JOIN product_users u ON u.org_id = w.org_id
            WHERE w.domain = rc.billing_domain AND w.is_dormant = false
                AND u.role = 'admin' AND u.status = 'accepted' AND NOT u.is_internal_support
                AND u.login_days_30d > 0 AND u.last_login_date <= CAST('{{snapshot_date}}' AS DATE)
                AND NULLIF(trim(u.email), '') IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM bounced_emails b WHERE b.contact_email = lower(trim(u.email)))
                AND NOT EXISTS (SELECT 1 FROM crm_contact_details c
                    WHERE c.normalized_email = lower(trim(u.email)) AND c.left_company)
            ORDER BY (w.org_id = rc.primary_org_id) DESC, u.last_login_date DESC, u.user_id
        ),
        crm_contact_hygiene := ARRAY(
            SELECT struct_pack(contact_id := c.contact_id, email := c.email,
                first_name := c.first_name, last_name := c.last_name,
                left_company := c.left_company, email_bounced := c.email_bounced,
                possible_duplicate_contact_ids := ARRAY(
                    SELECT d.contact_id FROM crm_contact_details d
                    WHERE d.account_id = c.account_id AND d.contact_id <> c.contact_id
                        AND (d.normalized_email = c.normalized_email
                            OR (lower(trim(d.last_name)) = lower(trim(c.last_name))
                                AND left(lower(trim(d.first_name)), 1) = left(lower(trim(c.first_name)), 1)))
                    ORDER BY d.contact_id
                ))
            FROM crm_contact_details c
            WHERE c.account_id = rc.crm_account_id
            ORDER BY c.contact_id
        )
    )) AS enrichment
FROM customer_360 rc
LEFT JOIN user_demand ud ON rc.primary_org_id = ud.org_id;
