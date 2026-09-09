"""Declared synthetic full-finalizer resource witness, never provider work."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

MODULE = "docs.superpowers.journals.corr-evidence.c1-capacity.graph_finalizer_profile"
SIZES = (100, 1000)


def source_work(index: int) -> dict:
    """Create one explicit synthetic input without corpus state."""
    return {"id": f"synthetic:graph-profile:{index:06d}", "title": "Constructed graph workload",
            "abstract": "Tax changes employment.", "year": 2024, "cited_by_count": 0,
            "doi": "", "synthetic": True}


def _frame_digest(size: int) -> str:
    digest = hashlib.sha256()
    for index in range(size):
        raw = json.dumps(source_work(index), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode()
        digest.update(("sha256:" + hashlib.sha256(raw).hexdigest() + "\n").encode())
    return "sha256:" + digest.hexdigest()


def _writer() -> SafeJsonWriter:
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

    return SafeJsonWriter("SYNTHETIC_PROFILE_NO_NETWORK_CREDENTIAL")



def _declaration() -> dict:
    path = Path(__file__).with_name("graph-resource-declaration-v3.json")
    declaration = json.loads(path.read_bytes())
    if (declaration["source_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            or declaration["synthetic"] is not True
            or declaration["frames"] != [{"input_count": size, "input_digest": _frame_digest(size)}
                                         for size in SIZES]):
        raise ValueError("graph_profile_declaration_mismatch")
    return declaration


def prepare(root: Path, size: int) -> None:
    from polisyos.data_forge.domains.academic.batch import reextraction_campaign as owner
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimOccurrenceVocabularyTransport,
        WorkRecord,
    )
    from polisyos.ir.analytics import VersionedClaimVocabularyEnvelope

    _declaration()
    if size not in SIZES:
        raise ValueError("graph_profile_undeclared_size")
    plan = owner.CampaignPlan(
        campaign_id=f"synthetic:graph-profile:{size}", synthetic=True,
        input_count=size, input_digest=_frame_digest(size),
        provider_profile_hash=owner._digest({"synthetic": True, "provider": "not_used"}),
        screening_model="synthetic:none", extraction_model="synthetic:none",
        concurrency=1, queue_capacity=1, max_attempts=1, max_attempts_per_phase=1,
        owner_source_hash=owner.campaign_owner_projection()["content_hash"],
    )
    with owner.CampaignCheckpoint(root, plan, _writer()) as checkpoint:
        checkpoint.prepare_inputs(source_work(i) for i in range(size))
        for index in range(size):
            work = source_work(index)
            occurrence = {"claim_id": "synthetic:claim:" + work["id"],
                          "cause": "tax_rate", "effect": "employment", "direction": "negative",
                          "mechanism": "", "synthetic": True,
                          "source_provenance": {"synthetic": True, "scope": "resource_fixture"}}
            record = WorkRecord(
                id=work["id"], title=work["title"], abstract=work["abstract"], year=2024,
                metadata={"synthetic": True, "scope": "resource_fixture_not_provider_output"},
                causal_claims=[ClaimOccurrenceVocabularyTransport(
                    occurrence=occurrence,
                    vocabulary=VersionedClaimVocabularyEnvelope(
                        cause="tax_rate", effect="employment", direction="negative", mechanism="",
                    ),
                )],
            )
            checkpoint.commit_work(checkpoint.register_work(work), status="extracted",
                                   record=record.model_dump(mode="json"))
        checkpoint.validate_complete_frame()
        if checkpoint.summary()["attempts"] != {}:
            raise ValueError("graph_profile_unexpected_provider_attempt")
    _writer()(root / "profile-input.json", {
        "synthetic": True, "scope": "synthetic_completed_work_fixture_no_provider_calls",
        "size": size, "input_digest": plan.input_digest,
        "plan_path": "plan.json",
        "plan_sha256": hashlib.sha256((root / "plan.json").read_bytes()).hexdigest(),
        "record_shape": "one_marked_raw_causal_occurrence_per_work_no_adjudication",
        "expected_admitted_claims": 0, "expected_admitted_edges": 0,
    })


def finalize(root: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import pipeline
    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import CampaignPlan

    plan = CampaignPlan(**json.loads((root / "plan.json").read_bytes())["plan"])
    ref = pipeline.finalize_extraction_campaign_graph(plan, root, safe_write_json=_writer())
    packet = pipeline.resolve_extraction_campaign_graph(plan, root, ref)
    if packet["graph_metrics"]["works"] != plan.input_count:
        raise ValueError("graph_profile_complete_work_denominator_mismatch")
    if packet["graph_metrics"]["claims"] != 0 or packet["graph_metrics"]["skg_edges"] != 0:
        raise ValueError("graph_profile_candidate_authority_leak")
    disk_bytes = 0
    enumerated: set[str] = set()
    owned_paths = (root / "graph-builds" / Path(ref.path).stem, root / ref.path)
    for owned in owned_paths:
        if owned.is_file():
            enumerated.add(owned.relative_to(root).as_posix())
            disk_bytes += owned.stat().st_size
            continue
        for current, _, filenames in os.walk(owned):
            for filename in filenames:
                path = Path(current) / filename
                enumerated.add(path.relative_to(root).as_posix())
                disk_bytes += path.stat().st_size
    independent = {path.relative_to(root).as_posix()
                   for owned in owned_paths
                   for path in ((owned,) if owned.is_file() else owned.rglob("*"))
                   if path.is_file()}
    if enumerated != independent:
        raise ValueError("graph_profile_artifact_identity_sets_disagree")
    _writer()(root / "profile-completed.json", {
        "synthetic": True, "scope": "candidate_only", "artifact_ref": asdict(ref),
        "completed_input_count": packet["completed_input_count"],
        "work_outcomes": packet["work_outcomes"], "graph_metrics": packet["graph_metrics"],
        "graph_file_denominator": len(enumerated),
        "graph_file_identity_digest": hashlib.sha256(
            "\n".join(sorted(enumerated)).encode(),
        ).hexdigest(),
        "independent_walk_rglob_identity_sets_equal": True, "graph_total_file_bytes": disk_bytes,
        "staging_usage": packet["staging_usage"],
    })


def profile(root: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import pipeline

    declaration = _declaration()
    with (root / "plan.json").open("rb") as stream:
        plan_raw = stream.read(8_388_609)
    if len(plan_raw) > 8_388_608:
        raise ValueError("graph_profile_plan_size_refused")
    plan = json.loads(plan_raw)["plan"]
    if (plan["synthetic"] is not True
            or {"input_count": plan["input_count"], "input_digest": plan["input_digest"]}
            not in declaration["frames"]):
        raise ValueError("graph_profile_input_frame_not_declared")
    before = pipeline.campaign_graph_owner_projection()
    telemetry = importlib.import_module(
        "docs.superpowers.journals.corr-evidence.c1-capacity.process_telemetry",
    )
    result = telemetry.profile_module(
        MODULE, ["finalize", str(root)], cwd=Path.cwd(), output_root=root / "profile-telemetry",
        limits=telemetry.ProfileLimits(
            max_wall_seconds=declaration["limits"]["max_wall_seconds_per_size"],
            max_rss_bytes=declaration["limits"]["max_rss_bytes"],
            max_disk_write_bytes=declaration["limits"]["max_disk_write_bytes"],
        ),
        synthetic=True,
    )
    after = pipeline.campaign_graph_owner_projection()
    result["graph_owner_projection_before"] = before["content_hash"]
    result["graph_owner_projection_after"] = after["content_hash"]
    result["complete_source_projections_equal"] = before == after
    _writer()(root / "profile-result.json", {
        "synthetic": True, "scope": "full_candidate_graph_finalizer",
        "input_declaration": "profile-input.json", "measurement": result,
        "extraction_and_checkpoint_preparation_timing_included": False,
        "held_corpus_or_signed_adjudication_scale_established": False,
    })
    print(json.dumps(result, sort_keys=True))  # noqa: T201 - bounded numeric measurement output
    if (result["status"] != "completed" or result["returncode"] != 0
            or before != after):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "profile", "finalize"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--size", type=int, choices=SIZES)
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.size is None:
            parser.error("prepare requires declared --size")
        prepare(args.root, args.size)
    else:
        {"profile": profile, "finalize": finalize}[args.mode](args.root)


if __name__ == "__main__":
    main()
