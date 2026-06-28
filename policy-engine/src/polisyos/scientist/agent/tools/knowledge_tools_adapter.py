"""Auto-convert ``KnowledgeToolkit`` methods into ``ToolDefinition``s."""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from polisyos.common.logger import get_logger

from .registry import ToolRegistry
from .schema import ToolDefinition
from .scholar_search_tools import build_scholar_search_tool_registry

logger = get_logger(__name__)

# Methods to expose as tools.  If empty, all public non-format methods are exposed.
_INCLUDE_METHODS: set[str] = {
    "search_datasets",
    "find_datasets_for_metric",
    "get_dataset_connector",
    "search_evidence",
    "get_parameter_prior",
    "find_causal_evidence",
    "get_mechanism_evidence",
    "search_legal_facts",
    "search_legal_provisions",
    "find_legal_constraints",
    "search_legal_thresholds",
    "get_applicable_norms",
    "load_provisions_by_anchor",
    "load_doc_version_chain",
    "expand_reference_neighborhood",
    "load_source_bundle",
    "assemble_legal_candidate_pack",
    "expand_legal_source_pack",
    "remember",
    "recall",
}

# Python type → JSON Schema type mapping.
_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "null",
    "NoneType": "null",
}


def _python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Best-effort mapping from a Python type annotation to JSON Schema."""
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}

    name = getattr(annotation, "__name__", str(annotation))

    # Handle Optional[X] → {"type": X_type}
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # list[X]
        if origin is list:
            args = getattr(annotation, "__args__", ())
            if args:
                return {"type": "array", "items": _python_type_to_json_schema(args[0])}
            return {"type": "array"}
        # dict[str, X]
        if origin is dict:
            return {"type": "object"}
        # Union/Optional
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_json_schema(non_none[0])

    json_type = _TYPE_MAP.get(name, "string")
    return {"type": json_type}


def _method_to_tool_definition(
    name: str,
    method: Any,
    *,
    domain: str = "",
) -> ToolDefinition:
    """Build a ``ToolDefinition`` from a method's signature and docstring."""
    sig = inspect.signature(method)
    if hasattr(method, "__annotations__"):
        try:
            hints = get_type_hints(method)
        except (NameError, TypeError, AttributeError):
            hints = dict(getattr(method, "__annotations__", {}))
    else:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        schema = _python_type_to_json_schema(hints.get(param_name, param.annotation))

        # Add description from docstring (if available) or parameter name
        schema["description"] = param_name.replace("_", " ")

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        elif param.default is not None:
            schema["default"] = param.default

        properties[param_name] = schema

    return ToolDefinition(
        name=name,
        description=(method.__doc__ or name.replace("_", " ")).strip().split("\n")[0],
        parameters={
            "type": "object",
            "properties": properties,
            "required": required,
        },
        domain=domain,
    )


def _infer_domain(name: str) -> str:
    """Infer the knowledge domain from the method name."""
    if "dataset" in name or "metric" in name or "connector" in name:
        return "datasets"
    if "evidence" in name or "parameter" in name or "causal" in name or "mechanism" in name:
        return "academic"
    if "legal" in name or "provision" in name or "norm" in name or "source" in name:
        return "legal"
    return ""


def build_knowledge_tool_registry(
    toolkit: Any,
    *,
    scholar_search_service: Any | None = None,
) -> ToolRegistry:
    """Introspect a ``KnowledgeToolkit`` instance and register all
    eligible methods as tools.

    Parameters
    ----------
    toolkit:
        A ``KnowledgeToolkit`` instance (or any object with matching methods).

    Returns
    -------
    ToolRegistry with all eligible methods registered.
    """
    registry = ToolRegistry()

    for name in sorted(dir(toolkit)):
        if name.startswith("_") or name.startswith("format_"):
            continue
        if _INCLUDE_METHODS and name not in _INCLUDE_METHODS:
            continue

        method = getattr(toolkit, name, None)
        if method is None or not callable(method):
            continue

        try:
            definition = _method_to_tool_definition(name, method, domain=_infer_domain(name))
            registry.register(definition, method)
        except Exception as exc:
            logger.debug("Failed to register tool %s: %s", name, exc)

    if scholar_search_service is not None:
        scholar_registry = build_scholar_search_tool_registry(scholar_search_service)
        for definition in scholar_registry.list_definitions():
            _, handler = scholar_registry.get(definition.name)
            registry.register(definition, handler)

    return registry
