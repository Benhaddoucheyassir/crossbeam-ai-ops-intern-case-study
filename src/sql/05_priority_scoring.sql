-- 05_priority_scoring.sql
-- Final prioritization and flags
CREATE OR REPLACE TABLE final_report AS
SELECT 
    *,
    -- Priority logic
    CASE 
        -- Critical: Imminent renewal (90 days) + Low usage/utilization
        WHEN days_to_renewal <= 90 AND (seat_utilization < 0.25 OR usage_trend_pct < -0.20) THEN 'CRITICAL'
        -- High: Seat demand exceeding purchased seats (Expansion opportunity)
        WHEN total_demand > billing_seats THEN 'HIGH (Expansion)'
        -- High: Imminent 30-day renewal + Billing/CRM seat mismatch (Commercial blocker / Stale CRM data)
        WHEN days_to_renewal <= 30 AND (billing_seats != crm_seats OR ABS(billing_arr - crm_arr) > 1) THEN 'HIGH (Renewal + Seat Mismatch)'
        -- High: Contact hygiene risk (< 2 active contacts)
        WHEN active_contacts_count < 2 THEN 'HIGH (Contact Hygiene)'
        -- Medium: Negative usage trend but renewal > 90 days
        WHEN usage_trend_pct < -0.10 THEN 'MEDIUM'
        ELSE 'LOW'
    END as priority_score,
    -- Flagging
    (crm_account_id IS NULL OR crm_is_deleted = true) as revops_missing_crm_link,
    (shadow_count > 0) as revops_shadow_workspaces,
    (billing_seats != crm_seats OR ABS(billing_arr - crm_arr) > 1) as revops_data_mismatch,
    (active_contacts_count = 0) as bd_no_contacts
FROM customer_360;
