from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.services.adapters.core_run import load_core_run

if TYPE_CHECKING:
    from pathlib import Path


def _bootstrap_registry_bundle(store: FileSystemCAS):
    slot_ref = store.put_json(
        {"slots": {}},
        PutOptions(kind="core.registry.slots", media_type="application/json"),
    )
    merge_ref = store.put_json(
        {"merge_rules": {}},
        PutOptions(kind="core.registry.merge", media_type="application/json"),
    )
    con_ref = store.put_json(
        {"constraints": {}},
        PutOptions(kind="core.registry.constraints", media_type="application/json"),
    )
    mech_ref = store.put_json(
        {"mechanisms": {}},
        PutOptions(kind="core.registry.mechanisms", media_type="application/json"),
    )
    trust_ref = store.put_json(
        {"trust_policies": {}},
        PutOptions(kind="core.registry.trust", media_type="application/json"),
    )

    bundle_payload = {
        "slot_registry": slot_ref.model_dump(),
        "merge_registry": merge_ref.model_dump(),
        "constraint_registry": con_ref.model_dump(),
        "mechanism_registry": mech_ref.model_dump(),
        "trust_registry": trust_ref.model_dump(),
    }
    bundle_ref = store.put_json(
        bundle_payload,
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    return bundle_ref


def test_run_context_emits_trace_and_writes_run_manifest(
    store: FileSystemCAS, tmp_path: Path, producer, env_info
):
    bundle_ref = _bootstrap_registry_bundle(store)

    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=tmp_path / "runs" / "R_test",
    )

    inp = store.put_json(
        {"policy": "noop"},
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
    )
    out = store.put_json(
        {"result": "ok"},
        PutOptions(kind="core.output", media_type="application/json"),
    )

    ctx.add_input(inp)
    ctx.add_output(out)

    run_ref = ctx.finalize(status="ok")

    assert store.has(run_ref.artifact_id)
    rep = store.verify(run_ref.artifact_id)
    assert rep.ok is True

    run_manifest = store.get_bytes(run_ref.artifact_id).decode("utf-8")
    assert '"status":"ok"' in run_manifest
    assert str(bundle_ref.artifact_id) in run_manifest
    assert str(inp.artifact_id) in run_manifest
    assert str(out.artifact_id) in run_manifest
    assert '"trace_ref"' in run_manifest


def test_run_context_finalize_recovery_repairs_pending_manifest(
    store: FileSystemCAS,
    tmp_path: Path,
    producer,
    env_info,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = tmp_path / "runs" / "R_recover"

    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        producer=producer,
        env=env_info,
        run_dir=run_dir,
    )
    out = store.put_json(
        {"result": "ok"},
        PutOptions(kind="core.output", media_type="application/json"),
    )
    ctx.add_output(out)

    original_put_json = store.put_json
    should_fail = True

    def _failing_put_json(obj, opts=None, canon_spec=None):
        nonlocal should_fail
        kind = getattr(opts, "kind", None)
        if should_fail and kind == "core.run_manifest":
            should_fail = False
            raise OSError("simulated finalize crash")
        return original_put_json(obj, opts, canon_spec=canon_spec)

    monkeypatch.setattr(store, "put_json", _failing_put_json)

    with pytest.raises(OSError, match="simulated finalize crash"):
        ctx.finalize(status="ok")

    journal_path = run_dir / ".finalize-journal.json"
    assert journal_path.exists()

    monkeypatch.setattr(store, "put_json", original_put_json)
    loaded = load_core_run(store=store, run_dir=run_dir)

    assert loaded is not None
    assert loaded.status == "ok"
    assert loaded.manifest_ref is not None
    assert journal_path.exists() is False
    assert "RUN_FINALIZED" in (run_dir / "trace.jsonl").read_text(encoding="utf-8")
