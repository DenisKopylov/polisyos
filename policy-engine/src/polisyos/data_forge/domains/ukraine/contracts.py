"""Contract markers owned by the Data Forge Ukraine domain."""

from __future__ import annotations


class RealBacktestBundleContract:
    """Marker for real-history Ukraine backtest bundle metadata."""

    contract_namespace = "polisyos.data_forge.domains.ukraine"
    contract_family = "real_backtest_bundle"


REAL_BACKTEST_BUNDLE_CONTRACT_FQN = (
    "polisyos.data_forge.domains.ukraine.contracts.RealBacktestBundleContract"
)

__all__ = ["REAL_BACKTEST_BUNDLE_CONTRACT_FQN", "RealBacktestBundleContract"]
