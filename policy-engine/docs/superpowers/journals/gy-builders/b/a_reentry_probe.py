"""Independent A review witness: requested-use distinction reaches the re-entry port."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path.cwd() / "tests"))

from unit.fabric.test_non_data_acquisition import CandidateOwner, candidate_request, make_runtime


class ObservingOwner(CandidateOwner):
    """Record actual re-entry inputs without importing runtime decision logic."""

    def __init__(self):
        self.inputs = []

    def reenter(self, **kwargs):
        self.inputs.append(json.dumps(kwargs, sort_keys=True, default=str))
        return super().reenter(**kwargs)


if __name__ == "__main__":
    raw = Path("docs/superpowers/journals/gy-builders/b/raw")
    raw.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=raw) as directory:
        module, _, runtime = make_runtime(Path(directory))
        observer = ObservingOwner()
        runtime.demanding_owner = observer
        narrow = candidate_request(module, runtime)
        broad = narrow.model_copy(update={"requested_use": narrow.requested_use.model_copy(
            update={"purpose_ref": "purpose:research"}
        )})
        first = runtime.acquire(narrow, at=datetime(2026, 9, 10, tzinfo=UTC))
        cut = len(observer.inputs)
        second = runtime.acquire(broad, at=datetime(2026, 9, 10, tzinfo=UTC))
        narrow_inputs, broad_inputs = observer.inputs[:cut], observer.inputs[cut:]
        sys.stdout.write(json.dumps({
            "narrow_purpose": narrow.requested_use.purpose_ref,
            "broad_purpose": broad.requested_use.purpose_ref,
            "narrow_result": first.resolution_state,
            "broad_result": second.resolution_state,
            "same_reentry_inputs": narrow_inputs == broad_inputs,
            "narrow_input_hashes": [hashlib.sha256(item.encode()).hexdigest() for item in narrow_inputs],
            "broad_input_hashes": [hashlib.sha256(item.encode()).hexdigest() for item in broad_inputs],
        }, indent=2) + "\n")
