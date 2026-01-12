import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set, Tuple

DEFAULT_ALLOWED_COLUMNS = {
    "macro_history": {
        "run_id",
        "step",
        "gdp",
        "unemployment_rate",
        "inflation_rate",
        "avg_price",
        "avg_income",
        "government_balance",
        "timestamp",
    },
    "agents_snapshot": {
        "run_id",
        "step",
        "agent_id",
        "age",
        "income",
        "savings",
        "is_employed",
    },
}

# Interaction.type values allowed in network queries.
DEFAULT_ALLOWED_RELATION_TYPES = {"paid_tax", "transfer"}

DEFAULT_SCHEMA_PATH = Path("data/curated/udf_schema.json")


DEFAULT_FIELD_CLASSIFICATION = {
    "macro_history": {
        "run_id": "internal",
        "step": "public",
        "gdp": "public",
        "unemployment_rate": "public",
        "inflation_rate": "public",
        "avg_price": "public",
        "avg_income": "public",
        "government_balance": "public",
        "timestamp": "internal",
    },
    "agents_snapshot": {
        "run_id": "internal",
        "step": "internal",
        "agent_id": "sensitive",
        "age": "internal",
        "income": "internal",
        "savings": "internal",
        "is_employed": "internal",
    },
}


@dataclass(frozen=True)
class UdfSchema:
    allowed_columns: Dict[str, Set[str]]
    allowed_relation_types: Set[str]
    field_classification: Dict[str, Dict[str, str]]


def _load_schema_file(path: Path) -> UdfSchema:
    if not path.exists():
        return UdfSchema(
            allowed_columns=DEFAULT_ALLOWED_COLUMNS,
            allowed_relation_types=DEFAULT_ALLOWED_RELATION_TYPES,
            field_classification=DEFAULT_FIELD_CLASSIFICATION,
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Некорректный или битый schema-файл — откатываемся к дефолтным правилам.
        return UdfSchema(
            allowed_columns=DEFAULT_ALLOWED_COLUMNS,
            allowed_relation_types=DEFAULT_ALLOWED_RELATION_TYPES,
            field_classification=DEFAULT_FIELD_CLASSIFICATION,
        )
    raw_cols = data.get("allowed_columns", {})
    raw_rel = data.get("allowed_relation_types", [])
    raw_class = data.get("field_classification", {})
    allowed_columns = {k: set(v) for k, v in raw_cols.items()}
    allowed_relations = set(raw_rel)
    field_classification = {k: dict(v) for k, v in raw_class.items()}
    if not allowed_columns:
        allowed_columns = DEFAULT_ALLOWED_COLUMNS
    if not allowed_relations:
        allowed_relations = DEFAULT_ALLOWED_RELATION_TYPES
    if not field_classification:
        field_classification = DEFAULT_FIELD_CLASSIFICATION
    return UdfSchema(
        allowed_columns=allowed_columns,
        allowed_relation_types=allowed_relations,
        field_classification=field_classification,
    )


def load_udf_schema(path: Path | None = None) -> UdfSchema:
    if path is None:
        path = Path(os.getenv("UDF_SCHEMA_PATH", str(DEFAULT_SCHEMA_PATH)))
    return _load_schema_file(path)


UDF_SCHEMA = load_udf_schema()
ALLOWED_COLUMNS = UDF_SCHEMA.allowed_columns
ALLOWED_RELATION_TYPES = UDF_SCHEMA.allowed_relation_types
FIELD_CLASSIFICATION = UDF_SCHEMA.field_classification
