"""Legacy iterative search controller for ask/evaluate search loops."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable, Iterator, Mapping
from contextvars import ContextVar
from copy import copy, deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from functools import lru_cache, wraps
from math import isfinite
from threading import Lock
from types import SimpleNamespace
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NoReturn,
    Protocol,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticSerializationError, SchemaSerializer, core_schema
from pydantic_core.core_schema import CoreSchema

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.search.contracts import (
    ParetoBasisScope,
    SearchIteration,
    SearchResult,
    SearchStatus,
    _EvaluationDisposition,
    _EvaluationTransition,
)
from polisyos.scientist.methods.search.frontier import (
    FrontierPoint,
    dominates,
    policy_candidate_hash,
    update_legacy_pareto_front,
)
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
)
from polisyos.scientist.methods.search.run_state import SearchRunState
from polisyos.scientist.methods.search.sentinels import extract_sentinel_metadata
from polisyos.scientist.methods.search.stopping import (
    StoppingCondition,
    StoppingCriterion,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

if TYPE_CHECKING:
    from polisyos.core.llm import TracedLLMClient
    from polisyos.core.observability import MetricsRegistry
    from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
    from polisyos.scientist.methods.search.strategies.transfer import (
        TransferLearningManager,
    )
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import (
        BudgetMiddleware,
    )
    from polisyos.scientist.policy_design.objectives import (
        ObjectiveStack,
        PolicyEvaluationVector,
    )

logger = get_logger(__name__)

_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)
_SEARCH_DEGRADED_ERRORS = (AttributeError, TypeError, ValidationError, ValueError)

CandidatePayload = dict[str, Any]
SearchContext = dict[str, Any]
StageAEvaluator = Callable[[CandidatePayload, SearchContext], tuple[float, bool]]
StageBEvaluator = Callable[[CandidatePayload, SearchContext], dict[str, Any]]


def _default_metrics() -> MetricsRegistry:
    from polisyos.core.observability import get_metrics

    return get_metrics()


def _search_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="search.controller",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class _PolicyEvaluationResolution:
    """Keep absent, valid, and invalid typed results distinct at the consumer."""

    value: Any | None
    status: str
    reason: str | None = None


class _OwnerBudgetStopping(StoppingCriterion):
    """Fail closed unless one exact durable owner snapshot leaves budget."""

    def __init__(self, delegate: StoppingCriterion) -> None:
        self._delegate = delegate

    @property
    def name(self) -> str:
        return f"{self._delegate.name}+durable_producer_budget"

    def state_keys(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self._delegate.state_keys(), "_source_budget_remaining_usd")))

    def reset(self) -> None:
        self._delegate.reset()

    def check(
        self,
        history: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> StoppingCondition:
        remaining = state.get("_source_budget_remaining_usd")
        try:
            valid_remaining = (
                isinstance(remaining, (int, float, Decimal))
                and not isinstance(remaining, bool)
                and isfinite(float(remaining))
            )
        except (OverflowError, TypeError, ValueError):
            valid_remaining = False
        if not valid_remaining:
            return StoppingCondition(
                should_stop=True,
                reason="Durable producer budget unavailable; search stopped",
                details={"budget_available": False},
            )
        if Decimal(str(remaining)) <= Decimal(0):
            return StoppingCondition(
                should_stop=True,
                reason="Durable producer budget exhausted; search stopped",
                details={"budget_available": True},
            )
        return self._delegate.check(history, state)


def _non_reentrant_run(
    method: Callable[..., SearchResult],
) -> Callable[..., SearchResult]:
    """Guard one controller lifecycle against overlapping invocations."""

    @wraps(method)
    def guarded(self: Any, *args: Any, **kwargs: Any) -> SearchResult:
        run_lock = self._run_lock
        if not run_lock.acquire(blocking=False):
            raise RuntimeError("SearchController.run is not reentrant")
        try:
            return method(self, *args, **kwargs)
        finally:
            run_lock.release()

    return guarded


class CandidateGenerator(Protocol):
    """Generate the next candidate proposal from search history and context."""

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Propose one candidate payload for the next evaluator round.

        Args:
            history: Prior iterations with objective values and Stage B feedback.
            current_best: Current best candidate payload, if any.
            context: Planner/runtime context assembled by the caller.

        Returns:
            JSON-compatible candidate payload accepted by the Stage A/B evaluators.
        """


class SearchBudgetProducerUnsupportedError(RuntimeError):
    """A protected search cannot prove the selected provider and owner path."""

    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}")


class _PromptTypedRefusalAbort(Exception):
    """Stop CoreSchema serialization after preserving the typed prompt refusal."""


def _prompt_refuse(reason_code: str, detail: str) -> NoReturn:
    raise SearchBudgetProducerUnsupportedError(reason_code, detail)


def _prompt_literal_strings(annotation: Any) -> set[str]:
    if get_origin(annotation) is Literal:
        return {value for value in get_args(annotation) if isinstance(value, str)}
    values: set[str] = set()
    for nested in get_args(annotation):
        values.update(_prompt_literal_strings(nested))
    return values


@lru_cache(maxsize=1)
def _prompt_core_schema_types() -> frozenset[str]:
    """Read supported node tags from the pinned Pydantic CoreSchema union."""
    schema_types: set[str] = set()
    for schema_type in get_args(CoreSchema):
        try:
            annotations = get_type_hints(schema_type, include_extras=True)
        except (NameError, TypeError):
            annotations = getattr(schema_type, "__annotations__", {})
        schema_types.update(_prompt_literal_strings(annotations.get("type")))
    return frozenset(schema_types)


_PROMPT_OPAQUE_SCHEMA_KEYS = frozenset(
    {"metadata", "config", "function", "cls", "default", "default_factory"}
)
_PROMPT_SERIALIZER_TYPES = frozenset({"function-plain", "function-wrap"})
_PROMPT_SERIALIZER_CACHE: dict[type[BaseModel], tuple[Any, SchemaSerializer]] = {}
_PROMPT_SERIALIZER_CACHE_LOCK = Lock()


_PROMPT_ACTIVE_GRAPH: ContextVar[set[int] | None] = ContextVar(
    "polisyos_search_prompt_active_graph",
    default=None,
)
_PROMPT_TYPED_REFUSALS: ContextVar[list[SearchBudgetProducerUnsupportedError] | None] = ContextVar(
    "polisyos_search_prompt_typed_refusals",
    default=None,
)


def _prompt_capture_typed_refusal(
    refusal: SearchBudgetProducerUnsupportedError,
) -> bool:
    pending = _PROMPT_TYPED_REFUSALS.get()
    if pending is None:
        return False
    if not pending:
        pending.append(refusal)
    return True


def _prompt_preserve_typed_refusal(
    callback: Callable[..., Any],
) -> Callable[..., Any]:
    """Carry a typed guard result across Pydantic's callback error wrapper."""

    @wraps(callback)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        if _PROMPT_TYPED_REFUSALS.get():
            raise _PromptTypedRefusalAbort
        try:
            result = callback(*args, **kwargs)
        except SearchBudgetProducerUnsupportedError as exc:
            if not _prompt_capture_typed_refusal(exc):
                raise
            raise _PromptTypedRefusalAbort from None
        if _PROMPT_TYPED_REFUSALS.get():
            raise _PromptTypedRefusalAbort
        return result

    return guarded


def _prompt_track_active_graph(value: Any, operation: Callable[[], Any]) -> Any:
    """Reject a cycle that crosses a mapping and a nested Pydantic model."""
    active = _PROMPT_ACTIVE_GRAPH.get()
    token = None
    if active is None:
        active = set()
        token = _PROMPT_ACTIVE_GRAPH.set(active)
    identity = id(value)
    if identity in active:
        _prompt_refuse(
            "search_prompt_contains_cycle",
            "prompt values must form an acyclic JSON projection",
        )
    active.add(identity)
    try:
        return operation()
    finally:
        active.remove(identity)
        if token is not None:
            _PROMPT_ACTIVE_GRAPH.reset(token)


def _prompt_selected_child(
    include: Any,
    exclude: Any,
    key: Any,
    *,
    sequence_length: int | None = None,
) -> tuple[bool, Any, Any]:
    """Resolve one child against Pydantic's include/exclude selector shapes."""
    sequence = sequence_length is not None
    negative_key = key - sequence_length if sequence and isinstance(key, int) else None
    if include is None or include is True or include is Ellipsis:
        child_include = None
    elif isinstance(include, (set, frozenset)):
        if (
            (sequence and "__all__" in include)
            or key in include
            or (negative_key is not None and negative_key in include)
        ):
            child_include = None
        else:
            return False, None, None
    elif isinstance(include, Mapping):
        if key in include:
            child_include = include[key]
        elif negative_key is not None and negative_key in include:
            child_include = include[negative_key]
        elif sequence and "__all__" in include:
            child_include = include["__all__"]
        else:
            return False, None, None
        if child_include is False:
            return False, None, None
        if child_include is True or child_include is Ellipsis:
            child_include = None
    else:
        _prompt_refuse(
            "search_prompt_projection_selector_unsupported",
            "the selected serializer include selector has an unsupported shape",
        )

    if exclude is True or exclude is Ellipsis:
        return False, None, None
    if exclude is None:
        child_exclude = None
    elif isinstance(exclude, (set, frozenset)):
        if sequence and "__all__" in exclude:
            child_exclude = None
        elif key in exclude or (negative_key is not None and negative_key in exclude):
            return False, None, None
        else:
            child_exclude = None
    elif isinstance(exclude, Mapping):
        if key in exclude:
            child_exclude = exclude[key]
        elif negative_key is not None and negative_key in exclude:
            child_exclude = exclude[negative_key]
        elif sequence and "__all__" in exclude:
            child_exclude = exclude["__all__"]
        else:
            child_exclude = None
        if child_exclude is True or child_exclude is Ellipsis:
            return False, None, None
        if child_exclude is False:
            child_exclude = None
    else:
        _prompt_refuse(
            "search_prompt_projection_selector_unsupported",
            "the selected serializer exclude selector has an unsupported shape",
        )
    return True, child_include, child_exclude


