"""Scratch-only F1 falsifiers and actual durable discovery execution readback."""

from __future__ import annotations

import hashlib
import json
import contextlib
import uuid
from collections import Counter
from pathlib import Path

import pytest

from tools.quality.validation import check_layer3_workflow_failure_authority as owner

ROOT = Path.cwd()


def _request_existing_discovery(monkeypatch):
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    async def launch_existing_workflow(self, request, **kwargs):
        roots = [
            identity
            for identity in self._artifact_store.iter_artifact_ids()
            if self._artifact_store.get_manifest(identity).kind
            == "workflow.failure.authority.root"
        ]
        assert len(roots) == 1
        return self.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": str(roots[0])},
                params={
                    "control_plane_transition": "legacy_shadow",
                    "workflow_id": "scientist_discovery",
                },
            ),
            **kwargs,
        )

    monkeypatch.setattr(ControlPlaneService, "launch_nl_run", launch_existing_workflow)


def _capture_complete_execution(monkeypatch, captures):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.executor import WorkflowReport
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    actual = owner._production_loop_fields

    def inspect(**kwargs):
        service = kwargs["service"]
        store = service._artifact_store
        identities = store.iter_artifact_ids()
        independent = {
            "sha256:" + path.name.removesuffix(".manifest.json")
            for path in store.base.rglob("*.manifest.json")
        }
        assert set(map(str, identities)) == independent
        records = []
        for identity in identities:
            manifest = store.get_manifest(identity)
            if manifest.kind not in {"scientist.workflow_report", "scientist.workflow_spec"}:
                continue
            raw = store.get_bytes(identity)
            assert store.verify(identity).ok
            assert hashlib.sha256(raw).hexdigest() == identity.hex
            payload = from_canonical_bytes(raw)
            model = WorkflowReport if manifest.kind == "scientist.workflow_report" else WorkflowSpec
            typed = model.model_validate(payload)
            records.append({
                "ref": str(identity), "kind": manifest.kind,
                "schema": manifest.artifact_schema.model_dump(mode="json"),
                "payload": typed.model_dump(mode="json"),
            })
        captures.append({
            "scenario": kwargs["scenario"],
            "run_id": kwargs["response"].run_id,
            "complete_cas_manifest_denominator": len(identities),
            "independent_sidecar_denominator": len(independent),
            "workflow_records": records,
        })
        return actual(**kwargs)

    monkeypatch.setattr(owner, "_production_loop_fields", inspect)


def _changes(before, after, path="$"):
    """Preserve absence versus explicit null, including all list/map members."""
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        rows = []
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                rows.append({
                    "path": f"{path}.{key}",
                    "before_present": key in before,
                    "after_present": key in after,
                    **({"before": before[key]} if key in before else {}),
                    **({"after": after[key]} if key in after else {}),
                })
            else:
                rows.extend(_changes(before[key], after[key], f"{path}.{key}"))
        return rows
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        return [item for index, pair in enumerate(zip(before, after, strict=True))
                for item in _changes(*pair, f"{path}[{index}]")]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def test_canonical_f1_recomputes_both_scenarios():
    payloads = owner.build_live_proof_payloads(ROOT)
    issues = []
    owner._validate_proof_payload(payloads[owner.PROOF_PATH], issues)
    assert issues == []


def test_removed_real_execution_cannot_keep_candidate_proof(monkeypatch):
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    _request_existing_discovery(monkeypatch)
    monkeypatch.setattr(ControlPlaneService, "_run_legacy_scientist_workflow", lambda *args: None)
    with pytest.raises(Exception, match="workflow.*(report|execution)"):
        proof = owner._run_durable_authority_surface_proof("legacy_shadow_candidate")
        print("REMOVED_REAL_EXECUTION_PROOF", json.dumps(proof, sort_keys=True))


def test_actual_discovery_report_and_repeat_drift(monkeypatch):
    from polisyos.scientist.orchestration.workflows.discovery import discovery_workflow_spec

    _request_existing_discovery(monkeypatch)
    captures = []
    _capture_complete_execution(monkeypatch, captures)
    proofs = [owner._run_durable_authority_surface_proof("legacy_shadow_candidate") for _ in range(2)]
    expected = discovery_workflow_spec()
    for capture, proof in zip(captures, proofs, strict=True):
        print("COMPLETE_EXECUTION_READBACK", json.dumps(capture, sort_keys=True))
        reports = [record for record in capture["workflow_records"] if record["kind"] == "scientist.workflow_report"]
        specs = [record for record in capture["workflow_records"] if record["kind"] == "scientist.workflow_spec"]
        assert len(reports) == len(specs) == 1
        report = reports[0]["payload"]
        assert specs[0]["payload"] == expected.model_dump(mode="json")
        assert report["run_id"] == capture["run_id"] == proof["run_id"]
        assert report["workflow_id"] == expected.workflow_id
        assert Counter((row["alias"], row["node_id"]) for row in report["nodes"]) == Counter((row.alias, str(row.node_id)) for row in expected.nodes)
        assert report["status"] == "ok"
        assert proof["authority_result"] == "candidate_only"
    by_kind = [{record["kind"]: record for record in capture["workflow_records"]}
               for capture in captures]
    print("COMPLETE_REPORT_DELTA", json.dumps(_changes(*by_kind), sort_keys=True))
    print("COMPLETE_PROOF_DELTA", json.dumps(_changes(proofs[0], proofs[1]), sort_keys=True))


def test_real_clock_and_identity_drift(monkeypatch):
    actual_patch = owner.patch
    actual_uuid4 = uuid.uuid4

    def real_clock_patch(target, *args, **kwargs):
        if target == "polisyos.runtime.http.services.control_plane_store._utc_now":
            return contextlib.nullcontext()
        return actual_patch(target, *args, **kwargs)

    monkeypatch.setattr(owner, "patch", real_clock_patch)
    monkeypatch.setattr(owner, "_deterministic_uuid_sequence", lambda seed: iter(actual_uuid4, None))
    test_actual_discovery_report_and_repeat_drift(monkeypatch)
