"""Schema helpers for BERL ExplanationBundle artifacts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    bundle_json_schema,
)

if TYPE_CHECKING:
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
