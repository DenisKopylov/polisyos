from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.run.context import RunContext


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
