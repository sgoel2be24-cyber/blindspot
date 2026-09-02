from __future__ import annotations

import json

import pandas as pd
import pytest

from blindspot.contracts import SchemaError
from blindspot.data.split import temporal_split


def test_temporal_split_is_strict_tie_safe_and_order_invariant(synthetic_transactions):
    first = temporal_split(synthetic_transactions)
    shuffled = temporal_split(synthetic_transactions.sample(frac=1, random_state=91))

    assert set(first.train["TransactionID"]) == set(shuffled.train["TransactionID"])
    assert set(first.calibration["TransactionID"]) == set(shuffled.calibration["TransactionID"])
    assert set(first.evaluation["TransactionID"]) == set(shuffled.evaluation["TransactionID"])
    assert first.train["TransactionDT"].max() < first.calibration["TransactionDT"].min()
    assert first.calibration["TransactionDT"].max() < first.evaluation["TransactionDT"].min()

    split_ids = [
        set(first.train["TransactionID"]),
        set(first.calibration["TransactionID"]),
        set(first.evaluation["TransactionID"]),
    ]
    assert split_ids[0].isdisjoint(split_ids[1])
    assert split_ids[0].isdisjoint(split_ids[2])
    assert split_ids[1].isdisjoint(split_ids[2])
    assert json.loads(json.dumps(first.manifest()))["row_counts"]["train"] == len(first.train)


def test_temporal_split_rejects_too_few_time_groups():
    frame = pd.DataFrame({"TransactionID": [1, 2, 3], "TransactionDT": [1, 1, 2]})
    with pytest.raises(SchemaError, match="three distinct time groups"):
        temporal_split(frame)
