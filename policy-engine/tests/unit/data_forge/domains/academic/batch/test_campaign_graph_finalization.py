"""Actual campaign checkpoint to privately built candidate graph publication."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest


def _writer():
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    return SafeJsonWriter("SYNTHETIC_TEST_CREDENTIAL_NOT_USED_FOR_NETWORK")


def _input_projection(root: Path) -> dict[str, str]:
    """Enumerate all immutable source, attempt and completed-work artifacts."""
    paths = [root / "plan.json", root / "checkpoint.sqlite3"]
    for directory in ("inputs", "intents", "attempts", "works", "strangles"):
        paths.extend((root / directory).rglob("*.json"))
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file()}


def _candidate_checkpoint(root: Path, count: int = 3):
    """Use real extraction and durable work owners with marked synthetic replies."""
    from tests.unit.data_forge.domains.academic.batch.test_reextraction_campaign import (
        _owner,
        _plan,
        _SyntheticTransport,
        _work,
    )

    owner = _owner()
    works = [_work(index) for index in range(count)]
    plan = _plan(owner, works, max_attempts=count * 3)
    transport = _SyntheticTransport()
    result = asyncio.run(owner.run_campaign(
        plan, works=iter(works), output_root=root, client_factory=transport.bind,
        safe_write_json=_writer(),
    ))
    assert result["works"] == {"complete": count}
    assert result["outcomes"] == {"extracted": count}
    return plan, transport


def _database(root: Path, packet: dict) -> Path:
    paths = [root / item["path"] for item in packet["artifacts"]
             if item["path"].endswith(".duckdb")]
    assert len(paths) == 1
    return paths[0]


def test_graph_finalizer_refuses_incomplete_checkpoint_before_build(tmp_path: Path) -> None:
    """Registered source presence cannot stand in for a completed campaign."""
    from polisyos.data_forge.domains.academic.batch import pipeline
    from tests.unit.data_forge.domains.academic.batch.test_reextraction_campaign import (
        _owner,
        _plan,
        _work,
    )

    owner = _owner()
    plan = _plan(owner)
    root = tmp_path / "campaign"
    with owner.CampaignCheckpoint(root, plan, _writer()) as checkpoint:
        checkpoint.prepare_inputs([_work()])
    with pytest.raises(ValueError, match="campaign_graph_inputs_incomplete"):
        pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    assert not (root / "graph-builds").exists()
    assert not (root / "graphs").exists()


def test_graph_finalizer_preserves_all_outcome_dispositions(tmp_path: Path) -> None:
    """Completed failed work stays visibly failed beside a valid empty graph."""
    from polisyos.data_forge.domains.academic.batch import pipeline
    from tests.unit.data_forge.domains.academic.batch.test_reextraction_campaign import (
        _owner,
        _plan,
        _work,
    )

    owner = _owner()
    works = [_work(i) for i in range(2)]
    plan = _plan(owner, works)
    root = tmp_path / "campaign"
    with owner.CampaignCheckpoint(root, plan, _writer()) as checkpoint:
        checkpoint.prepare_inputs(works)
        for work, outcome in zip(works, ("provider_failed", "screening_rejected"), strict=True):
            checkpoint.commit_work(checkpoint.register_work(work), status=outcome, record=None)
    ref = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    packet = pipeline.resolve_extraction_campaign_graph(plan, root, ref)
    assert packet["synthetic"] is True
    assert packet["scope"] == "candidate_only"
    assert packet["completed_input_count"] == 2
    assert packet["work_outcomes"] == {"provider_failed": 1, "screening_rejected": 1}
    assert packet["graph_metrics"]["works"] == 0
    assert packet["graph_metrics"]["family_edges"] == 0
    assert packet["graph_metrics"]["contested_edges"] == 0


def test_actual_extraction_graph_historical_replay_and_complete_artifact_refusal(
    tmp_path: Path, monkeypatch,
) -> None:
    """Current graph construction consumes intact old outputs, never new API calls."""
    import duckdb

    from polisyos.data_forge.domains.academic.batch import pipeline
    from polisyos.data_forge.domains.academic.batch import reextraction_campaign as owner
    from polisyos.data_forge.kernel.pipeline.manifests import ArtifactRef

    root = tmp_path / "campaign"
    plan, transport = _candidate_checkpoint(root)
    original = _input_projection(root)
    calls = len(transport.calls)
    monkeypatch.setattr(owner, "campaign_owner_projection", lambda: {"content_hash": "changed"})
    ref = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    packet = pipeline.resolve_extraction_campaign_graph(plan, root, ref)
    assert packet["input_mode"] == "historical_source_epoch"
    assert packet["input_execution_epoch"] == "v1"
    assert packet["input_owner_source_hash"] == plan.owner_source_hash
    assert packet["synthetic"] is True
    assert packet["strangle_receipt"]["default_flipped"] is True
    assert packet["strangle_receipt"]["predicate_posture"] == "recomputed"
    assert packet["strangle_receipt"]["migration_equivalence"] == "not_established_by_this_run"
    assert packet["graph_metrics"]["works"] == 3
    assert packet["graph_metrics"]["raw_claims"] == 3
    assert packet["graph_metrics"]["claims"] == 0
    assert packet["graph_metrics"]["skg_edges"] == 0
    assert len(transport.calls) == calls
    assert _input_projection(root) == original
    assert all(value["synthetic"] is True and value["authority"] == "candidate_only"
               for value in packet["staging_usage"].values())
    with duckdb.connect(str(_database(root, packet)), read_only=True) as con:
        assert con.execute("SELECT id FROM ac_works ORDER BY id").fetchall() == [
            (f"synthetic:{index}",) for index in range(3)
        ]
        assert con.execute("SELECT synthetic FROM ac_causal_claims_raw").fetchall() == [(True,)] * 3
    manifest_path = root / ref.path
    saved = manifest_path.read_bytes()
    for mutation in ("missing", "novel", "duplicate", "strangle"):
        mutant = json.loads(saved)
        if mutation == "missing":
            mutant["artifacts"].pop()
        elif mutation == "novel":
            mutant["artifacts"].append({"path": "novel.sqlite", "sha256": "0" * 64})
        elif mutation == "duplicate":
            mutant["artifacts"].append(dict(mutant["artifacts"][0]))
        else:
            mutant["strangle_receipt"]["default_flipped"] = False
        raw = json.dumps(mutant).encode()
        manifest_path.write_bytes(raw)
        mutated_ref = ArtifactRef(path=ref.path, sha256=hashlib.sha256(raw).hexdigest())
        with pytest.raises(ValueError, match=r"campaign_graph_(artifact_membership|manifest_artifact_identity|strangle_recomputation)_mismatch"):
            pipeline.resolve_extraction_campaign_graph(plan, root, mutated_ref)
    manifest_path.write_bytes(saved)
    database = _database(root, packet)
    with database.open("ab") as stream:
        stream.write(b"synthetic:corrupt_saved_artifact")
    with pytest.raises(ValueError, match="campaign_graph_artifact_hash_mismatch"):
        pipeline.resolve_extraction_campaign_graph(plan, root, ref)


def test_completed_envelope_disk_refusal_precedes_publication(tmp_path: Path) -> None:
    """Account actual serialized envelope bytes alongside every private output."""
    from polisyos.data_forge.domains.academic.batch import pipeline
    from polisyos.data_forge.domains.academic.batch._graph_staging import (
        GraphCapacityError,
        GraphCapacityLimits,
    )

    root = tmp_path / "campaign"
    plan, transport = _candidate_checkpoint(root, 1)
    original = _input_projection(root)
    writer = _writer()
    valid_ref = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=writer)
    valid = pipeline.resolve_extraction_campaign_graph(plan, root, valid_ref)
    assert valid["graph_metrics"]["raw_claims"] == 1
    assert valid["synthetic"] is True
    build = root / "graph-builds" / Path(valid_ref.path).stem
    actual_bytes = sum(path.stat().st_size for path in build.rglob("*") if path.is_file())
    limit = actual_bytes * 4
    completed_before = {path.name for path in (root / "graphs").iterdir()}

    def padded_writer(path: Path, payload: object) -> None:
        writer(path, payload)
        # Valid JSON and every marker remain; actual codec output exceeds the cap.
        with path.open("ab") as stream:
            stream.write(b" " * (limit * 2))

    with pytest.raises(GraphCapacityError, match="max_disk_bytes"):
        pipeline.finalize_extraction_campaign_graph(
            plan, root, safe_write_json=padded_writer,
            capacity_limits=replace(GraphCapacityLimits(), max_disk_bytes=limit),
        )
    assert {path.name for path in (root / "graphs").iterdir()} == completed_before
    assert _input_projection(root) == original
    assert len(transport.calls) == 3
    bounded_ref = pipeline.finalize_extraction_campaign_graph(
        plan, root, safe_write_json=writer,
        capacity_limits=replace(GraphCapacityLimits(), max_disk_bytes=limit),
    )
    assert pipeline.resolve_extraction_campaign_graph(plan, root, bounded_ref)["synthetic"] is True
    bounded_build = root / "graph-builds" / Path(bounded_ref.path).stem
    with (bounded_build / "synthetic-extra-output.json").open("wb") as stream:
        stream.write(b'{"synthetic":true,"scope":"candidate_only"}')
        stream.write(b" " * (limit * 2))
    with pytest.raises(GraphCapacityError, match="max_disk_bytes"):
        pipeline.resolve_extraction_campaign_graph(plan, root, bounded_ref)


def test_capacity_refusal_preserves_inputs_and_publishes_no_graph(tmp_path: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import pipeline
    from polisyos.data_forge.domains.academic.batch._graph_staging import (
        GraphCapacityError,
        GraphCapacityLimits,
    )

    root = tmp_path / "campaign"
    plan, transport = _candidate_checkpoint(root, 1)
    original = _input_projection(root)
    calls = len(transport.calls)
    with pytest.raises(GraphCapacityError, match="max_record_bytes"):
        pipeline.finalize_extraction_campaign_graph(
            plan, root, safe_write_json=_writer(),
            capacity_limits=replace(GraphCapacityLimits(), max_record_bytes=10),
        )
    assert _input_projection(root) == original
    assert len(transport.calls) == calls
    assert not (root / "graphs").exists()
    ref = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    assert pipeline.resolve_extraction_campaign_graph(plan, root, ref)["graph_metrics"]["works"] == 1



def test_raw_finalized_graph_retains_candidates_until_adjudicated(tmp_path: Path) -> None:
    """A raw candidate graph currently supplies no forwardable L2 reference."""
    from polisyos.data_forge.domains.academic.batch import pipeline
    from polisyos.runtime.quality import credal_reference as credal

    root = tmp_path / "campaign"
    plan, _ = _candidate_checkpoint(root, 1)
    ref = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    packet = pipeline.resolve_extraction_campaign_graph(plan, root, ref)
    link = tmp_path / "consumer" / credal.DEFAULT_L2_SCHOLAR_KG_PATH
    link.parent.mkdir(parents=True)
    link.symlink_to(_database(root, packet))
    edges = tuple(credal._iter_l2_edges(tmp_path / "consumer"))
    assert packet["graph_metrics"]["raw_claims"] == 1
    assert packet["graph_metrics"]["claims"] == 0
    assert packet["graph_metrics"]["skg_edges"] == 0
    assert edges == ()
    print(json.dumps({"synthetic": True, "actual_raw_claims": 1,
                      "actual_forwardable_l2_identities": [],
                      "governed_forwarding": "not_established",
                      "missing_input": "independently_admitted_claim_adjudication",
                      "synthetic_specific_refusal_proven_by_this_case": False}))


def test_graph_owner_signed_synthetic_reassembly_remains_governed(tmp_path, monkeypatch) -> None:
    """Existing genuine synthetic adjudication exercises both changed graph owners."""
    from tests.unit.data_forge.domains.academic.batch.test_abstract_reextraction import (
        test_removal_of_synthetic_authority_refusal_breaks_downstream_gate,
        test_signed_synthetic_graph_reassembly_preserves_source_limit_into_cg2,
    )

    test_signed_synthetic_graph_reassembly_preserves_source_limit_into_cg2(tmp_path / "control")
    test_removal_of_synthetic_authority_refusal_breaks_downstream_gate(
        tmp_path / "removal", monkeypatch,
    )


def _interrupted_finalizer(root: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import graph_builder, pipeline
    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import CampaignPlan

    plan = CampaignPlan(**json.loads((root / "plan.json").read_bytes())["plan"])
    original_load = graph_builder.load_graph

    def load_then_wait(*args, **kwargs):
        result = original_load(*args, **kwargs)
        _writer()(root / "synthetic-graph-loaded.json", {"synthetic": True, "state": "loaded"})
        while True:
            time.sleep(0.05)
        return result

    graph_builder.load_graph = load_then_wait
    pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())


def test_actual_sigkill_finalization_rebuilds_without_repeating_extraction(tmp_path: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import pipeline
    from tests.unit.data_forge.domains.academic.batch.test_graph_capacity import (
        complete_database_snapshot,
    )

    root = tmp_path / "campaign"
    plan, transport = _candidate_checkpoint(root, 2)
    original = _input_projection(root)
    calls = len(transport.calls)
    command = [sys.executable, "-m",
               "tests.unit.data_forge.domains.academic.batch.test_campaign_graph_finalization",
               "--interrupt-finalizer", str(root)]
    child = subprocess.Popen(command, env=os.environ.copy(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    ready = root / "synthetic-graph-loaded.json"
    deadline = time.monotonic() + 120
    try:
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        if not ready.exists() and child.poll() is not None:
            stdout, stderr = child.communicate(timeout=10)
            raise AssertionError("actual_graph_load_child_exited:" + json.dumps({
                "synthetic": True, "returncode": child.returncode, "stdout": stdout,
                "stderr": stderr, "module": __name__,
            }))
        assert ready.exists(), "actual_graph_load_boundary_not_reached"
        assert not (root / "graphs").exists()
        child.kill()
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == -signal.SIGKILL, (stdout, stderr)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)
    assert _input_projection(root) == original
    first = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    first_packet = pipeline.resolve_extraction_campaign_graph(plan, root, first)
    second = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    second_packet = pipeline.resolve_extraction_campaign_graph(plan, root, second)
    assert complete_database_snapshot(_database(root, first_packet)) == complete_database_snapshot(
        _database(root, second_packet),
    )
    assert _input_projection(root) == original
    assert len(transport.calls) == calls
    print(json.dumps({"synthetic": True, "child_returncode": child.returncode,
                      "completed_input_identity_hashes": original,
                      "provider_calls_before_after": [calls, len(transport.calls)],
                      "completed_graphs": [first.path, second.path],
                      "complete_database_identity_values_equal": True}))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--interrupt-finalizer":
        _interrupted_finalizer(Path(sys.argv[2]))
    else:
        raise SystemExit("unsupported synthetic test invocation")
