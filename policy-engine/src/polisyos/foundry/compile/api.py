"""Compile Trinity policy bundles into CAS-backed Foundry execution plans.

This module owns the public `compile()` entrypoint used by Scientist runtime
nodes and tutorials. It accepts only `CompileRequest` payloads whose
`policy_ref.kind` points to an `ir.trinity_bundle`, resolves the Trinity
compiler backend deterministically, and persists a `CompileReport` failure
envelope when compilation cannot produce an executable plan.
"""
from __future__ import annotations

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.compiler.report import CompileReport, put_compile_report
from polisyos.core.contracts.foundry import CompileRequest, CompileResult


def compile(store: FileSystemCAS, request: CompileRequest) -> CompileResult:
    """Compile a Trinity bundle into a Foundry execution plan.

    The current public surface accepts only Trinity-backed compile requests and
    returns a structured `CompileResult`. Successful compilation writes
    `foundry.program_graph`, `foundry.exec_plan`, `foundry.slot_layout`,
    `foundry.treasury_plan`, and a `CompileReport` artifact into CAS. Failures
    are converted into `CompileResult(ok=False, exec_plan_ref=None, ...)`
    envelopes with a persisted `compile_report_ref`.

    Compilation is expected to be deterministic for identical CAS inputs and
    compile flags. Requests with unsupported `policy_ref.kind` or
    `input_kind` do not raise to callers; they return a failure result whose
    report notes include the validation error.

    Args:
        store: Content-addressed artifact store that contains the Trinity
            bundle and optional registry bundle, and receives derived compile
            artifacts.
        request: Compile contract referencing the policy bundle, registry
            bundle, validation flags, and compile-time determinism settings.

    Returns:
        `CompileResult` with `ok=True` and `exec_plan_ref` on success, or
        `ok=False` plus `compile_report_ref` and explanatory `notes` on any
        compile failure.

    Example:
        ```python
        from polisyos.core.contracts.foundry import CompileRequest
        from polisyos.foundry import compile

        result = compile(store, CompileRequest(policy_ref=trinity_bundle_ref))
        if not result.ok:
            report = store.get_bytes(result.compile_report_ref.artifact_id)
        else:
            exec_plan_ref = result.exec_plan_ref
        ```
    """

    try:
        _resolve_compiler(request)
        from .trinity_compiler import compile_trinity

        return compile_trinity(store, request)
    except Exception as exc:
        return _compile_exception(store, request, exc)


def _resolve_compiler(request: CompileRequest) -> str:
    """Resolve the compiler backend for the Trinity-only Foundry pipeline.

    Raises:
        ValueError: If `request.policy_ref.kind` is not `ir.trinity_bundle` or
            `request.input_kind` is neither `trinity` nor `auto`.
    """
    kind = request.policy_ref.kind
    if kind != "ir.trinity_bundle":
        raise ValueError(
            f"Unsupported policy_ref.kind: {kind}. Only 'ir.trinity_bundle' is accepted."
        )
    if request.input_kind == "trinity":
        return "trinity"
    if request.input_kind == "auto":
        return "trinity"
    raise ValueError(f"Unsupported input_kind: {request.input_kind}")


def _compile_exception(
    store: FileSystemCAS, request: CompileRequest, exc: Exception
) -> CompileResult:
    """Persist a compile failure report and return the corresponding envelope."""
    notes = [f"compile_exception:{type(exc).__name__}:{exc}"]
    compile_report = CompileReport(
        ok=False,
        policy_ref=request.policy_ref,
        registry_bundle_ref=request.registry_bundle_ref,
        notes=notes,
    )
    inputs = [InputRef(artifact_id=request.policy_ref.artifact_id, role="ir")]
    if request.registry_bundle_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=request.registry_bundle_ref.artifact_id, role="registry_bundle"
            )
        )
    compile_report_ref = put_compile_report(store, compile_report, inputs=inputs)
    return CompileResult(
        ok=False,
        exec_plan_ref=None,
        compile_report_ref=compile_report_ref,
        derived_refs=[],
        notes=notes,
    )
