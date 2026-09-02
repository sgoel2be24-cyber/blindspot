from __future__ import annotations

import pytest

from blindspot.synthetic import SyntheticConfig, make_synthetic_transactions


@pytest.fixture
def synthetic_transactions():
    return make_synthetic_transactions(SyntheticConfig(rows=1_200, seed=1729))
