from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from polisyos.runtime import append_audit as runtime_append_audit


def append_audit(state: Dict[str, Any], node: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
    audit = state.get("audit_trail") or []
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "node": node,
        "action": action,
        "details": details,
    }
    audit.append(record)
    run_id = state.get("run_id")
    runtime_base_dir = state.get("runtime_base_dir")
    if run_id:
        base_dir = Path(runtime_base_dir) if runtime_base_dir else Path("runs")
        runtime_append_audit(run_id=run_id, record=record, base_dir=base_dir)
    return {**state, "audit_trail": audit}
