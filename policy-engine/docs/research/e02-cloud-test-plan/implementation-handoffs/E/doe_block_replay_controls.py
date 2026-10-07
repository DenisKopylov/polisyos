"""Isolated removal controls for native DoE quantities, block admission and readback."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore
    from polisyos.scientist.methods.doe.designs import SensitivityResult


def pytest_configure() -> None:
    """Remove one runtime property while retaining its typed result/receipt shape."""
    selected = os.environ["E02_DOE_BLOCK_CONTROL"]
    if selected == "interaction":
        import numpy as np
        from SALib.analyze import sobol

        original = sobol.analyze

        def shape_only(*args: object, **kwargs: object) -> dict[str, object]:
            result = original(*args, **kwargs)
            for key in ("S1", "ST"):
                result[key] = np.zeros_like(result[key])
            result["S2"][np.isfinite(result["S2"])] = 0.0
            return result

        sobol.analyze = shape_only
    elif selected == "blocks":
        from polisyos.scientist.methods.doe import analysis

        analysis._admit_sobol_sample_blocks = lambda *args, **kwargs: None
    elif selected == "readback":
        from polisyos.core.canon import from_canonical_bytes
        from polisyos.scientist.methods.doe import _receipt

        def shape_only_readback(store: ArtifactStore, ref: ArtifactRef) -> SensitivityResult:
            manifest = store.get_manifest(ref)
            if (
                manifest.kind != _receipt._KIND
                or manifest.artifact_schema is None
                or manifest.artifact_schema.name != _receipt._KIND
                or manifest.artifact_schema.version != _receipt._VERSION
                or not store.verify(ref).ok
            ):
                raise ValueError("Control retains kind/schema/integrity admission")
            payload = from_canonical_bytes(store.get_bytes(ref))
            return _receipt._AnalysisReceipt.model_validate(payload).result

        _receipt._load_analysis = shape_only_readback
    else:
        raise ValueError(f"Unsupported DoE property removal: {selected}")
