from __future__ import annotations

import json
import time
from importlib import metadata
from typing import TYPE_CHECKING, Any, Mapping

from polisyos.core.canon import truncated_hash
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)

if TYPE_CHECKING:
    from polisyos.foundry.methods.compiler import MethodCompiler


def _safe_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


class JaxRunner(MethodRunner):
    """Thin adapter around existing MethodCompiler execution path."""

    def __init__(self, compiler: "MethodCompiler | None" = None) -> None:
        if compiler is None:
            from polisyos.foundry.methods.compiler import MethodCompiler

            compiler = MethodCompiler()
        self._compiler = compiler

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.JAX})

    def is_available(self) -> bool:
        try:
            import jax  # noqa: F401
        except Exception:
            return False
        return True

    def execute(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        import jax

        compile_started = time.perf_counter()
        compiled = self._compiler.compile(
            method_name=signature.fqn,
            params=params,
        )
        compile_ms = (time.perf_counter() - compile_started) * 1000

        dynamic_params = {
            k: v for k, v in params.items() if k in signature.dynamic_param_names
        }

        run_started = time.perf_counter()
        output = compiled(state, dynamic_params)
        output = jax.tree_util.tree_map(
            lambda x: x.block_until_ready() if hasattr(x, "block_until_ready") else x,
            output,
        )
        exec_ms = (time.perf_counter() - run_started) * 1000

        versions: dict[str, str] = {}
        jax_ver = getattr(jax, "__version__", None)
        if jax_ver:
            versions["jax"] = jax_ver
        jaxlib_ver = _safe_version("jaxlib")
        if jaxlib_ver:
            versions["jaxlib"] = jaxlib_ver

        fp_payload = {
            "backend": ComputeBackend.JAX.value,
            "seed": seed,
            "versions": versions,
        }
        fingerprint = truncated_hash(json.dumps(fp_payload, sort_keys=True), length=16)

        return MethodResult(
            output=output,
            timing=MethodTiming(
                wall_time_ms=compile_ms + exec_ms,
                compile_time_ms=compile_ms,
            ),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.JAX,
                determinism_tier=DeterminismTier.STRICT_CPU,
                seed=seed,
                library_versions=versions,
                fingerprint=fingerprint,
            ),
        )
