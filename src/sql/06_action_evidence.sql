CREATE OR REPLACE VIEW snapshot_activity AS
SELECT *, lower(trim(contact_email)) AS normalized_email
FROM read_csv_auto('{{data_dir}}/activity.csv')
WHERE activity_date <= CAST('{{snapshot_date}}' AS DATE);

CREATE OR REPLACE VIEW customer_login_evidence AS
SELECT org_id, COUNT(*) AS accepted_customer_rows,
    COUNT(*) FILTER (WHERE last_login_date <= CAST('{{snapshot_date}}' AS DATE)) AS rows_with_known_login,
    COUNT(*) FILTER (WHERE last_login_date <= CAST('{{snapshot_date}}' AS DATE)
        AND login_days_30d > 0) AS users_with_30d_login,
    MAX(last_login_date) FILTER (WHERE last_login_date <= CAST('{{snapshot_date}}' AS DATE)) AS latest_customer_login
FROM product_users
WHERE status = 'accepted' AND NOT is_internal_support
    AND (invited_at IS NULL OR invited_at <= CAST('{{snapshot_date}}' AS DATE))
GROUP BY org_id;

CREATE OR REPLACE VIEW customer_action_evidence AS
SELECT r.billing_customer_id,
    to_json(struct_pack(
        crm_contract_start := c.contract_start,
        crm_parent_account_id := c.parent_account_id,
        workspace_resolution_basis := CASE WHEN r.primary_org_id IS NOT NULL THEN 'verified_billing_domain' END,
        crm_workspace_link_status := CASE
            WHEN r.revops_missing_crm_link THEN 'unknown_crm_link'
            WHEN r.crm_product_org_id IS NULL THEN 'missing'
            WHEN NOT EXISTS (SELECT 1 FROM workspaces w WHERE w.org_id = r.crm_product_org_id) THEN 'unresolved'
            WHEN r.crm_product_org_id = r.primary_org_id THEN 'matches_primary'
            ELSE 'differs_from_trusted_primary'
        END,
        related_workspaces := ARRAY(
            SELECT struct_pack(org_id := w.org_id, parent_org_id := w.parent_org_id,
                plan_tier := w.plan_tier, verification_status := w.verification_status,
                is_dormant := w.is_dormant, created_at := w.created_at,
                active_users_2026_10 := CASE WHEN CAST('{{snapshot_date}}' AS DATE) >= DATE '2026-11-01'
                    THEN w.active_users_2026_10 END,
                is_primary_workspace := COALESCE(w.org_id = r.primary_org_id, false))
            FROM workspaces w
            WHERE w.domain = lower(trim(r.billing_domain)) OR w.org_id = r.crm_product_org_id
            ORDER BY w.org_id
        ),
        active_billing_children := ARRAY(
            SELECT struct_pack(billing_customer_id := child.billing_customer_id,
                crm_account_id := child.crm_account_id, billing_customer_name := child.billing_customer_name,
                primary_org_id := child.primary_org_id, billing_seats := child.billing_seats,
                billing_arr := child.billing_arr, active_users_2026_10 := child.active_users_2026_10)
            FROM final_report child JOIN crm_accounts child_crm
                ON child.crm_account_id = child_crm.account_id AND child_crm.account_id_count = 1
            WHERE child_crm.parent_account_id = r.crm_account_id AND NOT child_crm.is_deleted
            ORDER BY child.billing_customer_id
        ),
        crm_link_candidates := ARRAY(
            SELECT struct_pack(crm_account_id := candidate.account_id, account_name := candidate.account_name,
                website_domain := candidate.website_domain, crm_owner := candidate.owner,
                reason := 'contact_domain_and_billing_terms',
                candidate_contact_ids := ARRAY(
                    SELECT cc.contact_id FROM crm_contact_details cc
                    WHERE cc.account_id = candidate.account_id
                        AND split_part(cc.normalized_email, '@', 2) = lower(trim(r.billing_domain))
                    ORDER BY cc.contact_id),
                candidate_activities := ARRAY(
                    SELECT struct_pack(activity_id := a.activity_id, activity_date := a.activity_date,
                        contact_email := a.contact_email, subject := a.subject, summary := a.summary)
                    FROM snapshot_activity a WHERE a.account_id = candidate.account_id
                    ORDER BY a.activity_date DESC, a.activity_id DESC LIMIT 5))
            FROM crm_accounts candidate
            WHERE r.crm_account_id IS NULL AND candidate.account_id_count = 1
                AND NOT candidate.is_deleted AND candidate.account_type = 'Customer'
                AND candidate.seats_purchased = r.billing_seats
                AND ABS(candidate.arr_usd - r.billing_arr) <= 1
                AND candidate.renewal_date = r.current_period_end
                AND NOT EXISTS (SELECT 1 FROM billing_universe b WHERE b.crm_account_id = candidate.account_id)
                AND EXISTS (SELECT 1 FROM crm_contact_details cc WHERE cc.account_id = candidate.account_id
                    AND split_part(cc.normalized_email, '@', 2) = lower(trim(r.billing_domain)))
            ORDER BY candidate.account_id
        ),
        prospect_contact_collisions := ARRAY(
            SELECT DISTINCT struct_pack(prospect_account_id := p.account_id, prospect_owner := p.owner,
                prospect_contact_id := pc.contact_id, customer_contact_id := cc.contact_id,
                contact_email := cc.normalized_email,
                outbound_activity_ids := ARRAY(
                    SELECT a.activity_id FROM snapshot_activity a
                    WHERE a.account_id = p.account_id AND a.normalized_email = cc.normalized_email
                        AND a.direction = 'outbound' ORDER BY a.activity_id),
                removal_request_activity_ids := ARRAY(
                    SELECT a.activity_id FROM snapshot_activity a
                    WHERE a.account_id = p.account_id AND a.normalized_email = cc.normalized_email
                        AND a.direction = 'inbound'
                        AND regexp_matches(lower(a.summary), '(take me off|remove me from) (this|the|your) list')
                    ORDER BY a.activity_id))
            FROM crm_contact_details cc
            JOIN crm_contact_details pc ON cc.normalized_email = pc.normalized_email
            JOIN crm_accounts p ON pc.account_id = p.account_id AND p.account_id_count = 1
            WHERE cc.account_id = r.crm_account_id AND NOT r.revops_missing_crm_link
                AND p.account_type = 'Prospect' AND NOT p.is_deleted
                AND NULLIF(cc.normalized_email, '') IS NOT NULL
            ORDER BY 1
        ),
        inactive_prospect_matches := ARRAY(
            SELECT p.account_id FROM crm_accounts p
            WHERE p.is_deleted AND p.account_type = 'Prospect'
                AND p.website_domain = lower(trim(r.billing_domain))
            ORDER BY p.account_id
        ),
        cross_workspace_identity_candidates := ARRAY(
            SELECT DISTINCT struct_pack(contact_id := cc.contact_id, current_user_id := u.user_id,
                other_user_id := other_user.user_id, other_org_id := other_user.org_id,
                other_status := other_user.status)
            FROM crm_contact_details cc
            JOIN product_users u ON cc.normalized_email = lower(trim(u.email)) AND u.org_id = r.primary_org_id
            JOIN product_users other_user
                ON lower(trim(u.full_name)) = lower(trim(other_user.full_name))
                AND split_part(lower(trim(u.email)), '@', 1) = split_part(lower(trim(other_user.email)), '@', 1)
                AND u.org_id <> other_user.org_id AND lower(trim(u.email)) <> lower(trim(other_user.email))
            JOIN workspaces other_org ON other_user.org_id = other_org.org_id
            WHERE cc.account_id = r.crm_account_id AND NOT r.revops_missing_crm_link
                AND cc.email_bounced AND NULLIF(trim(u.full_name), '') IS NOT NULL
                AND (u.invited_at IS NULL OR u.invited_at <= CAST('{{snapshot_date}}' AS DATE))
                AND (other_user.invited_at IS NULL OR other_user.invited_at <= CAST('{{snapshot_date}}' AS DATE))
            ORDER BY 1
        ),
        login_evidence := CASE WHEN r.primary_org_id IS NOT NULL THEN struct_pack(
            accepted_customer_rows := COALESCE(l.accepted_customer_rows, 0),
            rows_with_known_login := COALESCE(l.rows_with_known_login, 0),
            users_with_30d_login := l.users_with_30d_login,
            latest_customer_login := l.latest_customer_login,
            days_since_latest_customer_login := date_diff('day', l.latest_customer_login, CAST('{{snapshot_date}}' AS DATE)),
            recent_login_gap := date_diff('day', l.latest_customer_login, CAST('{{snapshot_date}}' AS DATE)) >= 21,
            derived_login_age_over_45_days := date_diff('day', l.latest_customer_login, CAST('{{snapshot_date}}' AS DATE)) > 45
        ) END,
        days_since_crm_contract_start := date_diff('day', c.contract_start, CAST('{{snapshot_date}}' AS DATE)),
        onboarding_workspace_missing := r.primary_org_id IS NULL
            AND date_diff('day', c.contract_start, CAST('{{snapshot_date}}' AS DATE)) >= 30
    )) AS evidence
