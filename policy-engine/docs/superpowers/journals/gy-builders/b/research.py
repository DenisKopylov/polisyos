"""Recompute CR1 source denominator and execute existing persistence seams."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import polisyos.runtime.http.services.control  # noqa: F401 - initialize the composition root
from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore


def main() -> None:
    """Print the complete census and real owner observations."""
    root = Path.cwd()
    source = root / "src"
    first = {p.relative_to(root).as_posix() for p in source.rglob("*.py")}
    second = {
        (Path(directory) / name).relative_to(root).as_posix()
        for directory, _, names in os.walk(source)
        for name in names
        if name.endswith(".py")
    }
    assert first == second
    symbols = (
        "AdaptationTransitionRequest", "AdaptationDecisionRecord",
        "RestartEvidenceRecord", "KPIControlStateSnapshot",
    )
    hits = {symbol: [] for symbol in symbols}
    unreadable = []
    for name in sorted(first):
        try:
            text = (root / name).read_text()
        except (OSError, UnicodeError):
            unreadable.append(name)
            continue
        for symbol in symbols:
            if symbol in text:
                hits[symbol].append(name)
    print(json.dumps({"denominator_path": "src/**/*.py", "rglob_count": len(first),
                      "os_walk_count": len(second), "identity_sets_equal": first == second,
                      "unreadable_ambiguous": unreadable, "symbol_matches": hits}, indent=2))
    scratch = root / "docs/superpowers/journals/gy-builders/b/raw"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        work = Path(directory)
        store = ControlPlaneStore(backend="sqlite", sqlite_path=work / "control.sqlite")
        submitted = store.enqueue_outbox_event(topic="cr1-research", event_key="same",
                                                payload={"request": "one"})
        reopened = ControlPlaneStore(backend="sqlite", sqlite_path=work / "control.sqlite")
        duplicate = reopened.enqueue_outbox_event(topic="cr1-research", event_key="same",
                                                  payload={"request": "one"})
        collision = reopened.enqueue_outbox_event(topic="cr1-research", event_key="same",
                                                  payload={"request": "DIFFERENT"})
        assert submitted.event_id == duplicate.event_id == collision.event_id
        assert duplicate.payload == {"request": "one"}
        reopened.mark_outbox_published(event_id=duplicate.event_id)
        final = store.get_outbox_event(submitted.event_id)
        assert final is not None and final.state == "published"
        args = dict(tenant_id="research", method="TEST", path="/cr1", idempotency_key="one",
                    request_hash="same")
        reservation = RuntimeIdempotencyStore(root=work / "idempotency").begin(**args)[0]
        restarted_reservation = RuntimeIdempotencyStore(root=work / "idempotency").begin(**args)[0]
        assert reservation == restarted_reservation == "started"
        print(json.dumps({"control_store_reopen_duplicate_same_identity": True,
                          "control_store_payload_collision_returns_existing": True,
                          "control_store_checkpoint_reopened": final.state,
                          "http_pending_reservation_process_local": True}, indent=2))


if __name__ == "__main__":
    main()
