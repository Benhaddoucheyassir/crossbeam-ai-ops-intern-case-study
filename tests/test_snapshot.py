import pytest
import json
import shutil
import pandas as pd
from src.run_pipeline import run_pipeline

DATA_DIR = './data'
SNAPSHOT_DATE = '2026-11-16'
@pytest.fixture(scope="module")
def snapshot_output(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("snapshot")
    run_pipeline(DATA_DIR, SNAPSHOT_DATE, str(output_dir))
    return output_dir


@pytest.fixture(scope="module")
def pipeline_output(snapshot_output):
    return pd.read_csv(snapshot_output / 'customer_360.csv')


@pytest.fixture(scope="module")
def accounts(snapshot_output):
    records = json.loads((snapshot_output / 'customer_360.json').read_text())
    return {record['primary_org_id']: record for record in records if record['primary_org_id']}

def test_tessel_orphan_billing(pipeline_output):
    tessel = pipeline_output[pipeline_output['billing_customer_name'] == 'Tessel Inc.']
    assert len(tessel) == 1
    assert pd.isna(tessel.iloc[0]['crm_account_id'])
    assert tessel.iloc[0]['revops_missing_crm_link'] == True
    assert tessel.iloc[0]['billing_domain'] == 'tessel.example'

def test_marlowe_analytics_workspace_resolution(pipeline_output):
    marlowe = pipeline_output[pipeline_output['billing_customer_name'] == 'Marlowe Analytics Ltd']
    assert len(marlowe) == 1
    assert marlowe.iloc[0]['primary_org_id'] == 'ORG-1041'
    assert marlowe.iloc[0]['verification_status'] == 'verified'

def test_quillon_health_multi_workspace(pipeline_output):
    quillon = pipeline_output[pipeline_output['billing_customer_name'] == 'Quillon Health']
    assert len(quillon) == 1
    assert quillon.iloc[0]['primary_org_id'] == 'ORG-1003'
    assert quillon.iloc[0]['shadow_count'] > 0
    assert 'ORG-1031' in str(quillon.iloc[0]['shadow_org_ids'])

def test_sable_insurance_contact_hygiene(pipeline_output):
    sable = pipeline_output[pipeline_output['billing_customer_name'] == 'Sable Insurance']
    assert len(sable) == 1
    assert sable.iloc[0]['active_contacts_count'] == 0
    assert 'Contact Hygiene' in sable.iloc[0]['priority_score']

def test_pellucid_bank_excluded_from_active(pipeline_output):
    pellucid = pipeline_output[pipeline_output['billing_customer_name'] == 'Pellucid Bank']
    assert len(pellucid) == 0

def test_halcyon_travel_renewal_seat_mismatch(pipeline_output):
    # Halcyon Travel (BIL-520) has renewal in 14 days and Billing (30) vs CRM (50) seat mismatch
    halcyon = pipeline_output[pipeline_output['billing_customer_name'] == 'Halcyon Travel']
    assert len(halcyon) == 1
    assert halcyon.iloc[0]['days_to_renewal'] == 14
    assert halcyon.iloc[0]['billing_seats'] == 30
    assert halcyon.iloc[0]['crm_seats'] == 50
    assert halcyon.iloc[0]['revops_data_mismatch'] == True
    assert halcyon.iloc[0]['priority_score'] == 'HIGH (Renewal + Seat Mismatch)'

def test_brightpath_learning_critical(pipeline_output):
    brightpath = pipeline_output[pipeline_output['billing_customer_name'] == 'Brightpath Learning Inc']
    assert len(brightpath) == 1
    assert brightpath.iloc[0]['days_to_renewal'] <= 90
    assert brightpath.iloc[0]['priority_score'] == 'CRITICAL'


def test_billing_book_is_unchanged(pipeline_output, snapshot_output):
    assert len(pipeline_output) == 17
    assert pipeline_output['billing_customer_id'].is_unique
    assert pipeline_output['billing_arr'].sum() == pytest.approx(492_099.96)
    summary = json.loads((snapshot_output / 'monday_summary.json').read_text())
    assert summary['total_active_customers'] == 17
    assert summary['total_billing_arr'] == 492_099.96
    assert round(summary['total_billing_arr'], -3) == 492_000


def test_internal_support_seat_adjustment(accounts):
    kestrel = accounts['ORG-1011']
    assert kestrel['internal_support_demand'] == 1
    assert kestrel['customer_accepted_seats'] == kestrel['accepted_seats'] - 1
    assert kestrel['customer_total_demand'] == kestrel['total_demand'] - 1
    assert kestrel['customer_accepted_seat_utilization'] == pytest.approx(
        kestrel['customer_accepted_seats'] / kestrel['billing_seats']
    )
    assert kestrel['customer_expansion_demand'] is True
    assert 'U-0267' not in {admin['user_id'] for admin in kestrel['active_product_admins']}


def test_admin_candidates_and_contact_hygiene(accounts):
    for org_id, name in (
        ('ORG-1013', 'Femi Adeyemi'),
        ('ORG-1002', 'Jules Lund'),
        ('ORG-1014', 'Noor Garza'),
        ('ORG-1005', 'Dara Ilunga'),
    ):
        assert name in {admin['full_name'] for admin in accounts[org_id]['active_product_admins']}

    sable = accounts['ORG-1013']
    assert [admin['full_name'] for admin in sable['active_product_admins']] == ['Femi Adeyemi']
    assert any(contact['email_bounced'] for contact in sable['crm_contact_hygiene'])
    arbor = {contact['contact_id']: contact for contact in accounts['ORG-1014']['crm_contact_hygiene']}
    assert arbor['CON-1401']['possible_duplicate_contact_ids'] == ['CON-1402']
    assert arbor['CON-1402']['possible_duplicate_contact_ids'] == ['CON-1401']
    quillon = accounts['ORG-1003']
    harper = next(admin for admin in quillon['active_product_admins'] if admin['full_name'] == 'Harper Benn')
    assert (harper['org_id'], harper['verification_status'], harper['is_primary_workspace']) == (
        'ORG-1031', 'pending', False
    )


def test_usage_and_connection_signals(accounts):
    brightpath = accounts['ORG-1002']
    assert brightpath['october_usage_drop'] is True
    assert brightpath['october_usage_halt'] is False
    assert brightpath['usage_trend_pct'] == pytest.approx(-3 / 7)
    for org_id, partners in (('ORG-1015', 9), ('ORG-1018', 3)):
        account = accounts[org_id]
        assert account['data_source_disconnected_with_partners'] is True
        assert account['partners_connected'] == partners
        assert account['partners_with_overlaps'] == 0
    assert accounts['ORG-1022']['data_source_disconnected_with_partners'] is False


def test_activity_match_provenance(accounts):
    sable = accounts['ORG-1013']['recent_activities']
    assert sable[0]['activity_id'] == 'ACT-0016'
    assert sable[0]['bounced'] is True
    tessel = accounts['ORG-1005']['recent_activities'][0]
    assert (tessel['activity_id'], tessel['crm_account_id'], tessel['match_basis']) == (
        'ACT-0008', None, 'billing_domain'
    )
    corvid = accounts['ORG-1006']['recent_activities'][0]
    assert (corvid['activity_id'], corvid['crm_account_id'], corvid['match_basis']) == (
        'ACT-0012', 'ACC-008', 'billing_domain'
    )


def test_usage_halt_and_support_only_demand(tmp_path):
    data_dir = tmp_path / 'data'
    shutil.copytree(DATA_DIR, data_dir)
    workspaces_path = data_dir / 'crossbeam_workspaces.csv'
    workspaces = pd.read_csv(workspaces_path)
    workspaces.loc[workspaces['org_id'] == 'ORG-1002', 'active_users_2026_10'] = 0
    workspaces.to_csv(workspaces_path, index=False)
    billing_path = data_dir / 'billing_subscriptions.csv'
    billing = pd.read_csv(billing_path)
    users = pd.read_csv(data_dir / 'crossbeam_users.csv')
    kestrel_demand = (users['org_id'] == 'ORG-1011').sum()
    billing.loc[billing['billing_customer_id'] == 'BIL-511', 'seats'] = kestrel_demand - 1
    billing.to_csv(billing_path, index=False)

    output_dir = tmp_path / 'output'
    run_pipeline(data_dir.as_posix(), SNAPSHOT_DATE, str(output_dir))
    records = json.loads((output_dir / 'customer_360.json').read_text())
    by_org = {record['primary_org_id']: record for record in records}
    assert by_org['ORG-1002']['october_usage_halt'] is True
    assert by_org['ORG-1002']['october_usage_drop'] is True
    assert by_org['ORG-1022']['october_usage_halt'] is False
    kestrel = by_org['ORG-1011']
    assert kestrel['total_demand'] > kestrel['billing_seats']
    assert kestrel['customer_total_demand'] == kestrel['billing_seats']
    assert kestrel['customer_expansion_demand'] is False


def test_cross_table_action_evidence(snapshot_output, accounts):
    corvid = accounts['ORG-1006']
    assert corvid['october_usage_halt'] is False
    assert corvid['login_evidence'] == {
        'accepted_customer_rows': 34,
        'rows_with_known_login': 34,
        'users_with_30d_login': 28,
        'latest_customer_login': '2026-10-24',
        'days_since_latest_customer_login': 23,
        'recent_login_gap': True,
        'derived_login_age_over_45_days': False,
    }
    assert [child['billing_customer_id'] for child in corvid['active_billing_children']] == ['BIL-507']
    assert {row['customer_contact_id'] for row in corvid['prospect_contact_collisions']} == {'CON-0601', 'CON-0602'}
    assert {activity_id for row in corvid['prospect_contact_collisions'] for activity_id in row['outbound_activity_ids']} == {
        'ACT-0010', 'ACT-0011'
    }
    signals = {signal['code']: signal for signal in corvid['action_signals']}
    assert signals['suppress_prospect_outreach']['owner'] == 'BD'
    assert signals['suppress_prospect_outreach']['same_day'] is True
    assert signals['acknowledge_removal_request']['source_ids'] == ['ACT-0012']
    assert accounts['ORG-1018']['prospect_contact_collisions'] == []
    assert accounts['ORG-1018']['inactive_prospect_matches'] == ['ACC-024']
    assert accounts['ORG-1041']['crm_workspace_link_status'] == 'differs_from_trusted_primary'
    assert accounts['ORG-1010']['crm_workspace_link_status'] == 'missing'

    rows = json.loads((snapshot_output / 'customer_360.json').read_text())
    fenwick = next(row for row in rows if row['billing_customer_id'] == 'BIL-525')
    assert fenwick['onboarding_workspace_missing'] is True
    assert fenwick['login_evidence'] is None
    assert fenwick['days_since_crm_contract_start'] == 46
    assert fenwick['priority_score'] == 'LOW'


def test_identity_candidates_and_routing(snapshot_output, accounts):
    tessel = accounts['ORG-1005']
    assert tessel['crm_account_id'] is None
    assert tessel['eligible_crm_email_count'] is None
    candidate, = tessel['crm_link_candidates']
    assert candidate['crm_account_id'] == 'ACC-005'
    assert candidate['candidate_contact_ids'] == ['CON-0502']
    assert [activity['activity_id'] for activity in candidate['candidate_activities']] == ['ACT-0007', 'ACT-0006']
    assert [activity['activity_id'] for activity in tessel['recent_activities']] == ['ACT-0008']

    sable = accounts['ORG-1013']
    assert sable['eligible_crm_email_count'] == 0
    clue, = sable['cross_workspace_identity_candidates']
    assert clue['other_user_id'] == 'U-0025'
    assert clue['other_status'] == 'pending_invite'
    dana, = sable['crm_contact_hygiene']
    assert dana['left_company'] is False

    arbor = accounts['ORG-1014']
    assert arbor['eligible_crm_email_count'] == 2
    assert any(signal['code'] == 'review_contact_aliases' for signal in arbor['action_signals'])
    juniper = accounts['ORG-1022']
    assert juniper['eligible_crm_email_count'] == 1
    assert juniper['login_evidence']['latest_customer_login'] is None
    assert juniper['login_evidence']['recent_login_gap'] is None

    summary = json.loads((snapshot_output / 'monday_summary.json').read_text())
    assert all(signal['same_day'] for signal in summary['action_queue'][:3])
    unrouted = {row['org_id']: row for row in summary['workspaces_outside_active_book']}
    assert set(unrouted) == {'ORG-1009', 'ORG-1030', 'ORG-1032'}
    assert unrouted['ORG-1030']['routing'] == 'bd_qualification_candidate'
    assert unrouted['ORG-1032']['routing'] == 'outside_active_book'
    assert unrouted['ORG-1009']['linked_departed_contact_ids'] == ['CON-0901']


def test_input_edge_cases_and_repeatable_outputs(tmp_path):
    data_dir = tmp_path / 'data'
    shutil.copytree(DATA_DIR, data_dir)

    def update_csv(name, transform):
        path = data_dir / name
        transform(pd.read_csv(path)).to_csv(path, index=False)

    def billing_changes(rows):
        rows.loc[rows['billing_customer_id'] == 'BIL-522', 'current_period_end'] = '2026-11-15'
        rows.loc[rows['billing_customer_id'] == 'BIL-520', 'seats'] = 17
        return rows

    def workspace_changes(rows):
        brightpath = rows[rows['org_id'] == 'ORG-1002']
        tied_row = brightpath.assign(org_id='ORG-9998')
        future_row = brightpath.assign(org_id='ORG-9999', created_at='2026-11-17')
        return pd.concat([future_row, tied_row, rows])

    def user_changes(rows):
        user = rows[rows['user_id'] == 'U-0267']
        return pd.concat([
            rows,
            user.assign(user_id='U-FUTURE', invited_at='2026-11-17'),
            user.assign(user_id='U-UNKNOWN', status='unknown'),
        ])

    update_csv('billing_subscriptions.csv', billing_changes)
    update_csv('crossbeam_workspaces.csv', workspace_changes)
    update_csv('crossbeam_users.csv', user_changes)
    update_csv('crm_accounts.csv', lambda rows: pd.concat([rows, rows[rows['account_id'] == 'ACC-004']]))
    update_csv('activity.csv', lambda rows: pd.concat([
        rows,
        rows[rows['activity_id'] == 'ACT-0016'].assign(
            activity_id='ACT-FUTURE', activity_date='2026-11-17', contact_email='femi.adeyemi@sableinsurance.example'
        ),
    ]))
    output_dir = tmp_path / 'first'
    run_pipeline(data_dir.as_posix(), SNAPSHOT_DATE, str(output_dir))
    records = json.loads((output_dir / 'customer_360.json').read_text())
    rows = {row['billing_customer_id']: row for row in records}
    assert len(rows) == len(records) == 17
    assert rows['BIL-504']['crm_workspace_link_status'] == 'unknown_crm_link'
    assert rows['BIL-502']['primary_org_id'] == 'ORG-1002'
    assert {org['org_id'] for org in rows['BIL-502']['related_workspaces']} == {'ORG-1002', 'ORG-9998'}
    assert rows['BIL-511']['total_demand'] == 34
    assert rows['BIL-522']['priority_score'] == 'HIGH (Contact Hygiene)'
    assert rows['BIL-520']['priority_score'] == 'HIGH (Expansion)'
    assert any(signal['code'] == 'reconcile_commercial_mismatch' for signal in rows['BIL-520']['action_signals'])
    assert rows['BIL-513']['active_product_admins'][0]['full_name'] == 'Femi Adeyemi'

    repeat_dir = tmp_path / 'repeat'
    run_pipeline(data_dir.as_posix(), SNAPSHOT_DATE, str(repeat_dir))
    for path in output_dir.iterdir():
        assert path.read_bytes() == (repeat_dir / path.name).read_bytes()
