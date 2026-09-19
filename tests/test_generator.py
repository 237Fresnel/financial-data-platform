from datetime import date
import pandas as pd
import numpy as np
from fdp.generator import inject_defects, DEFECT_TYPES
from fdp.generator import generate_reference, generate_day

DAY = date(2026, 9, 1)

def make(seed=42):
    customers, accounts = generate_reference(200, seed)
    return customers, accounts, generate_day(DAY, customers, accounts, 500, seed)

def test_reproducible():
    pd.testing.assert_frame_equal(make()[2], make()[2])

def test_clean_invariants():
    _, accounts, tx = make()
    assert tx["transaction_id"].is_unique
    assert (tx["amount"] > 0).all()
    assert tx["account_id"].isin(accounts["account_id"]).all()
    assert (tx["transaction_timestamp"].dt.date == DAY).all()

def test_defects_injected_as_declared():
    _, _, tx = make()
    dirty, manifest = inject_defects(tx, np.random.default_rng(0), rate=0.02, duplicate_rate=0.02)
    counts = manifest["defect_type"].value_counts()
    assert all(counts[d] == 10 for d in DEFECT_TYPES)   # 500 × 0,02
    assert counts["duplicate"] == 10
    assert len(dirty) == len(tx) + 10
    assert (dirty["currency"] == "ZZZ").sum() == 10
    assert (dirty["transaction_id"] == "").sum() == 10