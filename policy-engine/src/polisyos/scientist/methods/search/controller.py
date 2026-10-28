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

from polisyos.scientist.methods.search.contracts import (
    CandidatePayload,
    ParetoBasisScope,
    SearchContext,
    SearchIteration,
    SearchResult,
    SearchStatus,
    StageAEvaluator,
    StageBEvaluator,
    _EvaluationDisposition,
    _EvaluationTransition,
)
from polisyos.scientist.methods.search.frontier import (
    FrontierPoint,
    dominates,
    policy_candidate_hash,
    update_legacy_pareto_front,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _IMPORT_ERRORS as _IMPORT_ERRORS,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _SEARCH_DEGRADED_ERRORS as _SEARCH_DEGRADED_ERRORS,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _as_bool as _as_bool,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _default_metrics as _default_metrics,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _PolicyEvaluationResolution as _PolicyEvaluationResolution,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _search_degraded as _search_degraded,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    logger as logger,
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

if TYPE_CHECKING:
    from polisyos.core.llm import TracedLLMClient
    from polisyos.core.observability import MetricsRegistry
    from polisyos.scientist.methods.search.lifecycle import _SearchLifecycleOwner
    from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
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


@dataclass(frozen=True)
class _OwnerBudgetStopping(StoppingCriterion):
    """Fail closed unless one exact durable owner snapshot leaves budget."""

    def __init__(self, delegate: StoppingCriterion) -> None:
        object.__setattr__(self, "_delegate", delegate)

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
            cache_settlement_session=getattr(self.client, "_accounting_flight_owner", None),
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
    transfer_fingerprint: RunFingerprint | None = None
    initial_evaluations: list[dict[str, Any]] = field(default_factory=list)
    policy_objective_stack: ObjectiveStack | None = None
    pareto_registry: ParetoRegistry | None = None
    policy_source_store: Any | None = None
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
        if self.transfer_fingerprint is not None:
            from polisyos.scientist.methods.search.strategies.transfer import (
                RunFingerprint,
                TransferLearningManager,
            )

            if type(self.transfer_manager) is not TransferLearningManager:
                raise TypeError("transfer_history_owner_required")
            if type(self.transfer_fingerprint) is not RunFingerprint:
                raise TypeError("transfer_history_fingerprint_required")
            if not self.transfer_manager._has_complete_binding_basis(self.transfer_fingerprint):
                raise ValueError("transfer_history_fingerprint_incomplete")
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
    """Compatibility facade forwarding the historical controller surface.

    Mutable lifecycle state, configuration, evaluation, and run flow live in
    :class:`_SearchLifecycleOwner`. This facade preserves existing call sites
    and serialized-type module identities without owning a second ledger.
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
        from polisyos.scientist.methods.search.lifecycle import _SearchLifecycleOwner

        self.__lifecycle_owner = _SearchLifecycleOwner(
            config=config,
            candidate_generator=candidate_generator,
            stage_a_evaluator=stage_a_evaluator,
            stage_b_evaluator=stage_b_evaluator,
            evaluators=evaluators,
            metrics=metrics,
            metrics_factory=_default_metrics,
            bound_owner_validator=TracedLLMCandidateGenerator.require_bound_owner,
        )

    @property
    def _lifecycle_owner(self) -> _SearchLifecycleOwner:
        """Expose the single private owner to existing internal adapters."""
        return self.__lifecycle_owner

    @property
    def _config(self) -> SearchConfig:
        return self.__lifecycle_owner._config

    @_config.setter
    def _config(self, value: SearchConfig) -> None:
        self.__lifecycle_owner._config = value

    @property
    def _generator(self) -> CandidateGenerator:
        return self.__lifecycle_owner._generator

    @_generator.setter
    def _generator(self, value: CandidateGenerator) -> None:
        self.__lifecycle_owner._generator = value

    @property
    def _stage_a(self) -> StageAEvaluator:
        return self.__lifecycle_owner._stage_a

    @_stage_a.setter
    def _stage_a(self, value: StageAEvaluator) -> None:
        self.__lifecycle_owner._stage_a = value

    @property
    def _stage_b(self) -> StageBEvaluator:
        return self.__lifecycle_owner._stage_b

    @_stage_b.setter
    def _stage_b(self, value: StageBEvaluator) -> None:
        self.__lifecycle_owner._stage_b = value

    @property
    def _run_lock(self) -> Lock:
        return self.__lifecycle_owner._run_lock

    @_run_lock.setter
    def _run_lock(self, value: Lock) -> None:
        self.__lifecycle_owner._run_lock = value

    @property
    def _run_state(self) -> SearchRunState:
        return self.__lifecycle_owner._run_state

    @_run_state.setter
    def _run_state(self, value: SearchRunState) -> None:
        self.__lifecycle_owner._run_state = value

    @property
    def _source_budget_snapshot(self) -> dict[str, Any]:
        return self.__lifecycle_owner._source_budget_snapshot

    @_source_budget_snapshot.setter
    def _source_budget_snapshot(self, value: dict[str, Any]) -> None:
        self.__lifecycle_owner._source_budget_snapshot = value

    @property
    def _metrics(self) -> MetricsRegistry:
        return self.__lifecycle_owner._metrics

    @_metrics.setter
    def _metrics(self, value: MetricsRegistry) -> None:
        self.__lifecycle_owner._metrics = value

    @property
    def _diversity_enabled(self) -> bool:
        return self.__lifecycle_owner._diversity_enabled

    @_diversity_enabled.setter
    def _diversity_enabled(self, value: bool) -> None:
        self.__lifecycle_owner._diversity_enabled = value

    @property
    def _diversity_tracker(self) -> Any | None:
        return self.__lifecycle_owner._diversity_tracker

    @_diversity_tracker.setter
    def _diversity_tracker(self, value: Any | None) -> None:
        self.__lifecycle_owner._diversity_tracker = value

    @property
    def _history(self) -> list[SearchIteration]:
        return self.__lifecycle_owner._history

    @_history.setter
    def _history(self, value: list[SearchIteration]) -> None:
        self.__lifecycle_owner._history = value

    @property
    def _best_candidate(self) -> dict[str, Any] | None:
        return self.__lifecycle_owner._best_candidate

    @_best_candidate.setter
    def _best_candidate(self, value: dict[str, Any] | None) -> None:
        self.__lifecycle_owner._best_candidate = value

    @property
    def _best_objective(self) -> float:
        return self.__lifecycle_owner._best_objective

    @_best_objective.setter
    def _best_objective(self, value: float) -> None:
        self.__lifecycle_owner._best_objective = value

    @property
    def _status(self) -> SearchStatus:
        return self.__lifecycle_owner._status

    @_status.setter
    def _status(self, value: SearchStatus) -> None:
        self.__lifecycle_owner._status = value

    @property
    def _search_id(self) -> str:
        return self.__lifecycle_owner._search_id

    @_search_id.setter
    def _search_id(self, value: str) -> None:
        self.__lifecycle_owner._search_id = value

    @property
    def _pareto_front(self) -> list[dict[str, Any]]:
        return self.__lifecycle_owner._pareto_front

    @_pareto_front.setter
    def _pareto_front(self, value: list[dict[str, Any]]) -> None:
        self.__lifecycle_owner._pareto_front = value

    @property
    def _pareto_points(self) -> list[FrontierPoint]:
        return self.__lifecycle_owner._pareto_points

    @_pareto_points.setter
    def _pareto_points(self, value: list[FrontierPoint]) -> None:
        self.__lifecycle_owner._pareto_points = value

    @property
    def _stage_a_count(self) -> int:
        return self.__lifecycle_owner._stage_a_count

    @_stage_a_count.setter
    def _stage_a_count(self, value: int) -> None:
        self.__lifecycle_owner._stage_a_count = value

    @property
    def _stage_b_count(self) -> int:
        return self.__lifecycle_owner._stage_b_count

    @_stage_b_count.setter
    def _stage_b_count(self, value: int) -> None:
        self.__lifecycle_owner._stage_b_count = value

    @property
    def _sentinel_evaluations(self) -> int:
        return self.__lifecycle_owner._sentinel_evaluations

    @_sentinel_evaluations.setter
    def _sentinel_evaluations(self, value: int) -> None:
        self.__lifecycle_owner._sentinel_evaluations = value

    def run(
        self,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Run the lifecycle through the historical compatibility entrypoint."""
        return self.__lifecycle_owner.run(initial_context, initial_candidate)

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
        """Forward the historical discrete portfolio optimization entrypoint."""
        return self.__lifecycle_owner.run_portfolio_search(
            portfolio=portfolio,
            evaluator=evaluator,
            mode=mode,
            max_evaluations=max_evaluations,
            base_benefits=base_benefits,
            initial_context=initial_context,
        )

    def _build_generation_context(
        self,
        context: dict[str, Any],
        *,
        iteration: int,
    ) -> dict[str, Any]:
        return self.__lifecycle_owner._build_generation_context(context, iteration=iteration)

    def _resolve_policy_evaluation_with_status(
        self,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any] | None,
    ) -> _PolicyEvaluationResolution:
        return self.__lifecycle_owner._resolve_policy_evaluation_with_status(
            candidate, stage_b_result
        )

    def _resolve_policy_evaluation(
        self,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any] | None,
    ) -> PolicyEvaluationVector | None:
        return self.__lifecycle_owner._resolve_policy_evaluation(candidate, stage_b_result)

    def _update_pareto_front(
        self,
        candidate: dict[str, Any],
        objectives: list[ObjectiveValue],
    ) -> None:
        self.__lifecycle_owner._update_pareto_front(candidate, objectives)

    @staticmethod
    def _dominates(a: list[float], b: list[float]) -> bool:
        """Retain the historical static Pareto comparison helper."""
        return dominates(a, b)
