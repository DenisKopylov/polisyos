"""Public backends jax runner module API."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from polisyos.core.canon import truncated_hash
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    capture_backend_runtime_fingerprint,
    capture_versions,
    runtime_stack_for,
    safe_version,
)
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.components.io import dematerialize_method_output

if TYPE_CHECKING:
    from polisyos.foundry.methods.compiler import MethodCompiler


class JaxRunner(MethodRunner):
    """Thin adapter around existing MethodCompiler execution path."""

    def __init__(self, compiler: MethodCompiler | None = None) -> None:
        if compiler is None:
            from polisyos.foundry.methods.compiler import MethodCompiler

            compiler = MethodCompiler()
        self._compiler = compiler

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.JAX})

    def is_available(self) -> bool:
        posture = capture_backend_runtime_fingerprint(ComputeBackend.JAX)
        return posture.available

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
            jit=signature.supports_jit,
        )
        compile_ms = (time.perf_counter() - compile_started) * 1000

        dynamic_params = {k: v for k, v in params.items() if k in signature.dynamic_param_names}
        dynamic_params["__seed__"] = seed
        dynamic_params["__rng__"] = jax.random.PRNGKey(seed)

        run_started = time.perf_counter()
        output = compiled(state, dynamic_params)
        output = jax.tree_util.tree_map(
            lambda x: x.block_until_ready() if hasattr(x, "block_until_ready") else x,
            output,
        )
        postprocess = getattr(method_class, "postprocess_output", None)
        if callable(postprocess):
            output = postprocess(output=output, state=state, params=params)
        exec_ms = (time.perf_counter() - run_started) * 1000

        runtime_stack = runtime_stack_for(method_class)
        versions: dict[str, str] = capture_versions(
            base_packages=("jaxlib",),
            runtime_stack=runtime_stack,
        )
        jax_ver = getattr(jax, "__version__", None)
        if jax_ver:
            versions["jax"] = jax_ver
        jaxlib_ver = safe_version("jaxlib")
        if jaxlib_ver:
            versions["jaxlib"] = jaxlib_ver

        fp_payload = {
            "backend": ComputeBackend.JAX.value,
            "seed": seed,
            "versions": versions,
            "runtime_stack": runtime_stack,
        }
        fingerprint = truncated_hash(json.dumps(fp_payload, sort_keys=True), length=16)
        slot_outputs = dematerialize_method_output(
            method_class=method_class,
            signature=signature,
            output=output,
        )

        posture = capture_backend_runtime_fingerprint(
            ComputeBackend.JAX,
            method_class=method_class,
            seed=seed,
            extra_versions=versions,
        )
        determinism_tier = posture.determinism_tier or DeterminismTier.NONDETERMINISTIC
        declared_tier = getattr(method_class, "determinism_tier", None)
        if declared_tier in {DeterminismTier.STATISTICAL, DeterminismTier.NONDETERMINISTIC}:
            determinism_tier = declared_tier

        return MethodResult(
            output=output,
            timing=MethodTiming(
                wall_time_ms=compile_ms + exec_ms,
                compile_time_ms=compile_ms,
            ),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.JAX,
                determinism_tier=determinism_tier,
                seed=seed,
                library_versions=versions,
                fingerprint=fingerprint,
                observed_tolerance_budget=posture.observed_tolerance_budget,
                note=posture.replay_semantics,
            ),
            slot_outputs=slot_outputs,
            artifacts={"backend_runtime_fingerprint": posture.as_dict()},
        )
