-- 01_billing_universe.sql
-- Create the foundation of active customers from billing data
CREATE OR REPLACE TABLE billing_universe AS
SELECT 
    billing_customer_id,
    billing_customer_name,
    billing_domain,
    crm_account_id,
    plan,
    seats AS billing_seats,
    mrr_usd AS billing_mrr,
    (mrr_usd * 12) AS billing_arr,
    CAST(current_period_end AS DATE) AS current_period_end,
    'active' as status
FROM read_csv_auto('{{data_dir}}/billing_subscriptions.csv')
WHERE status = 'active';
