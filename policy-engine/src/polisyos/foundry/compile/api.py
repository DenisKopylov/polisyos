from __future__ import annotations

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.compiler.report import CompileReport, put_compile_report
from polisyos.core.contracts.foundry import CompileRequest, CompileResult

from .surface_compiler import compile_surface
from .trinity_compiler import compile_trinity


def compile(store: FileSystemCAS, request: CompileRequest) -> CompileResult:
    try:
        compiler = _resolve_compiler(request)
        if compiler == "surface":
            return compile_surface(store, request)
        return compile_trinity(store, request)
    except Exception as exc:
        return _compile_exception(store, request, exc)


def _resolve_compiler(request: CompileRequest) -> str:
    kind = request.policy_ref.kind
    if request.input_kind == "auto":
        if kind == "ir.policy_surface":
            return "surface"
        if kind == "ir.trinity_bundle":
            return "trinity"
        raise ValueError(f"Unsupported policy_ref.kind: {kind}")
    if request.input_kind == "surface" and kind != "ir.policy_surface":
        raise ValueError(f"policy_ref.kind mismatch: expected ir.policy_surface, got {kind}")
    if request.input_kind == "trinity" and kind != "ir.trinity_bundle":
        raise ValueError(f"policy_ref.kind mismatch: expected ir.trinity_bundle, got {kind}")
    return request.input_kind


def _compile_exception(
    store: FileSystemCAS, request: CompileRequest, exc: Exception
) -> CompileResult:
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
