import json
import os
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


def _load_schema_file(
    path: Path,
) -> Tuple[Dict[str, Set[str]], Set[str], Dict[str, Dict[str, str]]]:
    if not path.exists():
        return DEFAULT_ALLOWED_COLUMNS, DEFAULT_ALLOWED_RELATION_TYPES, DEFAULT_FIELD_CLASSIFICATION
    data = json.loads(path.read_text(encoding="utf-8"))
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
    return allowed_columns, allowed_relations, field_classification


def load_udf_schema() -> Tuple[Dict[str, Set[str]], Set[str], Dict[str, Dict[str, str]]]:
    path = Path(os.getenv("UDF_SCHEMA_PATH", str(DEFAULT_SCHEMA_PATH)))
    return _load_schema_file(path)


ALLOWED_COLUMNS, ALLOWED_RELATION_TYPES, FIELD_CLASSIFICATION = load_udf_schema()
