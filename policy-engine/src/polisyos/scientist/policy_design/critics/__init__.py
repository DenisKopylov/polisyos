"""W6.E policy-design critic implementations."""

from __future__ import annotations

from polisyos.scientist.policy_design.critics.adversarial import AdversarialCritic
from polisyos.scientist.policy_design.critics.affected_person import AffectedPersonCritic
from polisyos.scientist.policy_design.critics.data import DataCritic
from polisyos.scientist.policy_design.critics.equity import EquityCritic
from polisyos.scientist.policy_design.critics.fiscal import FiscalCritic
from polisyos.scientist.policy_design.critics.implementation import ImplementationCritic
from polisyos.scientist.policy_design.critics.legal import LegalCritic
from polisyos.scientist.policy_design.critics.monitoring import MonitoringCritic

__all__ = [
    "AdversarialCritic",
    "AffectedPersonCritic",
    "DataCritic",
    "EquityCritic",
    "FiscalCritic",
    "ImplementationCritic",
    "LegalCritic",
    "MonitoringCritic",
]
