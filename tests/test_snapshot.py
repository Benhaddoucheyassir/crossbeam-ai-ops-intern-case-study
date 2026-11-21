import pytest
import os
import pandas as pd
from src.run_pipeline import run_pipeline

DATA_DIR = './data'
SNAPSHOT_DATE = '2026-11-16'
OUTPUT_DIR = './output_test'

@pytest.fixture(scope="module")
def pipeline_output():
    run_pipeline(DATA_DIR, SNAPSHOT_DATE, OUTPUT_DIR)
    df = pd.read_csv(os.path.join(OUTPUT_DIR, 'customer_360.csv'))
    return df

def test_tessel_orphan_billing(pipeline_output):
    # BIL-505 (Tessel Inc.) has no crm_account_id but should be in the universe
    tessel = pipeline_output[pipeline_output['billing_customer_name'] == 'Tessel Inc.']
    assert len(tessel) == 1
    assert pd.isna(tessel.iloc[0]['crm_account_id'])
    assert tessel.iloc[0]['revops_missing_crm_link'] == True
    assert tessel.iloc[0]['billing_domain'] == 'tessel.example'

def test_marlowe_analytics_workspace_resolution(pipeline_output):
    # Marlowe has a failed/dormant org (ORG-1004) and a verified one (ORG-1041)
    marlowe = pipeline_output[pipeline_output['billing_customer_name'] == 'Marlowe Analytics Ltd']
    assert len(marlowe) == 1
    assert marlowe.iloc[0]['primary_org_id'] == 'ORG-1041'
    assert marlowe.iloc[0]['verification_status'] == 'verified'

def test_quillon_health_multi_workspace(pipeline_output):
    # Quillon has verified ORG-1003 and pending ORG-1031
    quillon = pipeline_output[pipeline_output['billing_customer_name'] == 'Quillon Health']
    assert len(quillon) == 1
    assert quillon.iloc[0]['primary_org_id'] == 'ORG-1003'
    assert quillon.iloc[0]['shadow_count'] > 0
    assert 'ORG-1031' in str(quillon.iloc[0]['shadow_org_ids'])

def test_sable_insurance_contact_hygiene(pipeline_output):
    # Sable Insurance (ACC-013) has 1 contact that bounced
    sable = pipeline_output[pipeline_output['billing_customer_name'] == 'Sable Insurance']
    assert len(sable) == 1
    assert sable.iloc[0]['active_contacts_count'] == 0
    assert 'Contact Hygiene' in sable.iloc[0]['priority_score']

def test_pellucid_bank_excluded_from_active(pipeline_output):
    # Pellucid Bank (BIL-509) is 'canceled' in billing_subscriptions.csv, so it must NOT be in customer_360
    pellucid = pipeline_output[pipeline_output['billing_customer_name'] == 'Pellucid Bank']
    assert len(pellucid) == 0

def test_halcyon_travel_data_mismatch(pipeline_output):
    # Halcyon Travel (BIL-520) has 30 seats in billing, 50 in CRM
    halcyon = pipeline_output[pipeline_output['billing_customer_name'] == 'Halcyon Travel']
    assert len(halcyon) == 1
    assert halcyon.iloc[0]['billing_seats'] == 30
    assert halcyon.iloc[0]['crm_seats'] == 50
    assert halcyon.iloc[0]['revops_data_mismatch'] == True

def test_brightpath_learning_critical(pipeline_output):
    # Brightpath (BIL-502) has renewal 2026-12-20 (within 90 days) and low usage
    brightpath = pipeline_output[pipeline_output['billing_customer_name'] == 'Brightpath Learning Inc']
    assert len(brightpath) == 1
    assert brightpath.iloc[0]['days_to_renewal'] <= 90
    assert brightpath.iloc[0]['priority_score'] == 'CRITICAL'
