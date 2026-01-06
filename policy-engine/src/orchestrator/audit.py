from datetime import datetime
from typing import Any, Dict


def append_audit(state: Dict[str, Any], node: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
    audit = state.get("audit_trail") or []
    audit.append(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "node": node,
            "action": action,
            "details": details,
        }
    )
    return {**state, "audit_trail": audit}
