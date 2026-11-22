-- 03_workspace_resolution.sql
-- Resolve the primary workspace and flag shadow orgs
CREATE OR REPLACE TABLE workspaces AS
SELECT * REPLACE (lower(trim(domain)) AS domain)
FROM read_csv_auto('{{data_dir}}/crossbeam_workspaces.csv')
WHERE created_at <= CAST('{{snapshot_date}}' AS DATE);

CREATE OR REPLACE TABLE primary_workspaces AS
WITH workspace_ranking AS (
    SELECT 
        w.*,
        ROW_NUMBER() OVER (
            PARTITION BY w.domain 
            ORDER BY 
                created_at DESC, org_id
        ) as rank
    FROM workspaces w
    WHERE verification_status = 'verified' AND is_dormant = false
)
SELECT * FROM workspace_ranking WHERE rank = 1;

CREATE OR REPLACE TABLE shadow_workspaces AS
SELECT 
    domain,
    LIST(org_id ORDER BY org_id) as shadow_org_ids,
    COUNT(*) as shadow_count
FROM workspaces
WHERE (verification_status != 'verified' OR is_dormant = true)
GROUP BY domain;

CREATE OR REPLACE TABLE resolved_customers AS
SELECT 
    c.*,
    w.org_id AS primary_org_id,
    w.org_name AS primary_org_name,
    w.verification_status,
    w.is_dormant,
    CASE WHEN CAST('{{snapshot_date}}' AS DATE) >= DATE '2026-09-01' THEN w.active_users_2026_08 END AS active_users_2026_08,
    CASE WHEN CAST('{{snapshot_date}}' AS DATE) >= DATE '2026-10-01' THEN w.active_users_2026_09 END AS active_users_2026_09,
    CASE WHEN CAST('{{snapshot_date}}' AS DATE) >= DATE '2026-11-01' THEN w.active_users_2026_10 END AS active_users_2026_10,
    w.partners_connected,
    w.partners_with_overlaps,
    w.data_source_connected,
    w.add_seat_clicks_90d,
    s.shadow_org_ids,
    s.shadow_count
FROM crm_mapping c
LEFT JOIN primary_workspaces w ON lower(trim(c.billing_domain)) = w.domain
LEFT JOIN shadow_workspaces s ON lower(trim(c.billing_domain)) = s.domain;
