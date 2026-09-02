from __future__ import annotations

import pandas as pd
import pytest

from blindspot.contracts import SchemaError
from blindspot.data.ieee_cis import load_ieee_cis


def _transaction_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TransactionID": [1, 2, 3],
            "TransactionDT": [10, 20, 30],
            "TransactionAmt": [12.0, 9.5, 42.0],
            "V1": [0.1, None, 0.4],
            "isFraud": [0, 1, 0],
        }
    )


def test_loads_transaction_and_optional_identity(tmp_path):
    _transaction_frame().to_csv(tmp_path / "train_transaction.csv", index=False)
    pd.DataFrame(
        {
            "TransactionID": [1, 3],
            "DeviceType": ["mobile", "desktop"],
        }
    ).to_csv(tmp_path / "train_identity.csv", index=False)

    loaded = load_ieee_cis(tmp_path, include_identity=True)

    assert len(loaded) == 3
    assert loaded.loc[loaded["TransactionID"] == 2, "DeviceType"].isna().all()
    assert len(loaded.attrs["blindspot_source_files"]) == 2


def test_loader_requires_identity_only_when_requested(tmp_path):
    _transaction_frame().to_csv(tmp_path / "train_transaction.csv", index=False)

    assert len(load_ieee_cis(tmp_path, include_identity=False)) == 3
    with pytest.raises(FileNotFoundError, match="include_identity=True"):
        load_ieee_cis(tmp_path, include_identity=True)


def test_loader_rejects_non_binary_target(tmp_path):
    invalid = _transaction_frame()
    invalid.loc[0, "isFraud"] = 2
    invalid.to_csv(tmp_path / "train_transaction.csv", index=False)

    with pytest.raises(SchemaError, match="binary 0/1"):
        load_ieee_cis(tmp_path, include_identity=False)
