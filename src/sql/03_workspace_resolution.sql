-- 03_workspace_resolution.sql
-- Resolve the primary workspace and flag shadow orgs
CREATE OR REPLACE TABLE workspaces AS SELECT * FROM read_csv_auto('{{data_dir}}/crossbeam_workspaces.csv');

CREATE OR REPLACE TABLE primary_workspaces AS
WITH workspace_ranking AS (
    SELECT 
        w.*,
        ROW_NUMBER() OVER (
            PARTITION BY w.domain 
            ORDER BY 
                CASE WHEN w.verification_status = 'verified' THEN 0 ELSE 1 END,
                CASE WHEN w.is_dormant = false THEN 0 ELSE 1 END,
                created_at DESC
        ) as rank
    FROM workspaces w
)
SELECT * FROM workspace_ranking WHERE rank = 1;

CREATE OR REPLACE TABLE shadow_workspaces AS
SELECT 
    domain,
    LIST(org_id) as shadow_org_ids,
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
    w.active_users_2026_08,
    w.active_users_2026_09,
    w.active_users_2026_10,
    w.partners_connected,
    w.partners_with_overlaps,
    w.data_source_connected,
    w.add_seat_clicks_90d,
    s.shadow_org_ids,
    s.shadow_count
FROM crm_mapping c
LEFT JOIN primary_workspaces w ON c.billing_domain = w.domain
LEFT JOIN shadow_workspaces s ON c.billing_domain = s.domain;
