# Deprecated module stub. Use flow_nodes.py via build_workflow().
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.scientist.orchestrator.nodes is deprecated; use flow_nodes.py via build_workflow().",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.scientist.orchestrator.flow_nodes import (  # noqa: F401
    governor_node,
    run_sim_node as simulator_node,
)
