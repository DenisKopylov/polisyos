"""Public CausalEngine API assembled from Phase 4.1 split modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.protocol import ArtifactStore

if TYPE_CHECKING:
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore

from . import artifacts as _artifacts
from . import discovery as _discovery
from . import identification as _identification
from .artifacts import CausalEngineArtifactsMixin
from .discovery import CausalEngineDiscoveryMixin
from .estimation import CausalEngineEstimationMixin
from .identification import CausalEngineIdentificationMixin
from .sensitivity import CausalEngineSensitivityMixin


class CausalEngine(
    CausalEngineDiscoveryMixin,
    CausalEngineIdentificationMixin,
    CausalEngineSensitivityMixin,
    CausalEngineEstimationMixin,
    CausalEngineArtifactsMixin,
):
    """Pearl-Bareinboim causal engine: identify -> compile -> estimate -> audit."""

    def __init__(
        self,
        registry: Any = None,
        knowledge_base: Any | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._registry = registry
        self._kb = knowledge_base
        self._artifact_store = artifact_store

    @property
    def _ir_artifact_store(self) -> IRArtifactStore | None:
        """Select the IR port while retaining the raw Core owner for Core-only work."""
        if self._artifact_store is None:
            return None
        return ensure_ir_artifact_store(self._artifact_store)


_artifacts.CausalEngine = CausalEngine
_discovery.CausalEngine = CausalEngine
_identification.CausalEngine = CausalEngine


__all__ = ["CausalEngine"]
