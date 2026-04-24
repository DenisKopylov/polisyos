"""Expose the built-in economics plugin and its registration entrypoint."""

from .mechanisms import (
    ConsumptionMechanism,
    LaborMarketMechanism,
    SavingsMechanism,
    TaxationMechanism,
    TransferMechanism,
)
from .objectives import (
    GDPObjective,
    GiniObjective,
    RawlsianWelfare,
    SocialWelfareObjective,
    UnemploymentObjective,
    UtilitarianWelfare,
)
from .plugin import EconomicsPlugin
from .rewards import EconomicReward
from .state import EconomicAgentState, EconomicPolicyState, EconomicState

__all__ = [
    "ConsumptionMechanism",
    "EconomicAgentState",
    "EconomicPolicyState",
    "EconomicReward",
    "EconomicState",
    "EconomicsPlugin",
    "GDPObjective",
    "GiniObjective",
    "LaborMarketMechanism",
    "RawlsianWelfare",
    "SavingsMechanism",
    "SocialWelfareObjective",
    "TaxationMechanism",
    "TransferMechanism",
    "UnemploymentObjective",
    "UtilitarianWelfare",
]
