"""Exercise the live port methods with isolated transport evidence, never a live fetch."""

import json
import sys
from pathlib import Path

from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionOwnerExecutionResult,
)
from tests.integration.core_runtime.test_acquisition_route_execution_binding import (
    _port_fixture,
    _route_closure,
)

removal = "--remove-reentry-property" in sys.argv
root = Path(__file__).parent / "raw" / ("port-removal-state" if removal else "port-probe-state")
port, observer, _ = _port_fixture(root)
if removal:
    # Leave result/refusal strings, DTOs and call sites intact; remove only enforcement.
    type(port)._raise_reentry_not_admitted = staticmethod(lambda: None)
closure = _route_closure()
result = port.execute(closure)
records = [{"method": "execute", "result": result.model_dump(mode="json"),
            "transport_calls": len(observer.calls)}]
positive = AcquisitionOwnerExecutionResult(
    disposition="world_committed",
    owner_receipt_refs=("sha256:" + "a" * 64,),
    admitted_observation_delta=1,
    overlay_admission_receipt_ref="sha256:" + "b" * 64,
    post_epoch_event_ref="sha256:" + "c" * 64,
)
for label, operation in (
    ("reenter_quarantined", lambda: port.reenter(closure, result)),
    ("resume_reentry", lambda: port.resume_reentry(closure, result.owner_receipt_refs)),
    ("reenter_shape_valid_positive", lambda: port.reenter(closure, positive)),
):
    try:
        value = operation()
        records.append({"method": label, "returned": value})
    except Exception as exc:
        records.append({"method": label, "error_type": type(exc).__name__,
                        "error": str(exc), "code": getattr(exc, "code", None)})
print(json.dumps({"claim": "actual production-port refusal after isolated transport",
                  "in_memory_removal": removal,
                  "authority": "behavioral_fixture_not_production",
                  "boundary": "No real transport, live dataset, appointment or positive admission is claimed.",
                  "records": records}, indent=2))
assert result.disposition == "quarantined_no_growth"
assert result.admitted_observation_delta == 0
assert all(row.get("code") == "acquisition_live_evidence_not_admitted"
           for row in records[1:])
