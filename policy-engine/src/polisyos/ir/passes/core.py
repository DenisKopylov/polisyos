"""Initial compiler-grade IR passes built on top of the stable IR contracts."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from polisyos.ir.analytics.estimand import EstimandAST, normalize_estimand_ast
from polisyos.ir.artifacts.lineage import build_artifact_lineage_graph
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.linker import link_trinity
from polisyos.ir.observation.causal_execution import CausalExecutionBundle
from polisyos.ir.passes.base import (
    IRAnalysis,
    IRPass,
    PassContext,
    PassDiagnostic,
    PassResult,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.ir.registry_fragments import (
    RegistryBundle,
    RegistryComposeRequest,
    compose_registry_fragments,
)
from polisyos.ir.trinity import TrinityBundle


class ArtifactRefTypeCheckResult(KernelModel):
    """Summarize artifact-ref validation across IR surfaces."""

    schema_version: str = "1.0"
    checked_ref_count: int = 0
    missing_ref_count: int = 0
    mismatched_ref_count: int = 0


class SlotMechanismReachability(KernelModel):
    """Describe the slot/mechanism dependency graph induced by linked Trinity policies."""

    schema_version: str = "1.0"
    reachable_mechanisms: list[str] = Field(default_factory=list)
    reachable_slots: list[str] = Field(default_factory=list)
    terminal_slots: list[str] = Field(default_factory=list)
    orphan_mechanisms: list[str] = Field(default_factory=list)
    unused_registry_slots: list[str] = Field(default_factory=list)


class UnusedArtifactAnalysisResult(KernelModel):
    """Summarize which artifacts are reachable from the declared roots."""

    schema_version: str = "1.0"
    root_artifact_ids: list[str] = Field(default_factory=list)
    used_artifact_ids: list[str] = Field(default_factory=list)
    unused_artifact_ids: list[str] = Field(default_factory=list)


def _sorted_diagnostics(diagnostics: Iterable[PassDiagnostic]) -> tuple[PassDiagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
            key=lambda diagnostic: (
                diagnostic.severity,
                diagnostic.code,
                tuple(str(part) for part in diagnostic.path),
                diagnostic.message,
            ),
        )
    )


def _registry_conflict_severity(conflict: Any) -> str:
    if conflict.conflict_kind == "duplicate_identical":
        return "info"
    if conflict.conflict_kind == "duplicate_different" and conflict.resolution != "none":
        return "warning"
    return "error"


def _iter_artifact_refs(
    value: Any,
    *,
    path: tuple[str | int, ...] = (),
) -> Iterable[tuple[tuple[str | int, ...], ArtifactRefModel]]:
    seen: set[int] = set()

    def _walk(
        candidate: Any,
        current_path: tuple[str | int, ...],
    ) -> Iterable[tuple[tuple[str | int, ...], ArtifactRefModel]]:
        obj_id = id(candidate)
        if obj_id in seen:
            return ()
        if isinstance(candidate, (BaseModel, dict, list, tuple, set, frozenset)):
            seen.add(obj_id)

        if isinstance(candidate, ArtifactRefModel):
            return ((current_path, candidate),)
        if isinstance(candidate, BaseModel):
            refs: list[tuple[tuple[str | int, ...], ArtifactRefModel]] = []
            for name in type(candidate).model_fields:
                refs.extend(_walk(getattr(candidate, name), (*current_path, name)))
            return tuple(refs)
        if isinstance(candidate, dict):
            refs = []
            for key, item in sorted(candidate.items(), key=lambda entry: str(entry[0])):
                refs.extend(_walk(item, (*current_path, str(key))))
            return tuple(refs)
        if isinstance(candidate, (list, tuple)):
            refs = []
            for index, item in enumerate(candidate):
                refs.extend(_walk(item, (*current_path, index)))
            return tuple(refs)
        if isinstance(candidate, (set, frozenset)):
            refs = []
            for item in sorted(candidate, key=repr):
                refs.extend(_walk(item, (*current_path, repr(item))))
            return tuple(refs)
        return ()

    return _walk(value, path)


def _coerce_estimand(value: Any) -> EstimandAST | None:
    if value is None:
        return None
    if isinstance(value, EstimandAST):
        return value
    try:
        return EstimandAST.model_validate(value)
    except ValidationError:
        return None


class RegistryDependencyPass(IRPass):
    """Compose registry fragments through the shared pass pipeline."""

    name = "registry_dependency"
    reads = ("registry_compose_request",)
    writes = ("registry_compose_result", "registry_bundle")

    def run(self, context: PassContext) -> PassResult:
        request = context.get("registry_compose_request")
        if request is None:
            return PassResult.noop()
        compose_request = (
            request
            if isinstance(request, RegistryComposeRequest)
            else RegistryComposeRequest.model_validate(request)
        )
        result = compose_registry_fragments(compose_request)
        diagnostics: list[PassDiagnostic] = []
        for conflict in result.conflicts:
            diagnostics.append(
                PassDiagnostic(
                    code=f"registry_{conflict.conflict_kind}",
                    severity=_registry_conflict_severity(conflict),
                    message=conflict.message or conflict.conflict_kind,
                    path=(conflict.registry_kind, conflict.item_key),
                    data={
                        "registry_kind": conflict.registry_kind,
                        "item_key": conflict.item_key,
                        "left_fragment_id": conflict.left_fragment_id,
                        "right_fragment_id": conflict.right_fragment_id,
                        "resolution": conflict.resolution,
                    },
                )
            )
        for warning in result.warnings:
            diagnostics.append(
                PassDiagnostic(
                    code="registry_warning",
                    severity="warning",
                    message=warning,
                )
            )
        return PassResult(
            surface_updates={
                "registry_compose_result": result,
                "registry_bundle": result.composed or RegistryBundle(),
            },
            diagnostics=_sorted_diagnostics(diagnostics),
        )


class TrinityLinkAnalysisPass(IRAnalysis):
    """Run the Trinity linker through the shared pipeline and cache its result."""

    name = "trinity_link"
    reads = ("trinity_bundle", "registry_bundle")

    def __init__(self, *, allow_extra_params: bool = False, strict: bool = True) -> None:
        self._allow_extra_params = allow_extra_params
        self._strict = strict

    def run(self, context: PassContext) -> PassResult:
        bundle = context.get("trinity_bundle")
        if bundle is None:
            return PassResult.noop()
        trinity_bundle = (
            bundle
            if isinstance(bundle, TrinityBundle)
            else TrinityBundle.model_validate(bundle)
        )
        registries = context.get("registry_bundle", RegistryBundle())
        registry_bundle = (
            registries
            if isinstance(registries, RegistryBundle)
            else RegistryBundle.model_validate(registries)
        )
        linked, report = link_trinity(
            trinity_bundle,
            registry_bundle,
            allow_extra_params=self._allow_extra_params,
            strict=self._strict,
        )
        diagnostics = _sorted_diagnostics(
            PassDiagnostic(
                code=f"link_{issue.code.value}",
                severity=issue.severity.value,
                message=issue.message,
                path=tuple(issue.path),
                data={"ids": dict(issue.ids), **dict(issue.data)},
            )
            for issue in report.issues
        )
        return PassResult(
            analysis_updates={
                "linked_trinity_bundle": linked,
                "link_report": report,
            },
            diagnostics=diagnostics,
        )


class CrossModelTypeCheckPass(IRAnalysis):
    """Validate artifact-ref compatibility and cross-surface invariants."""

    name = "cross_model_type_check"
    reads = (
        "artifact_store",
        "causal_execution_bundle",
        "linked_trinity_bundle",
        "normalized_estimand_ast",
        "estimand_ast",
    )

    def run(self, context: PassContext) -> PassResult:
        diagnostics: list[PassDiagnostic] = []
        checked_ref_count = 0
        missing_ref_count = 0
        mismatched_ref_count = 0

        estimand = _coerce_estimand(
            context.get("normalized_estimand_ast", context.get("estimand_ast"))
        )
        if estimand is not None:
            variables = set(estimand.all_variables)
            if estimand.treatment and estimand.treatment not in variables:
                diagnostics.append(
                    PassDiagnostic(
                        code="estimand_treatment_missing_from_all_variables",
                        severity="error",
                        message="estimand.treatment must be present in all_variables",
                    )
                )
            if estimand.outcome and estimand.outcome not in variables:
                diagnostics.append(
                    PassDiagnostic(
                        code="estimand_outcome_missing_from_all_variables",
                        severity="error",
                        message="estimand.outcome must be present in all_variables",
                    )
                )
            if not estimand.query_str.strip():
                diagnostics.append(
                    PassDiagnostic(
                        code="estimand_query_empty",
                        severity="error",
                        message="estimand.query_str must be non-empty",
                    )
                )

        store = context.get("artifact_store")
        get_manifest = getattr(store, "get_manifest", None) if store is not None else None
        surface_names = (
            "causal_execution_bundle",
            "linked_trinity_bundle",
        )
        if callable(get_manifest):
            for surface_name in surface_names:
                surface_value = context.get(surface_name)
                if surface_value is None:
                    continue
                for path, artifact_ref in _iter_artifact_refs(surface_value, path=(surface_name,)):
                    checked_ref_count += 1
                    try:
                        manifest = get_manifest(artifact_ref.artifact_id)
                    except FileNotFoundError:
                        missing_ref_count += 1
                        diagnostics.append(
                            PassDiagnostic(
                                code="artifact_ref_missing",
                                severity="error",
                            message=(
                                f"artifact ref '{artifact_ref.artifact_id}' "
                                "is missing from the store"
                            ),
                                path=path,
                            )
                        )
                        continue
                    if (
                        manifest.kind != artifact_ref.kind
                        or manifest.media_type != artifact_ref.media_type
                    ):
                        mismatched_ref_count += 1
                        diagnostics.append(
                            PassDiagnostic(
                                code="artifact_ref_type_mismatch",
                                severity="error",
                                message=(
                                    f"artifact ref '{artifact_ref.artifact_id}' expects "
                                f"{artifact_ref.kind}/{artifact_ref.media_type} "
                                "but manifest stores "
                                f"{manifest.kind}/{manifest.media_type}"
                            ),
                                path=path,
                            )
                        )
        result = ArtifactRefTypeCheckResult(
            checked_ref_count=checked_ref_count,
            missing_ref_count=missing_ref_count,
            mismatched_ref_count=mismatched_ref_count,
        )
        return PassResult(
            analysis_updates={"cross_model_type_check": result},
            diagnostics=_sorted_diagnostics(diagnostics),
        )


class EstimandNormalizationPass(IRAnalysis):
    """Normalize estimand ASTs for semantic dedupe and CAS stability."""

    name = "estimand_normalization"
    reads = ("estimand_ast",)

    def run(self, context: PassContext) -> PassResult:
        raw_estimand = context.get("estimand_ast")
        if raw_estimand is None:
            return PassResult.noop()
        estimand = (
            raw_estimand
            if isinstance(raw_estimand, EstimandAST)
            else EstimandAST.model_validate(raw_estimand)
        )
        normalized = normalize_estimand_ast(estimand)
        diagnostics: list[PassDiagnostic] = []
        if normalized != estimand:
            diagnostics.append(
                PassDiagnostic(
                    code="estimand_normalized",
                    severity="info",
                    message="estimand AST normalized to canonical algebraic form",
                )
            )
        return PassResult(
            analysis_updates={
                "normalized_estimand_ast": normalized,
                "estimand_content_hash": normalized.content_hash(prefix=True),
            },
            diagnostics=_sorted_diagnostics(diagnostics),
        )


class SlotMechanismReachabilityPass(IRAnalysis):
    """Compute reachability between linked mechanisms and runtime slots."""

    name = "slot_mechanism_reachability"
    reads = ("linked_trinity_bundle", "registry_bundle")

    def run(self, context: PassContext) -> PassResult:
        linked_bundle = context.get("linked_trinity_bundle")
        if linked_bundle is None:
            return PassResult.noop()

        reachable_mechanisms = sorted(set(linked_bundle.bindings.used_mechanisms))
        reachable_slots = sorted(
            set(linked_bundle.bindings.used_slots_read)
            | set(linked_bundle.bindings.used_slots_write)
        )
        terminal_slots = sorted(
            set(linked_bundle.bindings.used_slots_write)
            - set(linked_bundle.bindings.used_slots_read)
        )
        orphan_mechanisms = sorted(
            intervention.mechanism_id
            for intervention in linked_bundle.bindings.interventions
            if not intervention.reads_slots and not intervention.writes_slots
        )
        registry_bundle = context.get("registry_bundle")
        unused_registry_slots: list[str] = []
        if registry_bundle is not None:
            registry_bundle = (
                registry_bundle
                if isinstance(registry_bundle, RegistryBundle)
                else RegistryBundle.model_validate(registry_bundle)
            )
        if isinstance(registry_bundle, RegistryBundle) and registry_bundle.slots is not None:
            unused_registry_slots = sorted(
                set(registry_bundle.slots.slots) - set(reachable_slots)
            )
        result = SlotMechanismReachability(
            reachable_mechanisms=reachable_mechanisms,
            reachable_slots=reachable_slots,
            terminal_slots=terminal_slots,
            orphan_mechanisms=orphan_mechanisms,
            unused_registry_slots=unused_registry_slots,
        )
        diagnostics = _sorted_diagnostics(
            PassDiagnostic(
                code="orphan_mechanism",
                severity="warning",
                message=f"mechanism '{mechanism_id}' has no reachable slot edges",
                data={"mechanism_id": mechanism_id},
            )
            for mechanism_id in orphan_mechanisms
        )
        return PassResult(
            analysis_updates={"slot_mechanism_reachability": result},
            diagnostics=diagnostics,
        )


class UnusedArtifactAnalysisPass(IRAnalysis):
    """Build the artifact lineage graph and report artifacts unreachable from roots."""

    name = "unused_artifact_analysis"
    reads = (
        "artifact_store",
        "artifact_ids",
        "artifact_task_bindings",
        "root_artifact_ids",
        "causal_execution_bundle",
    )

    def _root_artifact_ids(self, context: PassContext) -> list[str]:
        explicit_roots = context.get("root_artifact_ids")
        if explicit_roots:
            return sorted({str(artifact_id) for artifact_id in explicit_roots})
        bundle = context.get("causal_execution_bundle")
        if bundle is not None:
            execution_bundle = (
                bundle
                if isinstance(bundle, CausalExecutionBundle)
                else CausalExecutionBundle.model_validate(bundle)
            )
            return sorted(str(artifact_id) for artifact_id in execution_bundle.root_artifact_ids())
        return []

    def run(self, context: PassContext) -> PassResult:
        store = context.get("artifact_store")
        if store is None:
            return PassResult.noop()

        artifact_ids = context.get("artifact_ids")
        task_bindings = context.get("artifact_task_bindings") or ()
        lineage_graph = build_artifact_lineage_graph(
            store,
            artifact_ids=artifact_ids,
            task_bindings=task_bindings,
        )
        root_artifact_ids = self._root_artifact_ids(context)
        used_artifact_ids: set[str] = set(root_artifact_ids)
        for artifact_id in list(root_artifact_ids):
            used_artifact_ids.update(lineage_graph.upstream_artifact_ids(artifact_id))

        graph_artifact_ids = sorted(
            str(node.artifact_id)
            for node in lineage_graph.nodes
            if node.artifact_id is not None
        )
        unused_artifact_ids = sorted(set(graph_artifact_ids) - used_artifact_ids)
        result = UnusedArtifactAnalysisResult(
            root_artifact_ids=root_artifact_ids,
            used_artifact_ids=sorted(used_artifact_ids),
            unused_artifact_ids=unused_artifact_ids,
        )
        diagnostics = _sorted_diagnostics(
            PassDiagnostic(
                code="unused_artifact",
                severity="warning",
                message=f"artifact '{artifact_id}' is unreachable from the declared roots",
                data={"artifact_id": artifact_id},
            )
            for artifact_id in unused_artifact_ids
        )
        return PassResult(
            analysis_updates={
                "artifact_lineage_graph": lineage_graph,
                "unused_artifact_analysis": result,
            },
            diagnostics=diagnostics,
        )


__all__ = [
    "ArtifactRefTypeCheckResult",
    "CrossModelTypeCheckPass",
    "EstimandNormalizationPass",
    "RegistryDependencyPass",
    "SlotMechanismReachability",
    "SlotMechanismReachabilityPass",
    "TrinityLinkAnalysisPass",
    "UnusedArtifactAnalysisPass",
    "UnusedArtifactAnalysisResult",
]
