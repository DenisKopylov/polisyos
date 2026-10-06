"""Schema helpers for BERL ExplanationBundle artifacts."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    HISTORICAL_EXPLANATION_BUNDLE_SCHEMA_VERSIONS,
    ExplanationBundle,
    bundle_json_schema,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


_PERSISTED_REQUIRED_FIELDS = (
    "schema_version",
    "bundle_id",
    "created_at",
    "model",
    "prediction",
    "feature_context",
    "assumptions",
    "methods",
    "validity",
    "audit",
)


def explanation_bundle_schema_id() -> str:
    """Return the stable schema id for the current bundle version."""

    return (
        "https://polisyos.local/schemas/berl/explanation_bundle/"
        f"{EXPLANATION_BUNDLE_SCHEMA_VERSION}"
    )


def generated_explanation_bundle_schema() -> dict[str, object]:
    """Return the reproducible persisted-output profile for ExplanationBundle."""

    schema = bundle_json_schema()
    schema["$id"] = explanation_bundle_schema_id()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "BERL ExplanationBundle"
    schema["description"] = (
        "Versioned audit contract for bounded, assumption-scoped model explanations."
    )
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise TypeError("ExplanationBundle schema must define object properties")
    properties["schema_version"] = {"const": EXPLANATION_BUNDLE_SCHEMA_VERSION}
    schema["required"] = list(_PERSISTED_REQUIRED_FIELDS)
    return schema


def validate_persisted_explanation_bundle(
    payload: Mapping[str, object],
) -> ExplanationBundle:
    """Validate a serialized bundle against the canonical persisted-output profile.

    Construction DTOs intentionally retain defaults and a general semantic-version
    pattern. Persisted records have a narrower contract: their complete top-level
    shape and exact supported wire version must satisfy the generated JSON schema
    before the strict DTO is materialized.

    Args:
        payload: JSON object read from a persisted explanation artifact.

    Returns:
        The validated ExplanationBundle.

    Raises:
        ValueError: If the payload is outside the generated persisted profile.
    """

    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise ValueError(
            "persisted ExplanationBundle schema validation failed at schema_version: "
            "a supported schema_version is required"
        )
    schema = _persisted_schema_for_version(version)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_error = next(validator.iter_errors(payload), None)
    if schema_error is not None:
        path = ".".join(str(part) for part in schema_error.absolute_path) or "$"
        raise ValueError(
            "persisted ExplanationBundle schema validation failed "
            f"at {path}: {schema_error.message}"
        )
    try:
        return ExplanationBundle.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"persisted ExplanationBundle DTO validation failed: {exc}") from exc


def _persisted_schema_for_version(version: str) -> dict[str, object]:
    """Return a generated schema profile for one explicitly supported wire version."""

    if version == EXPLANATION_BUNDLE_SCHEMA_VERSION:
        return generated_explanation_bundle_schema()
    if version not in HISTORICAL_EXPLANATION_BUNDLE_SCHEMA_VERSIONS:
        raise ValueError(
            "persisted ExplanationBundle schema validation failed at schema_version: "
            f"unsupported version {version}"
        )

    # Version 1.0.0 predates the optional typed conditional evidence member. Keep
    # its exact accepted shape while deriving unchanged structure from the owner
    # model and applying only the historical field/version deltas.
    schema = deepcopy(generated_explanation_bundle_schema())
    schema["$id"] = explanation_bundle_schema_id().rsplit("/", 1)[0] + f"/{version}"
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise TypeError("ExplanationBundle schema must define object properties")
    properties["schema_version"] = {"const": version}
    definitions = schema.get("$defs")
    if isinstance(definitions, dict):
        method_schema = definitions.get("MethodExplanation")
        if isinstance(method_schema, dict):
            method_properties = method_schema.get("properties")
            if isinstance(method_properties, dict):
                method_properties.pop("conditional_evidence", None)
        definitions.pop("ConditionalExplanationEvidence", None)
    return schema


def write_explanation_bundle_schema(path: Path) -> None:
    """Write the generated schema to a JSON file."""

    payload = json.dumps(generated_explanation_bundle_schema(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")
