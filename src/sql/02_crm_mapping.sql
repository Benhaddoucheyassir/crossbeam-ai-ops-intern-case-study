-- 02_crm_mapping.sql
-- Join CRM data to the billing universe, handling missing or deleted CRM records
CREATE OR REPLACE TABLE crm_accounts AS
SELECT *,
    NULLIF(regexp_extract(lower(trim(website)), '^(?:[a-z][a-z0-9+.-]*://)?(?:www\.)?([^/:?#]+)', 1), '') AS website_domain,
    COUNT(*) OVER (PARTITION BY account_id) AS account_id_count
FROM read_csv_auto('{{data_dir}}/crm_accounts.csv');

CREATE OR REPLACE TABLE crm_mapping AS
SELECT 
    b.*,
    c.account_name AS crm_account_name,
    c.website AS crm_website,
    c.product_org_id AS crm_product_org_id,
    c.owner AS crm_owner,
    c.segment AS crm_segment,
    c.seats_purchased AS crm_seats,
    c.arr_usd AS crm_arr,
    CAST(c.renewal_date AS DATE) AS crm_renewal_date,
    c.pqa_score,
    COALESCE(c.is_deleted, false) AS crm_is_deleted,
    COALESCE(c.no_logins_last_45_days, false) AS crm_no_logins_45d
FROM billing_universe b
LEFT JOIN crm_accounts c ON b.crm_account_id = c.account_id AND c.account_id_count = 1;
