"""Real process/CAS driver: an infinite duplicate producer cooperates per yield."""

import json
import sys
import time
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair

store = FileSystemCAS(Path(sys.argv[1]), ownership_enforced=False)
ref = store.put_bytes(
    b"infinite duplicate intake", PutOptions(kind="test", media_type="text/plain")
)
consumed = 0
item = ref if sys.argv[2] == "verify" else ref.artifact_id


def source():
    global consumed
    consumed += 1
    yield item
    while True:
        time.sleep(0.01)
        consumed += 1
        yield item


deadline = time.monotonic() + 0.04
kwargs = {"artifact_ids": source(), "max_workers": 1, "pending_window": 1, "deadline": deadline}
if sys.argv[2] == "verify":
    report = store.verify_all_signatures(Ed25519Verifier(), **kwargs)
else:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    report = store.sign_all_artifacts(signer, **kwargs)
print(
    json.dumps(
        {
            "state": report.state,
            "abort_reason": report.abort_reason,
            "admitted": report.admitted,
            "finished": report.finished,
            "inventory_exhausted": report.inventory_exhausted,
            "consumed": consumed,
        }
    )
)