def _prompt_validate_raw_graph(
    value: Any,
    *,
    include: Any = None,
    exclude: Any = None,
) -> None:
    """Reject lossy leaves in the selected raw graph before JSON serialization."""
    active: set[int] = set()

    def enter(container: Any, visit_children: Callable[[], None]) -> None:
        identity = id(container)
        if identity in active:
            _prompt_refuse(
                "search_prompt_contains_cycle",
                "prompt values must form an acyclic JSON projection",
            )
        active.add(identity)
        try:
            visit_children()
        finally:
            active.remove(identity)

    def visit(item: Any, item_include: Any, item_exclude: Any) -> None:
        if isinstance(item, Enum):
            enter(item, lambda: visit(item.value, item_include, item_exclude))
            return
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float):
            if not isfinite(item):
                _prompt_refuse(
                    "search_prompt_contains_nonfinite_number",
                    "protected candidate inputs must have finite JSON numbers",
                )
            return
        if isinstance(item, (datetime, date)):
            return
        if isinstance(item, Decimal):
            if not item.is_finite():
                _prompt_refuse(
                    "search_prompt_contains_nonfinite_number",
                    "protected candidate inputs must have finite JSON numbers",
                )
            return
        if isinstance(item, BaseModel):
            # Model fields are guarded by their transformed CoreSchema path so
            # caller selectors and exclude_if remain authoritative.
            return
        if is_dataclass(item) and not isinstance(item, type):

            def dataclass_values() -> None:
                for field in fields(item):
                    selected, child_include, child_exclude = _prompt_selected_child(
                        item_include,
                        item_exclude,
                        field.name,
                    )
                    if selected:
                        visit(getattr(item, field.name), child_include, child_exclude)

            enter(item, dataclass_values)
            return
        if isinstance(item, Iterator):
            _prompt_refuse(
                "search_prompt_one_shot_iterable_unsupported",
                "protected candidate inputs cannot safely preflight one-shot iterables",
            )
        if isinstance(item, (set, frozenset)):

            def set_values() -> None:
                for nested in item:
                    # Pydantic serializes sets as arrays and ignores index selectors.
                    visit(nested, None, None)

            enter(item, set_values)
            return
        if isinstance(item, Mapping):

            def mapping_values() -> None:
                for key, nested in item.items():
                    selected, child_include, child_exclude = _prompt_selected_child(
                        item_include,
                        item_exclude,
                        key,
                    )
                    if not selected:
                        continue
                    if not isinstance(key, str):
                        _prompt_refuse(
                            "search_prompt_contains_non_string_key",
                            "protected candidate inputs require string mapping keys",
                        )
                    visit(nested, child_include, child_exclude)

            enter(item, mapping_values)
            return
        if isinstance(item, (list, tuple)):

            def sequence_values() -> None:
                for index, nested in enumerate(item):
                    selected, child_include, child_exclude = _prompt_selected_child(
                        item_include,
                        item_exclude,
                        index,
                        sequence_length=len(item),
                    )
                    if selected:
                        visit(nested, child_include, child_exclude)

            enter(item, sequence_values)

    visit(value, include, exclude)


def _prompt_to_python(serializer: SchemaSerializer, value: Any, **kwargs: Any) -> Any:
    """Preserve the first typed refusal across nested Pydantic serializer calls."""
    pending = _PROMPT_TYPED_REFUSALS.get()
    owns_refusals = pending is None
    token = None
    if pending is None:
        pending = []
        token = _PROMPT_TYPED_REFUSALS.set(pending)

    try:
        try:
            if isinstance(value, BaseModel):
                result = _prompt_track_active_graph(
                    value,
                    lambda: serializer.to_python(value, **kwargs),
                )
            else:
                result = serializer.to_python(value, **kwargs)
        except SearchBudgetProducerUnsupportedError as exc:
            if not pending:
                pending.append(exc)
            result = None
        except PydanticSerializationError as exc:
            cause: BaseException | None = exc
            visited: set[int] = set()
            refusal: SearchBudgetProducerUnsupportedError | None = None
            while cause is not None and id(cause) not in visited:
                visited.add(id(cause))
                if isinstance(cause, SearchBudgetProducerUnsupportedError):
                    refusal = cause
                    break
                cause = cause.__cause__ or cause.__context__
            if not pending:
                pending.append(
                    refusal
                    or SearchBudgetProducerUnsupportedError(
                        "search_prompt_model_serialization_failed",
                        "the selected Pydantic serializer could not produce a supported prompt value",
                    )
                )
            result = None

        if owns_refusals and pending:
            raise pending[0]
        return result
    finally:
        if token is not None:
            _PROMPT_TYPED_REFUSALS.reset(token)


def _prompt_serialize_model(
    value: BaseModel,
    info: Any,
    model_type: type[BaseModel],
) -> Any:
    if not isinstance(value, model_type):
        _prompt_refuse(
            "search_prompt_model_schema_value_mismatch",
            "the selected model schema does not match the prompt value",
        )
    if (
        model_type.model_dump is not BaseModel.model_dump
        or type(value).model_dump is not BaseModel.model_dump
    ):
        _prompt_refuse(
            "search_prompt_custom_model_dump_not_interceptable",
            "custom model_dump overrides are outside the selected schema serializer path",
        )
    serializer = _prompt_compiled_serializer(model_type)
    result = _prompt_to_python(
        serializer,
        value,
        mode=info.mode,
        include=info.include,
        exclude=info.exclude,
        by_alias=info.by_alias,
        exclude_unset=info.exclude_unset,
        exclude_defaults=info.exclude_defaults,
        exclude_none=info.exclude_none,
        exclude_computed_fields=info.exclude_computed_fields,
        round_trip=info.round_trip,
        serialize_as_any=info.serialize_as_any,
        context=info.context,
    )
    _prompt_validate_raw_graph(result)
    return result


def _prompt_serialize_dynamic_model(value: BaseModel, info: Any) -> Any:
    return _prompt_serialize_model(value, info, type(value))


def _prompt_child_serialization_info(
    info: Any,
    include: Any,
    exclude: Any,
) -> Any:
    """Carry caller serializer options with one narrowed child selector."""
    return SimpleNamespace(
        mode=info.mode,
        include=include,
        exclude=exclude,
        by_alias=info.by_alias,
        exclude_unset=info.exclude_unset,
        exclude_defaults=info.exclude_defaults,
        exclude_none=info.exclude_none,
        exclude_computed_fields=info.exclude_computed_fields,
        round_trip=info.round_trip,
        serialize_as_any=info.serialize_as_any,
        context=info.context,
    )


def _prompt_prepare_any_value(
    value: Any,
    info: Any,
    include: Any,
    exclude: Any,
) -> Any:
    """Guard nested models using the caller's effective serializer projection."""
    if isinstance(value, BaseModel):
        child_info = _prompt_child_serialization_info(info, include, exclude)
        return _prompt_serialize_dynamic_model(value, child_info)
    if isinstance(value, Enum):
        return _prompt_track_active_graph(
            value,
            lambda: _prompt_prepare_any_value(value.value, info, include, exclude),
        )
    if is_dataclass(value) and not isinstance(value, type):

        def prepare_dataclass() -> Any:
            try:
                prepared = copy(value)
            except (TypeError, AttributeError) as exc:
                raise SearchBudgetProducerUnsupportedError(
                    "search_prompt_dataclass_projection_unavailable",
                    "the selected dataclass projection cannot be copied safely",
                ) from exc
            for field in fields(value):
                selected, child_include, child_exclude = _prompt_selected_child(
                    include,
                    exclude,
                    field.name,
                )
                if selected:
                    object.__setattr__(
                        prepared,
                        field.name,
                        _prompt_prepare_any_value(
                            getattr(value, field.name),
                            info,
                            child_include,
                            child_exclude,
                        ),
                    )
            return prepared

        return _prompt_track_active_graph(value, prepare_dataclass)
    if isinstance(value, Iterator):
        _prompt_refuse(
            "search_prompt_one_shot_iterable_unsupported",
            "protected candidate inputs cannot safely preflight one-shot iterables",
        )
    if isinstance(value, (set, frozenset)):

        def prepare_set() -> list[Any]:
            # The pinned Pydantic JSON projection emits a list and ignores selectors.
            return [_prompt_prepare_any_value(nested, info, None, None) for nested in value]

        return _prompt_track_active_graph(value, prepare_set)
    if isinstance(value, Mapping):

        def prepare_mapping() -> dict[Any, Any]:
            prepared: dict[Any, Any] = {}
            for key, nested in value.items():
                selected, child_include, child_exclude = _prompt_selected_child(
                    include,
                    exclude,
                    key,
                )
                if selected:
                    if not isinstance(key, str):
                        _prompt_refuse(
                            "search_prompt_contains_non_string_key",
                            "protected candidate inputs require string mapping keys",
                        )
                    prepared[key] = _prompt_prepare_any_value(
                        nested,
                        info,
                        child_include,
                        child_exclude,
                    )
                else:
                    prepared[key] = nested
            return prepared

        return _prompt_track_active_graph(value, prepare_mapping)
    if isinstance(value, (list, tuple)):

        def prepare_sequence() -> list[Any] | tuple[Any, ...]:
            prepared: list[Any] = []
            for index, nested in enumerate(value):
                selected, child_include, child_exclude = _prompt_selected_child(
                    include,
                    exclude,
                    index,
                    sequence_length=len(value),
                )
                prepared.append(
                    _prompt_prepare_any_value(
                        nested,
                        info,
                        child_include,
                        child_exclude,
                    )
                    if selected
                    else nested
                )
            return tuple(prepared) if isinstance(value, tuple) else prepared

        return _prompt_track_active_graph(value, prepare_sequence)
    _prompt_validate_raw_graph(value, include=include, exclude=exclude)
    return value


def _prompt_instrument_model_extras(schema: Any, *, untyped: bool) -> dict[str, Any]:
    """Guard a model's effective extra-field projection before JSON conversion."""

    def checked_extra(item: Any, handler: Any, info: Any) -> Any:
        if untyped:
            prepared = _prompt_prepare_any_value(
                item,
                info,
                info.include,
                info.exclude,
            )
        else:
            _prompt_validate_raw_graph(
                item,
                include=info.include,
                exclude=info.exclude,
            )
            prepared = item
        emitted = handler(prepared)
        _prompt_validate_raw_graph(emitted)
        return emitted

    return core_schema.any_schema(
        serialization=core_schema.wrap_serializer_function_ser_schema(
            _prompt_preserve_typed_refusal(checked_extra),
            info_arg=True,
            schema=schema,
            when_used="json",
        )
    )


