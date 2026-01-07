from __future__ import annotations

from polisyos.ir.migrations.base import register_migration

IR_CURRENT_VERSION = "1.0"


@register_migration("0.9", "1.0")
def migrate_policy_ir_0_9_to_1_0(data: dict) -> dict:
    if "projectName" in data and "project_name" not in data:
        data["project_name"] = data.pop("projectName")
    if "globalConstraints" in data and "global_constraints" not in data:
        data["global_constraints"] = data.pop("globalConstraints")
    return data
