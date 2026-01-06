NORMALIZATION_RULES = [
    {"pattern": r"\s+", "repl": "_"},
    {"pattern": r"[^a-zA-Z0-9_]", "repl": ""},
    {"pattern": r"_+", "repl": "_"},
]

RECONCILIATION_RULES = {
    "paid_tax": {"debit": "from_id", "credit": "to_id"},
    "transfer": {"debit": "from_id", "credit": "to_id"},
}

DEFAULT_RECONCILIATION_TOLERANCE = 1e-6
