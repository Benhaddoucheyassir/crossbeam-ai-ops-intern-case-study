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
