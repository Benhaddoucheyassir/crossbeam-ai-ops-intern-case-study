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
