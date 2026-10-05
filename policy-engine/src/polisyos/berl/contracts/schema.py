"""Schema helpers for BERL ExplanationBundle artifacts."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
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


def write_explanation_bundle_schema(path: Path) -> None:
    """Write the generated schema to a JSON file."""

    payload = json.dumps(generated_explanation_bundle_schema(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


def validate_persisted_explanation_bundle(
    payload: Mapping[str, object],
) -> ExplanationBundle:
    """Validate a serialized artifact against the canonical persisted profile.

    The construction DTO remains permissive about supported defaults and
    semver-shaped candidates. Persisted consumers must satisfy the generated
    schema for the current wire version before receiving that DTO's defaults.

    Args:
        payload: JSON-compatible serialized bundle record.

    Returns:
        The DTO parsed after the persisted-output profile passes.

    Raises:
        ValueError: If the record violates the generated profile or DTO.
    """

    try:
        _persisted_explanation_bundle_validator().validate(payload)
    except JsonSchemaValidationError as exc:
        field_path = ".".join(str(part) for part in exc.absolute_path) or "$"
        raise ValueError(
            "persisted ExplanationBundle does not satisfy the current schema: "
            f"{field_path} ({exc.validator})"
        ) from exc
    return ExplanationBundle.model_validate(payload)


@lru_cache(maxsize=1)
def _persisted_explanation_bundle_validator() -> Draft202012Validator:
    return Draft202012Validator(
        generated_explanation_bundle_schema(),
        format_checker=FormatChecker(),
    )
