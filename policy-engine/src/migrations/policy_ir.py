from __future__ import annotations

from src.migrations.base import register_migration

POLICY_IR_CURRENT_VERSION = "1.0"


@register_migration("policy_ir", "0.9", "1.0")
def migrate_policy_ir_0_9_to_1_0(data: dict) -> dict:
    # Placeholder: apply structural fixes when 0.9 format is known.
    # For now, only normalize known top-level field names if present.
    if "projectName" in data and "project_name" not in data:
        data["project_name"] = data.pop("projectName")
    if "globalConstraints" in data and "global_constraints" not in data:
        data["global_constraints"] = data.pop("globalConstraints")
    return data