def _prompt_instrument_serializer(schema: Any, parent_type: str | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        _prompt_refuse(
            "search_prompt_core_schema_unavailable",
            "the selected Pydantic CoreSchema serializer node is not inspectable",
        )
    serializer_type = schema.get("type")
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _PROMPT_OPAQUE_SCHEMA_KEYS:
            result[key] = value
        else:
            result[key] = _prompt_copy_schema_value(value)

    if serializer_type in _PROMPT_SERIALIZER_TYPES:
        source = schema["function"]
        if serializer_type == "function-plain":
            info_index = (
                (2 if schema.get("is_field_serializer", False) else 1)
                if schema.get("info_arg", False)
                else None
            )

            @wraps(source)
            def checked_plain(*args: Any, **kwargs: Any) -> Any:
                emitted = source(*args, **kwargs)
                info = (
                    args[info_index]
                    if info_index is not None and len(args) > info_index
                    else kwargs.get("info")
                )
                _prompt_validate_raw_graph(
                    emitted,
                    include=getattr(info, "include", None),
                    exclude=getattr(info, "exclude", None),
                )
                return emitted

            result["function"] = _prompt_preserve_typed_refusal(checked_plain)
        else:
            handler_index = 2 if schema.get("is_field_serializer", False) else 1
            info_index = handler_index + 1 if schema.get("info_arg", False) else None

            @wraps(source)
            def checked_wrap(*args: Any, **kwargs: Any) -> Any:
                mutable_args = list(args)
                if len(mutable_args) <= handler_index:
                    _prompt_refuse(
                        "search_prompt_core_schema_wrap_signature_unavailable",
                        "the selected Pydantic serializer callback signature is unknown",
                    )
                original_handler = mutable_args[handler_index]
                info = mutable_args[info_index] if info_index is not None else None

                @wraps(original_handler)
                def checked_handler(*handler_args: Any, **handler_kwargs: Any) -> Any:
                    if handler_args:
                        handler_value = handler_args[0]
                    else:
                        handler_value = handler_kwargs.get("input_value")
                    _prompt_validate_raw_graph(
                        handler_value,
                        include=getattr(info, "include", None),
                        exclude=getattr(info, "exclude", None),
                    )
                    if parent_type == "any" and info is not None:
                        emitted_inner = _prompt_prepare_any_value(
                            handler_value,
                            info,
                            info.include,
                            info.exclude,
                        )
                    else:
                        emitted_inner = original_handler(*handler_args, **handler_kwargs)
                    _prompt_validate_raw_graph(
                        emitted_inner,
                        include=getattr(info, "include", None),
                        exclude=getattr(info, "exclude", None),
                    )
                    return emitted_inner

                mutable_args[handler_index] = checked_handler
                emitted = source(*mutable_args, **kwargs)
                _prompt_validate_raw_graph(
                    emitted,
                    include=getattr(info, "include", None),
                    exclude=getattr(info, "exclude", None),
                )
                return emitted

            result["function"] = _prompt_preserve_typed_refusal(checked_wrap)

        if result.get("return_schema") is None:
            result["return_schema"] = _prompt_copy_schema_value(core_schema.any_schema())
    return result


def _prompt_instrument_model_field(value: Any) -> dict[str, Any]:
    """Guard one selected model field while retaining its actual serializer schema."""
    if not isinstance(value, dict):
        _prompt_refuse(
            "search_prompt_core_field_schema_unavailable",
            "the selected Pydantic model field is not inspectable",
        )
    result = {
        key: nested if key in _PROMPT_OPAQUE_SCHEMA_KEYS else _prompt_copy_schema_value(nested)
        for key, nested in value.items()
    }
    inner = result.get("schema")
    if not isinstance(inner, dict):
        _prompt_refuse(
            "search_prompt_core_field_schema_unavailable",
            "the selected Pydantic model field has no supported value schema",
        )

    def checked_field(item: Any, handler: Any, info: Any) -> Any:
        _prompt_validate_raw_graph(
            item,
            include=info.include,
            exclude=info.exclude,
        )
        emitted = handler(item)
        _prompt_validate_raw_graph(
            emitted,
            include=info.include,
            exclude=info.exclude,
        )
        return emitted

    result["schema"] = core_schema.any_schema(
        serialization=core_schema.wrap_serializer_function_ser_schema(
            _prompt_preserve_typed_refusal(checked_field),
            info_arg=True,
            schema=inner,
            when_used="json",
        )
    )
    return result


def _prompt_copy_schema_value(
    value: Any,
    *,
    root_model: bool = False,
    model_extra_allowed: bool = False,
) -> Any:
    schema_types = _prompt_core_schema_types()
    if isinstance(value, dict):
        node_type = value.get("type")
        if node_type == "definitions":
            return {
                key: (
                    _prompt_copy_schema_value(
                        nested,
                        root_model=root_model,
                        model_extra_allowed=model_extra_allowed,
                    )
                    if key == "schema"
                    else _prompt_copy_schema_value(nested)
                )
                for key, nested in value.items()
            }
        if node_type == "computed-field":
            result = {
                key: nested
                if key in _PROMPT_OPAQUE_SCHEMA_KEYS
                else _prompt_copy_schema_value(nested)
                for key, nested in value.items()
            }
            target = result["return_schema"]
            inner = _prompt_copy_schema_value(target)
            outer = _prompt_copy_schema_value(target)

            def checked_computed(item: Any, handler: Any, info: Any) -> Any:
                _prompt_validate_raw_graph(
                    item,
                    include=info.include,
                    exclude=info.exclude,
                )
                emitted = handler(item)
                _prompt_validate_raw_graph(
                    emitted,
                    include=info.include,
                    exclude=info.exclude,
                )
                return emitted

            outer["serialization"] = core_schema.wrap_serializer_function_ser_schema(
                _prompt_preserve_typed_refusal(checked_computed),
                info_arg=True,
                schema=inner,
                when_used="json",
            )
            result["return_schema"] = outer
            return result
        if node_type in schema_types:
            if node_type == "model-fields" and not isinstance(value.get("fields"), dict):
                _prompt_refuse(
                    "search_prompt_core_field_schema_unavailable",
                    "the selected Pydantic model field collection is not inspectable",
                )
            result: dict[str, Any] = {}
            if node_type == "model-fields":
                model_extra_allowed = model_extra_allowed or value.get("extra_behavior") == "allow"
            if node_type == "model":
                config = value.get("config")
                model_extra_allowed = value.get("extra_behavior") == "allow" or (
                    isinstance(config, Mapping) and config.get("extra_fields_behavior") == "allow"
                )
            for key, nested in value.items():
                if key in _PROMPT_OPAQUE_SCHEMA_KEYS:
                    result[key] = nested
                elif key == "fields" and node_type == "model-fields":
                    if not isinstance(nested, dict):
                        _prompt_refuse(
                            "search_prompt_core_field_schema_unavailable",
                            "the selected Pydantic model field collection is not inspectable",
                        )
                    result[key] = {
                        field_name: _prompt_instrument_model_field(field_schema)
                        for field_name, field_schema in nested.items()
                    }
                elif key == "serialization" and isinstance(nested, dict):
                    result[key] = _prompt_instrument_serializer(nested, node_type)
                elif key == "schema" and node_type == "model":
                    result[key] = _prompt_copy_schema_value(
                        nested,
                        model_extra_allowed=model_extra_allowed,
                    )
                elif key == "extras_schema" and node_type == "model-fields":
                    copied = _prompt_copy_schema_value(nested)
                    result[key] = (
                        _prompt_instrument_model_extras(copied, untyped=False)
                        if model_extra_allowed
                        else copied
                    )
                else:
                    result[key] = _prompt_copy_schema_value(nested)
            if (
                node_type == "model-fields"
                and model_extra_allowed
                and "extras_schema" not in result
            ):
                result["extras_schema"] = _prompt_instrument_model_extras(
                    core_schema.any_schema(),
                    untyped=True,
                )
            if (
                node_type == "model"
                and root_model
                and value.get("root_model") is True
                and not isinstance(value.get("serialization"), dict)
            ):
                declared_type = value.get("cls")
                if not isinstance(declared_type, type) or not issubclass(declared_type, BaseModel):
                    _prompt_refuse(
                        "search_prompt_core_model_type_unavailable",
                        "the selected root model has no supported Pydantic class",
                    )

                def checked_root_model(item: Any, handler: Any, info: Any) -> Any:
                    if not isinstance(item, declared_type):
                        _prompt_refuse(
                            "search_prompt_model_schema_value_mismatch",
                            "the selected root model schema does not match the prompt value",
                        )
                    if not hasattr(item, "root"):
                        _prompt_refuse(
                            "search_prompt_root_model_value_unavailable",
                            "the selected root model has no readable root value",
                        )

                    def serialize_root() -> Any:
                        _prompt_validate_raw_graph(
                            item.root,
                            include=info.include,
                            exclude=info.exclude,
                        )
                        emitted = handler(item)
                        _prompt_validate_raw_graph(
                            emitted,
                            include=info.include,
                            exclude=info.exclude,
                        )
                        return emitted

                    # _prompt_to_python owns this model's active-identity entry.
                    return serialize_root()

                result["serialization"] = core_schema.wrap_serializer_function_ser_schema(
                    _prompt_preserve_typed_refusal(checked_root_model),
                    info_arg=True,
                    when_used="json",
                )
            if node_type == "model" and not root_model:
                declared_type = value.get("cls")
                if not isinstance(declared_type, type) or not issubclass(declared_type, BaseModel):
                    _prompt_refuse(
                        "search_prompt_core_model_type_unavailable",
                        "the selected nested model has no supported Pydantic class",
                    )

                def checked_nested_model(item: Any, handler: Any, info: Any) -> Any:
                    del handler
                    if not isinstance(item, BaseModel):
                        _prompt_refuse(
                            "search_prompt_model_schema_value_mismatch",
                            "the selected model schema does not match the prompt value",
                        )
                    model_type = type(item) if info.serialize_as_any else declared_type
                    return _prompt_serialize_model(item, info, model_type)

                result["serialization"] = core_schema.wrap_serializer_function_ser_schema(
                    _prompt_preserve_typed_refusal(checked_nested_model),
                    info_arg=True,
                    when_used="json",
                )
            if node_type == "any" and not isinstance(value.get("serialization"), dict):
                inner = dict(result)

                def checked_any(item: Any, handler: Any, info: Any) -> Any:
                    if isinstance(item, BaseModel):
                        emitted = _prompt_serialize_dynamic_model(item, info)
                    else:
                        prepared = _prompt_prepare_any_value(
                            item,
                            info,
                            info.include,
                            info.exclude,
                        )
                        emitted = handler(prepared)
                    _prompt_validate_raw_graph(emitted)
                    return emitted

                result["serialization"] = core_schema.wrap_serializer_function_ser_schema(
                    _prompt_preserve_typed_refusal(checked_any),
                    info_arg=True,
                    schema=inner,
                    when_used="json",
                )
            return result
        return {
            key: nested if key in _PROMPT_OPAQUE_SCHEMA_KEYS else _prompt_copy_schema_value(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_prompt_copy_schema_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_prompt_copy_schema_value(item) for item in value)
    return value


def _prompt_compiled_serializer(model_type: type[BaseModel]) -> SchemaSerializer:
    schema = model_type.__pydantic_core_schema__
    with _PROMPT_SERIALIZER_CACHE_LOCK:
        cached = _PROMPT_SERIALIZER_CACHE.get(model_type)
        if cached is not None and cached[0] is schema:
            return cached[1]
        transformed = _prompt_copy_schema_value(schema, root_model=True)
        config = transformed.get("config") if isinstance(transformed, dict) else None
        serializer = SchemaSerializer(transformed, config=config)
        _PROMPT_SERIALIZER_CACHE[model_type] = (schema, serializer)
        return serializer


def _search_prompt_value(value: Any) -> Any:
    """Convert supported search inputs to JSON without dropping unknown values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise SearchBudgetProducerUnsupportedError(
                "search_prompt_contains_nonfinite_number",
                "protected candidate inputs must have finite JSON numbers",
            )
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise SearchBudgetProducerUnsupportedError(
                "search_prompt_contains_nonfinite_number",
                "protected candidate inputs must have finite decimal values",
            )
        return str(value)
    if isinstance(value, Enum):
        return _search_prompt_value(value.value)
    if isinstance(value, BaseModel):
        if type(value).model_dump is not BaseModel.model_dump:
            _prompt_refuse(
                "search_prompt_custom_model_dump_not_interceptable",
                "custom model_dump overrides are outside the selected schema serializer path",
            )
        _prompt_validate_raw_graph(value)
        emitted = _prompt_to_python(
            _prompt_compiled_serializer(type(value)),
            value,
            mode="json",
            exclude_none=False,
            serialize_as_any=False,
        )
        _prompt_validate_raw_graph(emitted)
        return _search_prompt_value(emitted)
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SearchBudgetProducerUnsupportedError(
                    "search_prompt_contains_non_string_key",
                    "protected candidate inputs require string mapping keys",
                )
            converted[key] = _search_prompt_value(item)
        return converted
    if isinstance(value, (list, tuple)):
        return [_search_prompt_value(item) for item in value]
    raise SearchBudgetProducerUnsupportedError(
        "search_prompt_contains_unsupported_value",
        f"candidate input type {type(value).__name__} has no declared JSON projection",
    )


def _search_prompt_objective_detail(value: Any) -> dict[str, Any]:
    """Project one declared search objective detail without admitting other dataclasses."""
    if type(value) is not ObjectiveValue:
        _prompt_refuse(
            "search_prompt_contains_unsupported_value",
            f"candidate input type {type(value).__name__} has no declared JSON projection",
        )
    return {
        objective_field.name: getattr(value, objective_field.name)
        for objective_field in fields(value)
    }


def _search_prompt_history(history: list[SearchIteration]) -> list[dict[str, Any]]:
    """Project the controller-owned history contract for a traced prompt."""
    if not isinstance(history, list):
        _prompt_refuse(
            "search_prompt_history_projection_unavailable",
            "protected search history must use the declared list representation",
        )
    _prompt_validate_raw_graph(history)
    projected: list[dict[str, Any]] = []
    for iteration in history:
        if type(iteration) is not SearchIteration:
            _prompt_refuse(
                "search_prompt_contains_unsupported_value",
                f"candidate input type {type(iteration).__name__} has no declared JSON projection",
            )
        record: dict[str, Any] = {}
        for record_field in fields(iteration):
            value = getattr(iteration, record_field.name)
            if record_field.name == "objective_details":
                if not isinstance(value, list):
                    _prompt_refuse(
                        "search_prompt_history_projection_unavailable",
                        "SearchIteration objective_details must retain its declared list shape",
                    )
                record[record_field.name] = [
                    _search_prompt_objective_detail(detail) for detail in value
                ]
            else:
                record[record_field.name] = value
        projected.append(record)
    return projected


@dataclass(frozen=True)
class TracedLLMCandidateGenerator:
    """Generate one JSON candidate through an exact, durably settled LLM client.

    The owner-bound candidate-generation path uses this concrete adapter to
    verify the selected ``TracedLLMClient`` and exact budget owner before callbacks.
    Other candidate generators remain supported for unprotected search only.
    This adapter accounts for candidate generation; arbitrary evaluator callbacks
    do not acquire an owner contract through it.
    """

    client: TracedLLMClient
    system_prompt: str

    def __post_init__(self) -> None:
        if not isinstance(self.system_prompt, str) or not self.system_prompt.strip():
            raise ValueError("system_prompt must be a non-empty string")

    @staticmethod
    def require_bound_owner(
        generator: CandidateGenerator,
        store: BudgetMiddleware,
        binding: BudgetLedgerProducerRunBinding,
    ) -> None:
        """Verify the selected traced client, durable owner, key, and run binding."""
        from polisyos.core.llm import TracedLLMClient
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
        )
        from polisyos.scientist.orchestration.engine.budget_middleware import (
            BudgetMiddleware,
        )

        if type(generator) is not TracedLLMCandidateGenerator:
            raise SearchBudgetProducerUnsupportedError(
                "budgeted_search_requires_traced_candidate_generator",
                "an arbitrary generator callback cannot prove which producer client it uses",
            )
        if type(generator.client) is not TracedLLMClient:
            raise SearchBudgetProducerUnsupportedError(
                "selected_traced_client_type_unproven",
                "protected search requires the exact TracedLLMClient implementation",
            )
        if (
            type(store) is not BudgetMiddleware
            or type(binding) is not BudgetLedgerProducerRunBinding
        ):
            raise SearchBudgetProducerUnsupportedError(
                "selected_traced_client_owner_or_run_mismatch",
                "protected search requires the selected middleware and typed run binding",
            )
        expected_key = f"nl-run:{binding.run_id}"
        if (
            generator.client._producer_settlement_store is not store
            or generator.client._producer_budget_key != expected_key
        ):
            raise SearchBudgetProducerUnsupportedError(
                "selected_traced_client_owner_or_run_mismatch",
                "the selected traced client must use the same owner and run budget key",
            )
        try:
            owner_identity = store.settlement_owner_identity
            state = store.budget_state
            limit = state.limits.get(expected_key)
        except Exception as exc:
            raise SearchBudgetProducerUnsupportedError(
                "selected_budget_owner_not_durable",
                "the selected owner does not expose a readable durable settlement identity",
            ) from exc
        if (
            type(owner_identity) is not tuple
            or len(owner_identity) != 3
            or any(not isinstance(part, str) or not part.strip() for part in owner_identity)
            or limit is None
            or limit.max_usd <= 0
        ):
            raise SearchBudgetProducerUnsupportedError(
                "selected_budget_owner_or_limit_not_established",
                "the selected owner identity and positive run limit must already exist",
            )

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Request one candidate and require a JSON object response."""
        from polisyos.core.llm import extract_llm_response_data

        request = {
            "history": _search_prompt_history(history),
            "current_best": current_best,
            "context": context,
        }
        payload = json.dumps(
            _search_prompt_value(request),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        user_prompt = f"Search inputs JSON:\n{payload}"
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise SearchBudgetProducerUnsupportedError(
                "traced_candidate_generator_requires_sync_search_driver",
                "the synchronous search controller cannot own an already-running event loop",
            )
        response = asyncio.run(
            self.client.generate(
                system=self.system_prompt.strip(),
                user=user_prompt,
                response_format={"type": "json_object"},
            )
        )
        response_data = extract_llm_response_data(
            response,
            cache_reuse_owner=self.client._cache_reuse_owner,
        )
        try:
            candidate = json.loads(response_data.content)
        except (TypeError, ValueError) as exc:
            raise SearchBudgetProducerUnsupportedError(
                "traced_candidate_response_is_not_json",
                "the selected traced provider must return one JSON candidate object",
            ) from exc
        if not isinstance(candidate, dict) or not candidate:
            raise SearchBudgetProducerUnsupportedError(
                "traced_candidate_response_is_not_object",
                "the selected traced provider must return a non-empty JSON object",
            )
        validated_candidate = _search_prompt_value(candidate)
        if not isinstance(validated_candidate, dict):
            raise SearchBudgetProducerUnsupportedError(
                "traced_candidate_response_is_not_object",
                "the selected traced provider must return a JSON object",
            )
        return validated_candidate


class BatchCandidateGenerator(CandidateGenerator, Protocol):
    """Generate a batch of candidate proposals for parallel Stage B evaluation."""

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        """Generate multiple candidates for parallel Stage B evaluation."""


@dataclass(frozen=True)
class SearchEvaluatorPorts:
    """Bundle evaluator callables so controller construction does not sprawl."""

    stage_a: StageAEvaluator
    stage_b: StageBEvaluator


@dataclass
class SearchConfig:
    """Configure candidate generation, objective evaluation, stopping, and warm start."""

    stopping: StoppingCriterion
    objective: CompositeObjective
    max_iterations_hard_limit: int = 100
    enable_stage_a: bool = True
    log_level: str = "INFO"
    batch_size: int = 1
    resource_arbiter: Any | None = None
    transfer_manager: TransferLearningManager | None = None
    initial_evaluations: list[dict[str, Any]] = field(default_factory=list)
    policy_objective_stack: ObjectiveStack | None = None
    pareto_registry: ParetoRegistry | None = None
    pareto_objective_basis_by_view: dict[str, ParetoBasisScope] = field(default_factory=dict)
    max_empty_generation_attempts: int = 3
    producer_settlement_store: BudgetMiddleware | None = None
    producer_run_binding: BudgetLedgerProducerRunBinding | None = None

    def __post_init__(self) -> None:
        """Validate controller bounds and freeze owner and Pareto contracts."""
        if any(
            not isinstance(basis, ParetoBasisScope)
            for basis in self.pareto_objective_basis_by_view.values()
        ):
            raise TypeError("pareto_objective_basis_by_view values must be ParetoBasisScope")
        self.pareto_objective_basis_by_view = deepcopy(self.pareto_objective_basis_by_view)
        if self.max_iterations_hard_limit < 1:
            raise ValueError("max_iterations_hard_limit must be >= 1")
        if self.max_empty_generation_attempts < 1:
            raise ValueError("max_empty_generation_attempts must be >= 1")
        if (self.producer_settlement_store is None) != (self.producer_run_binding is None):
            raise ValueError("durable producer budget requires both store and run binding")
        if self.producer_run_binding is not None:
            from polisyos.scientist.orchestration.engine.budget_ledger import (
                BudgetLedgerProducerRunBinding,
            )
            from polisyos.scientist.orchestration.engine.budget_middleware import (
                BudgetMiddleware,
            )

            if type(self.producer_run_binding) is not BudgetLedgerProducerRunBinding:
                raise TypeError("producer_run_binding must be a server-issued typed binding")
            if type(self.producer_settlement_store) is not BudgetMiddleware:
                raise TypeError("producer_settlement_store must be BudgetMiddleware")
            required_operations = (
                "list_producer_events_for_run_safe",
                "producer_run_binding_scope",
            )
            if any(
                not callable(getattr(self.producer_settlement_store, item, None))
                for item in required_operations
            ):
                raise TypeError("producer settlement owner contract is incomplete")
            if not isinstance(self.stopping, _OwnerBudgetStopping):
                self.stopping = _OwnerBudgetStopping(self.stopping)


class SearchController:
    """Coordinate a legacy ask/evaluate loop over one Stage A and one Stage B evaluator.

    Candidate generation is delegated to `CandidateGenerator`, evaluator feedback
    is captured in `SearchIteration`, optional transfer/Pareto/diversity state is
    injected into generation context, and stopping criteria terminate the loop.
    `run()` is intentionally non-reentrant; overlapping calls on one controller
    raise a deterministic `RuntimeError` before replacing run state.
    """

    def __init__(
        self,
        config: SearchConfig,
        candidate_generator: CandidateGenerator,
        stage_a_evaluator: StageAEvaluator | None = None,
        stage_b_evaluator: StageBEvaluator | None = None,
        *,
        evaluators: SearchEvaluatorPorts | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._config = config
        self._generator = candidate_generator
        if config.producer_settlement_store is not None:
            assert config.producer_run_binding is not None
            TracedLLMCandidateGenerator.require_bound_owner(
                candidate_generator,
                config.producer_settlement_store,
                config.producer_run_binding,
            )
        if evaluators is not None:
            if stage_a_evaluator is not None or stage_b_evaluator is not None:
                raise ValueError(
                    "Pass either SearchEvaluatorPorts or legacy evaluator arguments, not both"
                )
            stage_a_evaluator = evaluators.stage_a
            stage_b_evaluator = evaluators.stage_b
        if stage_a_evaluator is None or stage_b_evaluator is None:
            raise ValueError("SearchController requires Stage A and Stage B evaluators")
        self._stage_a = stage_a_evaluator
        self._stage_b = stage_b_evaluator

        self._run_lock = Lock()
        self._run_state = SearchRunState(status=SearchStatus.NOT_STARTED)
        self._source_budget_snapshot: dict[str, Any] = {"status": "not_configured"}
        self._metrics = metrics if metrics is not None else _default_metrics()
        self._diversity_enabled = _as_bool(
            os.getenv("POLISYOS_SEARCH_DIVERSITY_ENABLED"),
            default=False,
        )
        self._diversity_tracker = None
        self._reset_diversity_tracker(operation="initialize_diversity_tracker")

    def _reset_diversity_tracker(self, *, operation: str) -> None:
        """Allocate fresh optional diversity telemetry for one lifecycle."""
        if not self._diversity_enabled:
            self._diversity_tracker = None
            return
        try:
            from polisyos.scientist.methods.search.diversity import DiversityTracker
        except _IMPORT_ERRORS as exc:
            _search_degraded(
                operation=operation,
                reason="optional_dependency_unavailable",
                exc=exc,
            )
            self._diversity_enabled = False
            self._diversity_tracker = None
        else:
            self._diversity_tracker = DiversityTracker()

    @property
    def _history(self) -> list[SearchIteration]:
        """Compatibility view onto the current run-state history."""
        return self._run_state.history

    @_history.setter
    def _history(self, value: list[SearchIteration]) -> None:
        self._run_state.history = value

    @property
    def _best_candidate(self) -> dict[str, Any] | None:
        """Compatibility view onto the current run-state champion."""
        return self._run_state.best_candidate

    @_best_candidate.setter
    def _best_candidate(self, value: dict[str, Any] | None) -> None:
        self._run_state.best_candidate = value

    @property
    def _best_objective(self) -> float:
        """Compatibility view onto the current run-state objective."""
        return self._run_state.best_objective

    @_best_objective.setter
    def _best_objective(self, value: float) -> None:
        self._run_state.best_objective = value

    @property
    def _status(self) -> SearchStatus:
        """Compatibility view onto the current run-state status."""
        return cast("SearchStatus", self._run_state.status)

    @_status.setter
    def _status(self, value: SearchStatus) -> None:
        self._run_state.status = value

    @property
    def _search_id(self) -> str:
        """Compatibility view onto the current run identity."""
        return self._run_state.search_id

    @_search_id.setter
    def _search_id(self, value: str) -> None:
        self._run_state.search_id = value

    @property
    def _pareto_front(self) -> list[dict[str, Any]]:
        """Compatibility view onto the current run frontier."""
        return self._run_state.pareto_front

    @_pareto_front.setter
    def _pareto_front(self, value: list[dict[str, Any]]) -> None:
        self._run_state.pareto_front = value

    @property
    def _pareto_points(self) -> list[FrontierPoint]:
        """Compatibility view onto the current run frontier points."""
        return self._run_state.pareto_points

    @_pareto_points.setter
    def _pareto_points(self, value: list[FrontierPoint]) -> None:
        self._run_state.pareto_points = value

    @property
    def _stage_a_count(self) -> int:
        """Compatibility view onto Stage A evaluation count."""
        return self._run_state.stage_a_evaluations

    @_stage_a_count.setter
    def _stage_a_count(self, value: int) -> None:
        self._run_state.stage_a_evaluations = value

    @property
    def _stage_b_count(self) -> int:
        """Compatibility view onto Stage B evaluation count."""
        return self._run_state.stage_b_evaluations

    @_stage_b_count.setter
    def _stage_b_count(self, value: int) -> None:
        self._run_state.stage_b_evaluations = value

    @property
    def _sentinel_evaluations(self) -> int:
        """Compatibility view onto sentinel evaluation count."""
        return self._run_state.sentinel_evaluations

    @_sentinel_evaluations.setter
    def _sentinel_evaluations(self, value: int) -> None:
        self._run_state.sentinel_evaluations = value

    def _prepare_service_run(self) -> None:
        """Ensure the ask/tell bridge has one explicit run-state owner.

        The compatibility ``run()`` path always starts a fresh state.  The
        contract adapter, however, may receive several ask/tell transitions
        before a full loop is invoked.  This small owner operation gives that
        path a stable search identity and makes a later ask an explicit
        continuation of the same state rather than an accidental new ledger.
        """
        if self._run_state.status in {None, SearchStatus.NOT_STARTED}:
            self._run_state = SearchRunState(
                search_id=str(uuid4())[:8],
                status=SearchStatus.RUNNING,
            )
            self._config.stopping.reset()
            self._reset_diversity_tracker(operation="prepare_service_run")
            return
        if self._run_state.status is not SearchStatus.RUNNING:
            self._run_state.status = SearchStatus.RUNNING

    def _accept_tell(
        self,
        *,
        candidate: CandidatePayload,
        objective_value: float,
        objective_details: list[Any],
        is_promising: bool,
        stage_a_passed: bool,
        stage_b_result: dict[str, Any],
        duration_seconds: float,
    ) -> SearchIteration:
        """Accept one ask/tell result through the controller-owned transition.

        This is an internal bridge for ``LegacySearchServiceAdapter``.  It
        reuses the typed-evaluation resolver and frontier owner from the full
        controller loop, preserving the distinction between absent and
        malformed typed results (B123) without exposing private fields to the
        adapter.
        """
        self._prepare_service_run()
        policy_resolution = self._resolve_policy_evaluation_with_status(
            candidate,
            stage_b_result,
        )
        policy_evaluation = policy_resolution.value
        effective_objective = float(objective_value)
        effective_details: list[ObjectiveValue] = [
            detail for detail in objective_details if isinstance(detail, ObjectiveValue)
        ]
        if policy_resolution.status == "invalid":
            self._run_state.policy_evaluation_errors += 1
            effective_objective = float("inf")
            effective_details = []
        elif policy_evaluation is not None:
            effective_objective = policy_evaluation.legacy_scalar_proxy
            effective_details = policy_evaluation.as_legacy_objectives()

        is_sentinel = extract_sentinel_metadata(candidate) is not None
        feedback = stage_b_result.get("feedback")
        verdict = feedback.get("verdict") if isinstance(feedback, dict) else None
        accepted = (
            bool(is_promising)
            and bool(stage_a_passed)
            and policy_resolution.status != "invalid"
            and (policy_evaluation is None or policy_evaluation.feasible)
            and verdict == "APPROVE"
        )
        if stage_a_passed and not is_sentinel and policy_resolution.status != "invalid":
            if effective_objective < self._best_objective:
                self._best_objective = effective_objective
                self._best_candidate = deepcopy(candidate)
            if effective_details:
                self._update_policy_or_legacy_frontier(
                    candidate=candidate,
                    objective_details=effective_details,
                    policy_evaluation=policy_evaluation,
                    stage_b_result=stage_b_result,
                )

        record = SearchIteration(
            iteration=self._run_state.evaluation_iterations,
            candidate=deepcopy(candidate),
            objective_value=effective_objective,
            objective_details=deepcopy(effective_details),
            is_promising=accepted,
            stage_a_passed=bool(stage_a_passed),
            stage_b_result=deepcopy(stage_b_result),
            duration_seconds=float(duration_seconds),
            policy_evaluation=deepcopy(policy_evaluation),
            policy_evaluation_status=policy_resolution.status,
            policy_evaluation_error=policy_resolution.reason,
        )
        transition = _EvaluationTransition(
            disposition=(
                _EvaluationDisposition.SENTINEL if is_sentinel else _EvaluationDisposition.ORDINARY
            ),
            record=record,
        )
        self._run_state.apply_tell_transition(
            transition,
            stage_a_evaluated=self._config.enable_stage_a,
            stage_b_evaluated=stage_a_passed,
        )
        return record

    def _service_tell_snapshot(self) -> dict[str, Any]:
        """Return detached state feedback for the ask/tell compatibility bridge."""
        snapshot = self._run_state.snapshot()
        return {
            "best_candidate": deepcopy(snapshot.best_candidate),
            "best_objective": (
                None if snapshot.best_objective == float("inf") else float(snapshot.best_objective)
            ),
            "history_length": snapshot.history_size,
            "registry_update": {"search_id": snapshot.search_id},
            "lesson_cards": [],
            "frontier_delta": deepcopy(snapshot.pareto_front),
            "pareto_projection": snapshot.pareto_projection,
        }

    def _begin_native_run(self, initial_context: dict[str, Any]) -> datetime:
        """Initialize one native service run and seed its warm history."""
        start_time = datetime.now(UTC)
        search_id = str(uuid4())[:8]
        self._reset_diversity_tracker(operation="reset_diversity_tracker")
        self._run_state = SearchRunState(
            search_id=search_id,
            status=SearchStatus.RUNNING,
        )
        self._config.stopping.reset()
        self._refresh_budget_snapshot(initial_context)
        self._run_state.training_evaluations = len(self._config.initial_evaluations)

        for eval_dict in self._config.initial_evaluations:
            obj_value = eval_dict.get("objective_value", float("inf"))
            record = SearchIteration(
                iteration=-1,
                candidate=deepcopy(eval_dict.get("candidate", {})),
                objective_value=obj_value,
                objective_details=[],
                is_promising=eval_dict.get("is_promising", False),
                stage_a_passed=True,
                stage_b_result=deepcopy(eval_dict.get("stage_b_result")),
                duration_seconds=0.0,
            )
            self._history.append(record)
            if obj_value < self._best_objective:
                self._best_objective = obj_value
                self._best_candidate = deepcopy(record.candidate)

        logger.info(f"Starting search {search_id}")
        return start_time

    def _finish_native_run(
        self,
        *,
        start_time: datetime,
        stopping_reason: str | None,
    ) -> SearchResult:
        """Build a detached result from the controller-owned run state."""
        if self._status == SearchStatus.RUNNING:
            self._status = SearchStatus.STOPPED
            stopping_reason = (
                f"Hard iteration limit ({self._config.max_iterations_hard_limit}) reached"
            )

        total_duration = (datetime.now(UTC) - start_time).total_seconds()
        snapshot = self._run_state.snapshot()
        telemetry: dict[str, Any] = {
            "history_size": snapshot.history_size,
            "training_evaluations": snapshot.training_evaluations,
            "new_evaluations": snapshot.new_evaluations,
            "evaluation_count": snapshot.evaluation_count,
            "scientific_evaluations": snapshot.scientific_evaluations,
            "sentinel_evaluations": snapshot.sentinel_evaluations,
            "policy_evaluation_errors": snapshot.policy_evaluation_errors,
            "budget_required": bool(self._config.stopping.state_keys()),
            "budget_available": snapshot.budget_available,
            "budget_snapshot": deepcopy(snapshot.budget_snapshot),
            "budget_spent": (snapshot.budget_spent if snapshot.budget_available else None),
        }
        source_budget = self._source_budget_telemetry()
        if source_budget is not None:
            telemetry["producer_budget_owner"] = source_budget
        if self._diversity_tracker is not None:
            telemetry["diversity_unique_mechanisms_total"] = (
                self._diversity_tracker.unique_mechanisms_total
            )
            telemetry["diversity_ratio"] = self._diversity_tracker.diversity_ratio
        transition_payload = snapshot.generation_transition_payload()
        if transition_payload is not None:
            telemetry["generation_transition"] = transition_payload

        return SearchResult(
            search_id=snapshot.search_id,
            status=cast("SearchStatus", snapshot.status),
            best_candidate=deepcopy(snapshot.best_candidate),
            best_objective=snapshot.best_objective,
            iterations_completed=snapshot.evaluation_iterations,
            history=deepcopy(snapshot.history),
            stopping_reason=stopping_reason,
            total_duration_seconds=total_duration,
            stage_a_evaluations=snapshot.stage_a_evaluations,
            stage_b_evaluations=snapshot.stage_b_evaluations,
            pareto_front=deepcopy(snapshot.pareto_front),
            pareto_projection=snapshot.pareto_projection,
            telemetry=deepcopy(telemetry),
        )

    def run(
        self,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Execute the native ask/tell driver through the compatibility entrypoint."""
        from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver

        driver = _NativeSearchServiceDriver(self)
        if self._config.producer_settlement_store is None:
            return driver.run_search(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )
        assert self._config.producer_run_binding is not None
        with self._config.producer_settlement_store.producer_run_binding_scope(
            self._config.producer_run_binding
        ):
            return driver.run_search(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )

    def _stopping_state(self) -> dict[str, Any]:
        """Build stopping input from run counters and declared budget owners."""
        state = {
            "iteration": self._run_state.evaluation_iterations,
            "evaluation_iterations": self._run_state.evaluation_iterations,
            "generation_attempts": self._run_state.generation_attempts,
            "empty_generation_attempts": self._run_state.empty_generation_attempts,
            "best_objective": self._best_objective,
            "budget_spent": self._run_state.budget_spent,
        }
        state.update(self._run_state.budget_snapshot)
        if self._source_budget_snapshot.get("status") == "resolved":
            state["_source_budget_remaining_usd"] = self._source_budget_snapshot["remaining"]
        return state

    def _refresh_budget_snapshot(self, context: dict[str, Any]) -> None:
        """Capture one detached snapshot from the declared budget owner.

        The controller never forwards the mutable evaluator context directly to
        stopping criteria.  Only keys explicitly requested by the criterion are
        copied into the run-owned snapshot, so both stopping checkpoints and the
        final report observe the same owner contract without creating a ledger.
        """
        required_keys = self._config.stopping.state_keys()
        source_budget_key = "_source_budget_remaining_usd"
        context_required_keys = tuple(key for key in required_keys if key != source_budget_key)
        snapshot: dict[str, float] = {}
        for key in context_required_keys:
            if self._config.producer_settlement_store is not None and key == "cumulative_cost_usd":
                continue
            value = context.get(key)
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                numeric_value = float(value)
                if isfinite(numeric_value):
                    snapshot[key] = numeric_value

        if self._config.producer_settlement_store is not None:
            self._source_budget_snapshot = self._read_source_budget_snapshot()
            if self._source_budget_snapshot.get("status") == "resolved":
                source_spent = self._source_budget_snapshot["spent"]
                if "cumulative_cost_usd" in required_keys:
                    snapshot["cumulative_cost_usd"] = float(source_spent)
                self._run_state.budget_spent = float(source_spent)
        else:
            self._source_budget_snapshot = {"status": "not_configured"}
        self._run_state.budget_snapshot = snapshot
        context_available = all(key in snapshot for key in context_required_keys)
        source_available = (
            self._config.producer_settlement_store is None
            or self._source_budget_snapshot.get("status") == "resolved"
        )
        self._run_state.budget_available = (
            bool(required_keys) and context_available and source_available
        )
        if self._config.producer_settlement_store is not None:
            pass
        elif "cumulative_cost_usd" in snapshot:
            self._run_state.budget_spent = snapshot["cumulative_cost_usd"]
        elif snapshot:
            self._run_state.budget_spent = next(iter(snapshot.values()))
        else:
            self._run_state.budget_spent = 0.0

    def _read_source_budget_snapshot(self) -> dict[str, Any]:
        """Read one owner, typed run scope, exact producer events, and remaining budget."""
        store = self._config.producer_settlement_store
        binding = self._config.producer_run_binding
        if store is None or binding is None:
            return {"status": "not_configured"}

        owner_identity: tuple[str, str, str] | None = None
        try:
            from polisyos.scientist.orchestration.engine.budget import BudgetState

            owner_identity = store.settlement_owner_identity
            if (
                type(owner_identity) is not tuple
                or len(owner_identity) != 3
                or any(not isinstance(value, str) or not value.strip() for value in owner_identity)
            ):
                raise ValueError("settlement_owner_identity_not_established")
            budget_state = store.budget_state
            if type(budget_state) is not BudgetState:
                raise TypeError("budget_owner_returned_untyped_state")
            budget_key = f"nl-run:{binding.run_id}"
            limit = budget_state.limits.get(budget_key)
            if limit is None or limit.max_usd <= 0:
                raise ValueError("run_budget_limit_not_established")
            records = store.list_producer_events_for_run_safe(binding)
            event_status_counts: dict[str, int] = {}
            settled = Decimal(0)
            for record in records:
                event_status_counts[record.status] = event_status_counts.get(record.status, 0) + 1
                if record.run_binding != binding or record.key != budget_key:
                    raise ValueError("producer_event_scope_mismatch")
                if record.status != "committed" or record.amount is None:
                    raise ValueError("producer_event_settlement_unresolved")
                settled += record.amount
            spent = budget_state.spent.get(budget_key, Decimal(0))
            reserved = budget_state.reserved.get(budget_key, Decimal(0))
            if spent != settled:
                raise ValueError("producer_settlement_spend_disagrees_with_budget_owner")
            if (
                self._run_state.generation_attempts > 0 or self._run_state.evaluation_iterations > 0
            ) and not records:
                raise ValueError("producer_event_missing_after_search_work")
            remaining = limit.max_usd - spent - reserved
            return {
                "status": "resolved",
                "owner_identity": owner_identity,
                "run_binding": binding.model_dump(mode="json"),
                "budget_key": budget_key,
                "limit": limit.max_usd,
                "spent": spent,
                "reserved": reserved,
                "remaining": remaining,
                "event_count": len(records),
                "event_status_counts": event_status_counts,
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "owner_identity": owner_identity,
                "run_binding": binding.model_dump(mode="json"),
                "reason_code": f"source_budget_{type(exc).__name__.lower()}",
            }

    def _source_budget_telemetry(self) -> dict[str, Any] | None:
        """Project source-bound accounting values without exposing event payloads."""
        snapshot = self._source_budget_snapshot
        if snapshot.get("status") == "not_configured":
            return None
        payload = dict(snapshot)
        for key in ("limit", "spent", "reserved", "remaining"):
            value = payload.get(key)
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload

    def _generate_candidates(
        self,
        iteration: int,
        initial_candidate: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if iteration == 0 and initial_candidate is not None:
            return [initial_candidate]

        effective_context = context
        if self._diversity_enabled:
            try:
                from polisyos.scientist.methods.search.diversity import (
                    enrich_context_with_diversity,
                )
            except _IMPORT_ERRORS as exc:
                _search_degraded(
                    operation="enrich_diversity_context",
                    reason="optional_dependency_unavailable",
                    exc=exc,
                    details={"iteration": iteration},
                )
                effective_context = context
            else:
                try:
                    effective_context = enrich_context_with_diversity(context, self._history)
                except _SEARCH_DEGRADED_ERRORS as exc:
                    _search_degraded(
                        operation="enrich_diversity_context",
                        reason="diversity_context_failed",
                        exc=exc,
                        details={"iteration": iteration},
                    )
                    effective_context = context
        effective_context = self._build_generation_context(effective_context, iteration=iteration)

        # Adaptive batch sizing based on evaluation cost
        batch_size = max(1, int(self._config.batch_size))
        if self._history:
            durations = [h.duration_seconds for h in self._history if h.duration_seconds > 0]
            if durations:
                avg_duration = sum(durations) / len(durations)
                if avg_duration < 1.0:
                    batch_size = min(batch_size * 2, 16)
                elif avg_duration > 30.0:
                    batch_size = max(1, batch_size // 2)
        generate_batch = None
        if hasattr(self._generator, "generate_batch"):
            generate_batch = self._generator.generate_batch
        if batch_size > 1 and callable(generate_batch):
            return generate_batch(
                self._history,
                self._best_candidate,
                effective_context,
                batch_size,
            )
        return [
            self._generator.generate(
                self._history,
                self._best_candidate,
                effective_context,
            )
        ]

    def _evaluate_candidate(
        self,
        candidate: dict[str, Any],
        iteration: int,
        context: dict[str, Any],
    ) -> _EvaluationTransition:
        candidate = deepcopy(candidate)
        iter_start = datetime.now(UTC)
        is_sentinel = extract_sentinel_metadata(candidate) is not None

        stage_a_passed = True
        stage_a_score = 0.0

        if self._config.enable_stage_a:
            self._stage_a_count += 1
            stage_a_score, stage_a_passed = self._stage_a(candidate, context)
            if not stage_a_passed:
                logger.debug(f"Iteration {iteration}: Stage A rejected (score={stage_a_score:.4f})")

        stage_b_result: dict[str, Any] | None = None
        objective_value = float("inf")
        objective_details: list[ObjectiveValue] = []
        policy_evaluation = None
        policy_resolution = _PolicyEvaluationResolution(value=None, status="missing")
        iter_duration = 0.0

        if stage_a_passed:
            self._stage_b_count += 1
            arbiter = self._config.resource_arbiter
            if arbiter is not None:
                with arbiter.acquire("jax"):
                    stage_b_result = self._stage_b(candidate, context)
            else:
                stage_b_result = self._stage_b(candidate, context)

            sim_results = stage_b_result.get("simulation_results", {})
            policy_resolution = self._resolve_policy_evaluation_with_status(
                candidate,
                stage_b_result,
            )
            policy_evaluation = policy_resolution.value
            if policy_resolution.status == "invalid":
                self._run_state.policy_evaluation_errors += 1
            elif policy_evaluation is not None:
                objective_value = policy_evaluation.legacy_scalar_proxy
                objective_details = policy_evaluation.as_legacy_objectives()
            else:
                obj_eval = self._config.objective.evaluate(sim_results)
                objective_value = obj_eval.raw_value
                objective_details = self._config.objective.evaluate_detailed(sim_results)

            if (
                policy_resolution.status != "invalid"
                and not is_sentinel
                and objective_value < self._best_objective
            ):
                self._best_objective = objective_value
                self._best_candidate = deepcopy(candidate)
                logger.info(f"Iteration {iteration}: New best objective = {objective_value:.6f}")

            if not is_sentinel and policy_resolution.status != "invalid":
                self._update_policy_or_legacy_frontier(
                    candidate=candidate,
                    objective_details=objective_details,
                    policy_evaluation=policy_evaluation,
                    stage_b_result=stage_b_result,
                )

        iter_duration = (datetime.now(UTC) - iter_start).total_seconds()
        record = SearchIteration(
            iteration=iteration,
            candidate=deepcopy(candidate),
            objective_value=objective_value,
            objective_details=deepcopy(objective_details),
            is_promising=stage_a_passed
            and policy_resolution.status != "invalid"
            and (policy_evaluation is None or policy_evaluation.feasible)
            and (stage_b_result or {}).get("feedback", {}).get("verdict") == "APPROVE",
            stage_a_passed=stage_a_passed,
            stage_b_result=deepcopy(stage_b_result),
            duration_seconds=iter_duration,
            policy_evaluation=deepcopy(policy_evaluation),
            policy_evaluation_status=policy_resolution.status,
            policy_evaluation_error=policy_resolution.reason,
        )
        if not is_sentinel and self._diversity_tracker is not None:
            self._diversity_tracker.record_iteration(candidate)
        return _EvaluationTransition(
            disposition=(
                _EvaluationDisposition.SENTINEL if is_sentinel else _EvaluationDisposition.ORDINARY
            ),
            record=record,
        )

    def _build_generation_context(
        self,
        context: dict[str, Any],
        *,
        iteration: int,
    ) -> dict[str, Any]:
        enriched = dict(context)
        best_candidate = self._best_candidate
        best_objective = self._best_objective
        if best_candidate is None and best_objective == float("inf"):
            best_objective = None
        enriched["search_state"] = {
            "iteration": int(iteration),
            "history_length": len(self._history),
            "current_best_candidate": best_candidate,
            "current_best_objective": best_objective,
        }
        if self._history:
            enriched["last_stage_b_result"] = self._history[-1].stage_b_result
        lesson_hints = self._build_lesson_hints(enriched)
        if lesson_hints:
            enriched["lesson_hints"] = lesson_hints
        try:
            from polisyos.scientist.methods.autotune.execution_plan import (
                build_execution_plan_generation_context,
            )
        except _IMPORT_ERRORS as exc:
            _search_degraded(
                operation="build_generation_context",
                reason="execution_plan_context_unavailable",
                exc=exc,
                details={"iteration": iteration},
            )
            return enriched

        try:
            execution_plan_context = build_execution_plan_generation_context(
                history=self._history,
                current_best=self._best_candidate,
                context=enriched,
            )
        except _SEARCH_DEGRADED_ERRORS as exc:
            _search_degraded(
                operation="build_generation_context",
                reason="execution_plan_context_failed",
                exc=exc,
                details={"iteration": iteration},
            )
            return enriched

        if execution_plan_context.get("execution_plan_topology_mutation_payload"):
            enriched.update(execution_plan_context)
        return enriched

    def _build_lesson_hints(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        lesson_registry = context.get("lesson_registry")
        if lesson_registry is None:
            return []
        try:
            from polisyos.scientist.methods.search.lessons import LessonQuery
            from polisyos.scientist.methods.search.transfer_context import (
                lesson_hint_payload,
                resolve_transfer_context,
            )

            transfer_context = resolve_transfer_context(context=context)
            if hasattr(lesson_registry, "query_with_transfer"):
                cards = lesson_registry.query_with_transfer(
                    LessonQuery(
                        task_family=transfer_context.task_family,
                        min_confidence=0.5,
                        limit=3,
                    ),
                    target_context=transfer_context,
                )
                return [lesson_hint_payload(card) for card in cards]
            if hasattr(lesson_registry, "top_patterns"):
                return [
                    {
                        "summary": pattern.summary,
                        "failure_type": pattern.failure_type,
                        "remediation_hint": pattern.remediation_hint,
                        "trust_level": (
                            pattern.trust_level.value
                            if hasattr(pattern.trust_level, "value")
                            else str(pattern.trust_level)
                        ),
                        "provenance_weight": float(
                            getattr(pattern, "provenance_weight", 1.0) or 0.0
                        ),
                        "domain": getattr(pattern, "domain", "general"),
                        "task_family": getattr(pattern, "task_family", "policy"),
                    }
                    for pattern in lesson_registry.top_patterns(limit=3)
                ]
        except (_IMPORT_ERRORS, _SEARCH_DEGRADED_ERRORS) as exc:
            _search_degraded(
                operation="build_lesson_hints",
                reason="lesson_hint_generation_failed",
                exc=exc,
            )
        return []

    def _resolve_policy_evaluation(
        self,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any] | None,
    ) -> PolicyEvaluationVector | None:
        """Resolve a typed evaluation while preserving the legacy private API."""
        resolution = self._resolve_policy_evaluation_with_status(candidate, stage_b_result)
        return cast("PolicyEvaluationVector | None", resolution.value)

    def _resolve_policy_evaluation_with_status(
        self,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any] | None,
    ) -> _PolicyEvaluationResolution:
        """Resolve typed evaluation input without conflating absent and invalid data."""
        if not stage_b_result:
            return _PolicyEvaluationResolution(value=None, status="missing")

        typed_vector_present = "policy_evaluation" in stage_b_result
        typed_bundle_present = (
            "policy_evaluation_bundle" in stage_b_result
            or "_policy_evaluation_bundle" in stage_b_result
        )
        if not typed_vector_present and not typed_bundle_present:
            return _PolicyEvaluationResolution(value=None, status="missing")

        try:
            from polisyos.scientist.policy_design.objectives import (
                PolicyEvaluationBundle,
                _normalize_policy_evaluation_vector,
            )
            from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
        except _IMPORT_ERRORS as exc:
            _search_degraded(
                operation="resolve_policy_evaluation",
                reason="policy_objective_stack_unavailable",
                exc=exc,
            )
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason="policy_objective_stack_unavailable",
            )

        typed_error_reason: str | None = None
        if typed_vector_present:
            raw_vector = stage_b_result.get("policy_evaluation")
            try:
                return _PolicyEvaluationResolution(
                    value=_normalize_policy_evaluation_vector(raw_vector, allow_mapping=True),
                    status="valid",
                )
            except _SEARCH_DEGRADED_ERRORS as exc:
                typed_error_reason = "policy_evaluation_parse_failed"
                _search_degraded(
                    operation="resolve_policy_evaluation",
                    reason=typed_error_reason,
                    exc=exc,
                )

        objective_stack = self._config.policy_objective_stack
        if objective_stack is None:
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason=typed_error_reason or "policy_evaluation_stack_unavailable",
            )

        raw_bundle = stage_b_result.get("policy_evaluation_bundle")
        if raw_bundle is None:
            raw_bundle = stage_b_result.get("_policy_evaluation_bundle")
        if raw_bundle is None:
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason=typed_error_reason or "policy_evaluation_bundle_missing",
            )
        try:
            if isinstance(raw_bundle, PolicyEvaluationBundle):
                bundle = raw_bundle
            else:
                if hasattr(raw_bundle, "model_dump"):
                    raw_bundle = raw_bundle.model_dump(mode="python")
                bundle = PolicyEvaluationBundle.model_validate(raw_bundle)
        except _SEARCH_DEGRADED_ERRORS as exc:
            _search_degraded(
                operation="resolve_policy_evaluation",
                reason="policy_evaluation_bundle_parse_failed",
                exc=exc,
            )
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason="policy_evaluation_bundle_parse_failed",
            )

        if bundle.candidate is None:
            candidate_schema = stage_b_result.get("_policy_candidate_schema") or stage_b_result.get(
                "policy_candidate"
            )
            if isinstance(candidate_schema, PolicyCandidateSchema):
                bundle = bundle.model_copy(update={"candidate": candidate_schema})
            else:
                try:
                    if hasattr(candidate_schema, "model_dump"):
                        candidate_payload = candidate_schema.model_dump(mode="python")
                    else:
                        candidate_payload = candidate_schema
                    if isinstance(candidate_payload, dict):
                        bundle = bundle.model_copy(
                            update={
                                "candidate": PolicyCandidateSchema.model_validate(candidate_payload)
                            }
                        )
                except _SEARCH_DEGRADED_ERRORS as exc:
                    _search_degraded(
                        operation="resolve_policy_evaluation",
                        reason="policy_candidate_parse_failed",
                        exc=exc,
                    )
            if (
                bundle.candidate is None
                and isinstance(candidate, dict)
                and "trinity_bundle" in candidate
            ):
                try:
                    bundle = bundle.model_copy(
                        update={"candidate": PolicyCandidateSchema.model_validate(candidate)}
                    )
                except _SEARCH_DEGRADED_ERRORS as exc:
                    _search_degraded(
                        operation="resolve_policy_evaluation",
                        reason="policy_candidate_validation_failed",
                        exc=exc,
                    )

        try:
            evaluation = objective_stack.evaluate(bundle)
            try:
                normalized = _normalize_policy_evaluation_vector(evaluation)
            except TypeError as exc:
                _search_degraded(
                    operation="resolve_policy_evaluation",
                    reason="objective_stack_returned_untyped_result",
                    exc=exc,
                )
                return _PolicyEvaluationResolution(
                    value=None,
                    status="invalid",
                    reason="objective_stack_returned_untyped_result",
                )
            except _SEARCH_DEGRADED_ERRORS as exc:
                _search_degraded(
                    operation="resolve_policy_evaluation",
                    reason="objective_stack_returned_invalid_vector",
                    exc=exc,
                )
                return _PolicyEvaluationResolution(
                    value=None,
                    status="invalid",
                    reason="objective_stack_returned_invalid_vector",
                )
            return _PolicyEvaluationResolution(value=normalized, status="valid")
        except _SEARCH_DEGRADED_ERRORS as exc:
            _search_degraded(
                operation="resolve_policy_evaluation",
                reason="objective_stack_evaluation_failed",
                exc=exc,
            )
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason="objective_stack_evaluation_failed",
            )

    def _update_policy_or_legacy_frontier(
        self,
        *,
        candidate: dict[str, Any],
        objective_details: list[ObjectiveValue],
        policy_evaluation: PolicyEvaluationVector | None,
        stage_b_result: dict[str, Any] | None,
    ) -> None:
        registry = self._config.pareto_registry
        if policy_evaluation is not None and registry is not None:
            try:
                from polisyos.scientist.methods.search.transfer_context import (
                    resolve_transfer_context,
                )
            except _IMPORT_ERRORS as exc:
                _search_degraded(
                    operation="update_frontier",
                    reason="transfer_context_unavailable",
                    exc=exc,
                )
                transfer_context = None
            else:
                transfer_context = resolve_transfer_context(
                    candidate=candidate, fallback_run_id=self._search_id
                )
            candidate_hash = self._policy_candidate_hash(
                candidate=candidate,
                policy_evaluation=policy_evaluation,
                stage_b_result=stage_b_result or {},
            )
            registry.update(
                self._search_id,
                candidate_hash=candidate_hash,
                evaluation=policy_evaluation,
                candidate_id=policy_evaluation.candidate_id,
                candidate_ref=(stage_b_result or {}).get("candidate_ref"),
                policy_family=(str(policy_evaluation.metadata.get("policy_family") or "") or None),
                promotion_metadata={
                    "iteration": len(self._history),
                    "feedback": dict((stage_b_result or {}).get("feedback", {})),
                },
                seed_payload=dict(candidate),
                task_family=(
                    transfer_context.task_family if transfer_context is not None else None
                ),
                domain=(transfer_context.domain if transfer_context is not None else None),
                transfer_context=transfer_context,
                objective_basis_by_view=(self._config.pareto_objective_basis_by_view or None),
            )
            from polisyos.scientist.methods.search.pareto_registry import ParetoView

            self._run_state.pareto_projection = registry.get_snapshot(
                self._search_id, transfer_context=transfer_context
            ).project_view(ParetoView.GLOBAL_FEASIBLE)
            self._pareto_front = registry.as_legacy_frontier_payload(
                self._search_id, transfer_context=transfer_context
            )
            return

        if objective_details:
            self._update_pareto_front(candidate, objective_details)

    @staticmethod
    def _policy_candidate_hash(
        *,
        candidate: dict[str, Any],
        policy_evaluation: PolicyEvaluationVector,
        stage_b_result: dict[str, Any],
    ) -> str:
        metadata_hash = str(policy_evaluation.metadata.get("candidate_hash", "")).strip()
        explicit = stage_b_result.get("candidate_hash")
        return policy_candidate_hash(
            candidate,
            metadata_hash=metadata_hash,
            explicit_hash=explicit if isinstance(explicit, str) else None,
        )

    def _update_pareto_front(
        self,
        candidate: dict[str, Any],
        objectives: list[ObjectiveValue],
    ) -> None:
        """Update the Pareto front with a new candidate if non-dominated."""
        self._pareto_points = update_legacy_pareto_front(
            self._pareto_points,
            candidate=candidate,
            objectives=objectives,
            cap=100,
        )
        self._pareto_front = [point.as_payload() for point in self._pareto_points]

    @staticmethod
    def _dominates(a: list[float], b: list[float]) -> bool:
        """Return True if *a* dominates *b* (all <= and at least one <)."""
        return dominates(a, b)

    def _to_history_dict(self, iteration: SearchIteration) -> dict[str, Any]:
        """Convert iteration to dict for stopping criteria."""
        return {
            "iteration": iteration.iteration,
            "objective_value": iteration.objective_value,
            "is_promising": iteration.is_promising,
            "stage_a_passed": iteration.stage_a_passed,
        }

    def run_portfolio_search(
        self,
        *,
        portfolio: Any,
        evaluator: Callable[[Any, dict[str, Any]], Any],
        mode: str = "enumerate",
        max_evaluations: int = 100,
        base_benefits: dict[str, float] | None = None,
        initial_context: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Run discrete portfolio optimization over policy combinations.

        Returns a list of `PortfolioEvaluationResult`, sorted by objective descending.
        """

        from polisyos.scientist.methods.search.portfolio import (
            PortfolioEvaluationResult,
            PortfolioSearchMode,
            PortfolioSearchSpace,
        )

        context = dict(initial_context or {})
        base = dict(base_benefits or {})
        max_evaluations = max(1, int(max_evaluations))

        search_space = PortfolioSearchSpace(portfolio)
        search_mode = PortfolioSearchMode(mode)
        if search_mode is PortfolioSearchMode.ENUMERATE:
            try:
                combinations = search_space.enumerate_combinations()
            except ValueError as exc:
                logger.warning(
                    "Portfolio enumeration capped ({}). Falling back to sampling mode.",
                    exc,
                )
                combinations = search_space.sample_combinations(max_evaluations)
        elif search_mode is PortfolioSearchMode.SAMPLE:
            combinations = search_space.sample_combinations(max_evaluations)
        else:
            combinations = search_space.greedy_combinations(
                base_benefits=base,
                max_combinations=max_evaluations,
            )

        results: list[PortfolioEvaluationResult] = []
        for combination in combinations[:max_evaluations]:
            raw = evaluator(combination, context)
            if isinstance(raw, PortfolioEvaluationResult):
                result = raw
            elif isinstance(raw, dict):
                value = float(raw.get("objective_value", 0.0))
                result = PortfolioEvaluationResult(
                    combination=combination,
                    objective_value=value,
                    metrics=raw,
                )
            else:
                result = PortfolioEvaluationResult(
                    combination=combination,
                    objective_value=float(raw),
                    metrics={},
                )
            results.append(result)

        results.sort(key=lambda item: item.objective_value, reverse=True)

        portfolio_id = str(getattr(portfolio, "portfolio_id", "portfolio"))
        helper = getattr(self._metrics, "record_portfolio_search", None)
        if callable(helper):
            helper(
                portfolio_id=portfolio_id,
                combinations_evaluated=len(results),
                best_objective=(float(results[0].objective_value) if results else None),
            )
        else:
            counter = getattr(self._metrics, "portfolio_combinations_evaluated", None)
            if counter is not None and hasattr(counter, "add"):
                counter.add(len(results), {"portfolio_id": portfolio_id})
            gauge = getattr(self._metrics, "portfolio_best_objective", None)
            if results and gauge is not None and hasattr(gauge, "set"):
                gauge.set(float(results[0].objective_value), {"portfolio_id": portfolio_id})

        return results
