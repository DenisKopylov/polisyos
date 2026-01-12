# Deprecated module stub. The legacy implementations live in polisyos.scientist._legacy.nodes.
from __future__ import annotations

import warnings

warnings.warn(
    "polisyos.scientist.orchestrator.nodes is deprecated; use flow_nodes.py via build_workflow().",
    DeprecationWarning,
    stacklevel=2,
)

from polisyos.scientist._legacy.nodes import governor_node, simulator_node  # noqa: F401
