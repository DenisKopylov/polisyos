from __future__ import annotations

import json
from unittest.mock import patch

from polisyos.foundry.methods.backends import runtime_fingerprint
from polisyos.foundry.methods.backends.runtime_fingerprint import BackendRuntimeFingerprint
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.plugins.training_adapter import TrainingBridgeError, _training_runtime_tier
from polisyos.foundry.runtime.fingerprint import DeterminismTier

results = []
for tier in (DeterminismTier.LIBRARY_DETERMINISTIC, DeterminismTier.STATISTICAL):
    profile = BackendRuntimeFingerprint(
        backend=ComputeBackend.JAX,
        available=True,
        determinism_tier=tier,
        execution_device="cpu:cpu",
        runtime_stack=(),
        seed=7,
    )
    with patch.object(runtime_fingerprint, "capture_backend_runtime_fingerprint", return_value=profile):
        try:
            _training_runtime_tier(7)
        except TrainingBridgeError as exc:
            assert exc.code == "training_runtime_profile_unsupported", (tier, exc.code)
            results.append({"tier": tier.value, "status": "typed_refusal", "code": exc.code})
        else:
            raise AssertionError(f"{tier.value} unexpectedly admitted")

print(json.dumps({"result": "PASS", "tiers": results, "optimizer_or_cas_invoked": False}, indent=2))
