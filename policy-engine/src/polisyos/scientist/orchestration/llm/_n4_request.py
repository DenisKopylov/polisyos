"""Internal N4 stage vocabulary over the generic source-owned request carrier.

The common carrier knows no N4 or policy-domain vocabulary. Only the canonical
N4 call owners issue these candidate-computation stages.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, get_args

from polisyos.common.producer_request import (
    ProducerRequestBinding as _ProducerBinding,
)
from polisyos.common.producer_request import (
    consume_producer_request_context as _generic_call_context,
)
from polisyos.common.producer_request import (
    producer_request_scope as _binding_scope,
)
from polisyos.common.producer_request import (
    read_producer_payload as _generic_read_payload,
)

_OWNER = "scientist.n4"
_N4Stage = Literal["draft", "drafter_multipass", "drafter_consolidation", "formalizer", "critic"]
_STAGES = frozenset(get_args(_N4Stage))


def _n4_binding(problem_ref: str, model_id: str) -> _ProducerBinding:
    return _ProducerBinding(problem_ref, model_id, _OWNER)


def _check_n4_context(context: dict[str, Any]) -> dict[str, Any]:
    if context["producer_id"] != _OWNER or context["stage"] not in _STAGES:
        raise ValueError("n4_producer_context_incompatible")
    return context


def _request_args(
    client: object,
    *,
    stage: _N4Stage,
    attempt: int = 0,
    instance: str | None = None,
    **request: Any,
) -> dict[str, Any]:
    binding = getattr(client, "_producer_request_binding", None)
    if binding is None:
        return request
    if type(binding) is not _ProducerBinding or binding.producer_id != _OWNER:
        raise ValueError("n4_producer_binding_incompatible")
    if stage not in _STAGES:
        raise ValueError("n4_producer_stage_invalid")
    issue = getattr(client, "_issue_producer_request", None)
    if not callable(issue):
        raise ValueError("n4_producer_source_preparer_missing")
    return issue(stage=stage, attempt=attempt, instance=instance, request=request)


def _call_context(
    request: Mapping[str, Any], binding: _ProducerBinding | None
) -> dict[str, Any] | None:
    context = _generic_call_context(request, binding)
    return _check_n4_context(context) if context is not None else None


def _read_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _check_n4_context(_generic_read_payload(payload))
