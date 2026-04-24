"""Expose intervention-to-runtime wiring contracts and executors for agent simulation.

The facade exports only the vectorized batch contracts and executor classes
that bridge compiled intervention parameters into synthetic `GlobalState`
updates. Low-level helper functions inside submodules remain internal unless
explicitly re-exported here.
"""

from .contracts import (
    FirmLifecycleEventBatch,
    FirmLifecycleEventType,
    InterventionMechanismConfig,
    ProcurementShockBatch,
    multiplex_layer_code,
)
from .executors import (
    ContractsDistributionAwareExecutor,
    ContractsGraphAwareExecutor,
    ContractsPopulationAwareExecutor,
)

__all__ = [
    "ContractsDistributionAwareExecutor",
    "ContractsGraphAwareExecutor",
    "ContractsPopulationAwareExecutor",
    "FirmLifecycleEventBatch",
    "FirmLifecycleEventType",
    "InterventionMechanismConfig",
    "ProcurementShockBatch",
    "multiplex_layer_code",
]