FROM final_report r
LEFT JOIN crm_accounts c ON r.crm_account_id = c.account_id AND c.account_id_count = 1 AND NOT c.is_deleted
LEFT JOIN customer_login_evidence l ON r.primary_org_id = l.org_id;

CREATE OR REPLACE VIEW workspace_routing_evidence AS
SELECT to_json(struct_pack(org_id := w.org_id, org_name := w.org_name, domain := w.domain,
    verification_status := w.verification_status, is_dormant := w.is_dormant,
    plan_tier := w.plan_tier, active_users_2026_10 := CASE WHEN CAST('{{snapshot_date}}' AS DATE) >= DATE '2026-11-01'
        THEN w.active_users_2026_10 END,
    latest_customer_login := l.latest_customer_login,
    days_since_latest_customer_login := date_diff('day', l.latest_customer_login, CAST('{{snapshot_date}}' AS DATE)),
    crm_account_ids := ARRAY(SELECT a.account_id FROM crm_accounts a
        WHERE a.product_org_id = w.org_id OR a.website_domain = w.domain ORDER BY a.account_id),
    linked_crm_login_flags := ARRAY(SELECT struct_pack(crm_account_id := a.account_id,
        no_logins_last_45_days := a.no_logins_last_45_days)
        FROM crm_accounts a WHERE a.product_org_id = w.org_id ORDER BY a.account_id),
    linked_departed_contact_ids := ARRAY(SELECT cc.contact_id FROM crm_contact_details cc
        JOIN crm_accounts a ON cc.account_id = a.account_id AND a.account_id_count = 1
        WHERE a.product_org_id = w.org_id AND NOT a.is_deleted AND cc.left_company ORDER BY cc.contact_id),
    billing_subscriptions := ARRAY(SELECT struct_pack(billing_customer_id := b.billing_customer_id, status := b.status)
        FROM read_csv_auto('{{data_dir}}/billing_subscriptions.csv') b
        WHERE lower(trim(b.billing_domain)) = w.domain ORDER BY b.billing_customer_id)
)) AS evidence
FROM workspaces w LEFT JOIN customer_login_evidence l ON w.org_id = l.org_id
WHERE NOT EXISTS (SELECT 1 FROM billing_universe b WHERE lower(trim(b.billing_domain)) = w.domain)
ORDER BY w.org_id;
