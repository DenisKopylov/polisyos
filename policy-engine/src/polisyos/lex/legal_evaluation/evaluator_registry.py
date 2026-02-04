from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import (
    ComponentEntry,
    ComponentKind,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
    ENTRY_POINT_GROUP_LEX_EVALUATORS,
    HostAbi,
    discover_components,
    validate_metadata,
)
from polisyos.core.components.ids import SemVer
from polisyos.core.contracts.lex import ChangeProposalRef, LegalEvaluationRequest, LegalReportRef
from polisyos.lex.errors import LexValidationError

LexEvaluatorFn = Callable[
    [FileSystemCAS, Path, LegalEvaluationRequest, str | None],
    tuple[LegalReportRef, list[ChangeProposalRef]],
]


@dataclass(slots=True)
class EvaluatorRecord:
    component_id: str
    base_id: str
    version: str
    evaluate: LexEvaluatorFn
    source: str


@dataclass(slots=True)
class EvaluatorBootstrapReport:
    registered: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)


class LexEvaluatorRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, EvaluatorRecord] = {}
        self._by_base: dict[str, list[EvaluatorRecord]] = {}

    def register(self, record: EvaluatorRecord) -> None:
        self._by_id[record.component_id] = record

        rows = [
            item
            for item in self._by_base.get(record.base_id, [])
            if item.component_id != record.component_id
        ]
        rows.append(record)
        rows.sort(key=lambda row: SemVer.parse(row.version), reverse=True)
        self._by_base[record.base_id] = rows

    def resolve(self, eval_policy_id: str) -> EvaluatorRecord:
        record = self._by_id.get(eval_policy_id)
        if record is not None:
            return record

        rows = self._by_base.get(eval_policy_id)
        if rows:
            return rows[0]

        raise LexValidationError(
            f"unsupported eval_policy_id: {eval_policy_id}",
            details={"available": ",".join(self.list_ids())},
        )

    def list_ids(self) -> list[str]:
        names = set(self._by_id.keys())
        names.update(self._by_base.keys())
        return sorted(names)


_GLOBAL_REGISTRY = LexEvaluatorRegistry()
_BUILTINS_REGISTERED = False


def get_evaluator_registry() -> LexEvaluatorRegistry:
    _ensure_builtin_evaluators()
    return _GLOBAL_REGISTRY


def _ensure_builtin_evaluators() -> None:
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return

    from polisyos.lex.legal_evaluation.evaluate import (
        evaluate_legality_impl as simple_v1_backend,
    )

    _GLOBAL_REGISTRY.register(
        EvaluatorRecord(
            component_id="lex.eval.simple_v1@1.0.0",
            base_id="lex.eval.simple_v1",
            version="1.0.0",
            evaluate=lambda cas, fact_log_root, request, segment_name: simple_v1_backend(
                cas=cas,
                fact_log_root=fact_log_root,
                request=request,
                segment_name=segment_name,
            ),
            source="builtin",
        )
    )
    _BUILTINS_REGISTERED = True


def bootstrap_component_evaluators(components_index: ComponentRegistry) -> EvaluatorBootstrapReport:
    report = EvaluatorBootstrapReport()
    host = HostAbi(versions={"ir_abi": "1.0", "world_abi": "1.0"}, strict=True)

    for entry in components_index.query(kind=ComponentKind.LEX_EVALUATOR):
        component_id = str(entry.metadata.component_id)
        issues = validate_metadata(
            entry.metadata,
            host_abi=host,
            available_components=components_index,
        )
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            report.errors.append(
                f"{component_id}: {'; '.join(issue.message for issue in errors)}"
            )
            continue

        try:
            created = entry.component.create()
        except Exception as exc:
            report.errors.append(f"{component_id}: component.create() failed: {exc}")
            continue

        evaluator = _coerce_evaluator(created)
        if evaluator is None:
            report.errors.append(
                f"{component_id}: evaluator must be callable or object with evaluate()"
            )
            continue

        _GLOBAL_REGISTRY.register(
            EvaluatorRecord(
                component_id=component_id,
                base_id=entry.metadata.component_id.base_id,
                version=entry.metadata.component_id.version,
                evaluate=evaluator,
                source=str(getattr(entry.source, "source_type", "entry_point")),
            )
        )
        report.registered.append(component_id)

    report.registered.sort()
    report.errors.sort()
    return report


def discover_and_bootstrap_evaluators(
    *,
    include_dev_scan: bool = True,
) -> EvaluatorBootstrapReport:
    discovered = discover_components(
        groups=[ENTRY_POINT_GROUP_LEX_EVALUATORS],
        include_dev_scan=include_dev_scan,
    )

    registry = ComponentRegistry()
    for row in discovered.components:
        registry.register(
            ComponentEntry(metadata=row.metadata, component=row.component, source=row.source),
            on_duplicate=DuplicateComponentIdPolicy.WARN,
        )

    report = bootstrap_component_evaluators(registry)
    report.discovery_errors = [
        f"{error.source}:{error.item or '<unknown>'}: {error.message}"
        for error in discovered.errors
    ]
    report.discovery_errors.sort()
    return report


def _coerce_evaluator(value: Any) -> LexEvaluatorFn | None:
    if callable(value):
        return lambda cas, fact_log_root, request, segment_name: _invoke_callable(
            value,
            cas=cas,
            fact_log_root=fact_log_root,
            request=request,
            segment_name=segment_name,
        )

    evaluate = getattr(value, "evaluate", None)
    if callable(evaluate):
        return lambda cas, fact_log_root, request, segment_name: _invoke_callable(
            evaluate,
            cas=cas,
            fact_log_root=fact_log_root,
            request=request,
            segment_name=segment_name,
        )

    return None


def _invoke_callable(
    callable_obj: Any,
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: LegalEvaluationRequest,
    segment_name: str | None,
) -> tuple[LegalReportRef, list[ChangeProposalRef]]:
    try:
        return callable_obj(
            cas=cas,
            fact_log_root=fact_log_root,
            request=request,
            segment_name=segment_name,
        )
    except TypeError:
        return callable_obj(
            cas=cas,
            fact_log_root=fact_log_root,
            request=request,
        )


__all__ = [
    "EvaluatorBootstrapReport",
    "LexEvaluatorRegistry",
    "discover_and_bootstrap_evaluators",
    "get_evaluator_registry",
]
