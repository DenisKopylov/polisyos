#!/usr/bin/env python3
"""Validate Layer 2 S1 graded-outcome routing and canonical corpus wiring."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.assurance_case import (  # noqa: E402
    build_policy_design_case_profile,
    build_policy_intent_envelope,
)
from polisyos.runtime.quality.closeout_reader import (  # noqa: E402
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.graded_outcomes import (  # noqa: E402
    S1_GRADED_OUTCOME_SCHEMA_VERSION,
    GradedOutcomeDecision,
    GradedOutcomeEvidenceInput,
    GradedOutcomeInputError,
    compose_graded_outcome,
    graded_outcome_closeout_record,
)
from polisyos.runtime.quality.proving_ground.pinned_route_demand_home import (  # noqa: E402
    read_layer3_gx_pinned_case_id,
)
from polisyos.runtime.quality.projection_semantics import (  # noqa: E402
    build_policy_design_case_projection_contract_fixture,
)
from tools.quality.validation import build_policy_evidence_capability_index as builder  # noqa: E402
from tools.quality.validation import run_universal_outcome_corpus as w12d  # noqa: E402

DEFAULT_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json"
)
DEFAULT_SLICE_CELL_MATRIX_PATH = Path(
    "architecture/policy_design_case/layer2_slice_cell_matrix.toml"
)
DEFAULT_CORPUS_CASES_PATH = Path("tests/fixtures/universal-corpus/cases")
NOW = datetime(2026, 5, 30, tzinfo=UTC)


def validate_s1_graded_outcomes(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Validate S1 graded outcomes from manifest through canonical W12.D route.

    Args:
        repo_root: Repository root containing architecture manifests and corpus cases.

    Returns:
        JSON-compatible S1 readiness summary.

    Raises:
        ValueError: If any manifest, corpus, closeout, projection, or canonical route
            invariant fails.
    """

    root = Path(repo_root).resolve()
    manifest = _load_manifest(root)
    matrix = _load_toml(root / DEFAULT_SLICE_CELL_MATRIX_PATH)
    cases = _load_cases(root / DEFAULT_CORPUS_CASES_PATH)
    cases_by_id = {_case_id(case): case for case in cases}

    open_cell_count = int(matrix.get("open_cell_count_baseline") or 0)
    cells_closed = list(manifest.get("cells_closed") or [])
    _expect(open_cell_count == 17, "s1_open_cell_count_changed")
    _expect(cells_closed == [], "s1_manifest_closes_cells")
    _expect(_s1_assigned_cells(matrix) == [], "s1_slice_cell_assignment_present")

    limitation_case_ids = [
        _case_id(case)
        for case in cases
        if _expert_label(case) == "limitation_required"
    ]
    expected_limitation_ids = list(manifest["limitation_required_case_ids"])
    _expect(
        limitation_case_ids == expected_limitation_ids,
        "s1_limitation_case_ids_mismatch",
    )
    production_control_ids = list(manifest["production_strict_control_case_ids"])
    _expect(
        sorted(cases_by_id) == sorted(production_control_ids),
        "s1_production_control_ids_mismatch",
    )

    governed_decisions = [
        compose_graded_outcome(
            _input_for(cases_by_id[case_id], authority_level="governed")
        )
        for case_id in expected_limitation_ids
    ]
    _expect(
        all(decision.outcome == "publish_with_limitation" for decision in governed_decisions),
        "s1_governed_limitation_routing_failed",
    )
    production_decisions = [
        compose_graded_outcome(
            _input_for(cases_by_id[case_id], authority_level="production")
        )
        for case_id in production_control_ids
    ]
    _expect(
        all(decision.outcome == "typed_blocker" for decision in production_decisions),
        "s1_production_strictness_failed",
    )

    closeout_verdict = _closeout_verdict(governed_decisions)
    _expect(
        closeout_verdict["status"] == "closed_with_limitations",
        "s1_closeout_status_not_limited",
    )
    projection_audiences = _projection_audiences(closeout_verdict)
    canonical_status, closeout_honesty_rate = _canonical_route_status(root)
    _validate_missing_owner_negative_control(cases_by_id[expected_limitation_ids[0]])

    return {
        "status": "pass",
        "slice": "S1",
        "open_cell_count": open_cell_count,
        "cells_closed": cells_closed,
        "limitation_required_case_count": len(expected_limitation_ids),
        "governed_publish_with_limitation_count": sum(
            1
            for decision in governed_decisions
            if decision.outcome == "publish_with_limitation"
        ),
        "production_control_case_count": len(production_control_ids),
        "production_typed_blocker_count": sum(
            1 for decision in production_decisions if decision.outcome == "typed_blocker"
        ),
        "closeout_status": closeout_verdict["status"],
        "canonical_route_status": canonical_status,
        "projection_audiences_verified": projection_audiences,
        "closeout_honesty_rate": closeout_honesty_rate,
    }


def validate_fabricated_limitation_negative_control() -> None:
    """Raise when a fabricated limitation lacks proxy or partial evidence refs."""

    compose_graded_outcome(
        GradedOutcomeEvidenceInput(
            schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
            case_id="fabricated-limitation",
            claim_id="claim:fabricated",
            authority_level="governed",
            requested_outcome="publish_with_limitation",
            evidence_profile="partial_or_proxy",
            proxy_evidence_refs=(),
            partial_evidence_refs=(),
            limitation_reason_codes=("unsupported_limitation",),
            mandatory_gate_state="none",
            owner="team-evaluation",
            decision_owner_ref="review://layer2-s1/fabricated/governed-owner",
            authority_profile_ref="authority_profile.governed",
            review_refs=("review://layer2-s1/fabricated/limitation",),
            ttl_expires_at=datetime(2026, 6, 30, tzinfo=UTC),
            public_limitation_note="Unsupported limitation.",
            rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
        )
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the S1 validator CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the S1 validator CLI."""

    args = build_parser().parse_args(argv)
    try:
        summary = validate_s1_graded_outcomes(repo_root=args.repo_root)
    except Exception as exc:
        payload = {"status": "fail", "error": str(exc)}
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _load_manifest(repo_root: Path) -> dict[str, Any]:
    return _load_json(repo_root / DEFAULT_MANIFEST_PATH)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(case_path.read_text(encoding="utf-8"))
        for case_path in sorted(path.glob("*.json"))
    ]


def _input_for(
    case: Mapping[str, Any],
    *,
    authority_level: str,
) -> GradedOutcomeEvidenceInput:
    case_id = _case_id(case)
    return GradedOutcomeEvidenceInput(
        schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
        case_id=case_id,
        claim_id=_claim_id(case),
        authority_level=authority_level,
        requested_outcome="publish_with_limitation",
        evidence_profile="partial_or_proxy",
        proxy_evidence_refs=(f"corpus://{case_id}/proxy-evidence",),
        partial_evidence_refs=(f"corpus://{case_id}/partial-support",),
        limitation_reason_codes=("s1_manifest_limitation_required",),
        mandatory_gate_state="none",
        owner="team-evaluation",
        decision_owner_ref=f"review://layer2-s1/{case_id}/{authority_level}/owner",
        authority_profile_ref=f"authority_profile.{authority_level}",
        review_refs=(f"review://layer2-s1/{case_id}/{authority_level}/limitation",),
        ttl_expires_at=datetime(2026, 6, 30, tzinfo=UTC),
        public_limitation_note=(
            "S1 readiness validates publish-with-limitation over partial or proxy evidence."
        ),
        rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
    )


def _closeout_verdict(decisions: Sequence[GradedOutcomeDecision]) -> dict[str, Any]:
    closeout_record = graded_outcome_closeout_record(decisions, generated_at=NOW)
    module_records = _passing_w4_records()
    module_records["deficit_crosswalk"] = closeout_record
    return build_can_i_closeout_verdict(
        run_id="run-layer2-s1-readiness",
        module_records=module_records,
    )


def _projection_audiences(closeout_verdict: Mapping[str, Any]) -> list[str]:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=_policy_design_case(),
        closeout_verdict=closeout_verdict,
        audiences=("public", "reviewer", "expert"),
        generated_at=NOW,
    )
    _expect(fixture["status"] == "pass", "s1_projection_fixture_failed")
    verified: list[str] = []
    for audience in ("public", "reviewer", "expert"):
        projection = fixture["projections"][audience]
        truth = projection["closeout_truth"]
        gaps = projection["projection_gaps"]
        _expect(truth["limitation_codes"], f"s1_projection_{audience}_limitation_missing")
        _expect(
            any(gap["publication_effect"] == "publish_with_limitation" for gap in gaps),
            f"s1_projection_{audience}_gap_missing",
        )
        verified.append(audience)
    return verified


def _canonical_route_status(repo_root: Path) -> tuple[str, float]:
    case_path = (
        repo_root
        / DEFAULT_CORPUS_CASES_PATH
        / f"{read_layer3_gx_pinned_case_id(repo_root)}.json"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        index_dir = tmp / "capability-index"
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = builder.main(["--mode", "fixture", "--output-dir", str(index_dir)])
        _expect(exit_code == 0, "s1_capability_index_fixture_failed")
        report = w12d.run_w12d_universal_outcome_corpus(
            repo_root=repo_root,
            corpus_path=case_path,
            graph_output_dir=tmp / "graphs",
            hypothesis_ledger_output_dir=tmp / "ledgers",
            critic_report_output_dir=tmp / "critic-reports",
            mode="corpus_stub",
            producer_stub_dir=repo_root / "tests/fixtures/universal-corpus/producer_stubs",
            capability_index_path=index_dir / "capability_index_v1.duckdb",
        )
    case = report["cases"][0]
    s1 = case["s1_graded_outcome"]
    canonical_status = (
        "pass"
        if s1["outcome"] == "publish_with_limitation"
        and case["outcome"] == "publish-with-limitation"
        else "fail"
    )
    _expect(canonical_status == "pass", "s1_canonical_route_failed")
    return canonical_status, float(report["summary"]["closeout_honesty_rate"])


def _validate_missing_owner_negative_control(case: Mapping[str, Any]) -> None:
    try:
        compose_graded_outcome(
            _input_for(case, authority_level="governed").model_copy(
                update={"decision_owner_ref": None, "review_refs": ()}
            )
        )
    except GradedOutcomeInputError:
        return
    raise ValueError("s1_missing_decision_owner_not_rejected")


def _s1_assigned_cells(matrix: Mapping[str, Any]) -> list[str]:
    return [
        str(row.get("cell_ref"))
        for row in _sequence(matrix.get("assignment"))
        if isinstance(row, Mapping) and str(row.get("slice")) == "S1"
    ]


def _passing_w4_records() -> dict[str, dict[str, object]]:
    return {
        "i4_policy_design_case_graph": _w4_record(
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "portfolio_effective_support": _w4_record(
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue": _w4_record(
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "projection_consumer_contract": _w4_record(
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants": _w4_record("policyos.runtime.formal_invariants.v1"),
        "source_truth": _w4_record("policyos.runtime.source_truth.v1"),
        "conflict_materialization": _w4_record(
            "policyos.runtime.policy_design_case.conflict_materialization_closeout.v1"
        ),
        "attestation": _w4_record("policyos.runtime.attestation.v1"),
        "closeout_compatibility": _w4_record(
            "policyos.runtime.can_i_closeout_compatibility.v1"
        ),
        "semantic_binding": _w4_record("policyos.runtime.semantic_binding.v1"),
        "claim_registry": _w4_record("policyos.runtime.claim_registry.v1"),
        "pdc_record_family_status": _w4_record(
            "policyos.policy_design_case.record_family_coverage.v1"
        ),
        "projection_publication_state": _w4_record(
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_gate": _w4_record("policyos.runtime.run_cost_gate.v1"),
        "complexity_self_fmea": _w4_record(
            "policyos.runtime.run_cost_proportionality.v1"
        ),
        "audit_verifier_ingestion": _w4_record("policyos.runtime.audit_verifier.v1"),
        "prompt_tool_repair_fmea": _w4_record(
            "policyos.runtime.prompt_tool_repair_fmea.v1"
        ),
    }


def _w4_record(schema_version: str) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "status": "pass",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "layer2.s1.validator",
        "runtime_event_ref": "event://layer2-s1/validator",
        "cas_ref": "sha256:" + "a" * 64,
        "issues": [],
    }


def _policy_design_case() -> dict[str, object]:
    return build_policy_design_case_profile(
        case_id="pdc-layer2-s1",
        run_id="run-layer2-s1",
        job_id="job-layer2-s1",
        tenant_id="tenant-layer2-s1",
        effective_execution_profile="production",
        runtime_authority={
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "cas_ref": _sha("a"),
            "runtime_event_ref": "event://layer2-s1/profile",
            "same_input_closure_ref": _sha("b"),
            "effective_mode_ref": _sha("c"),
            "schema_compatibility_ref": _sha("d"),
        },
        capability_ledger={
            "schema_version": "policyos.runtime.policy_design_case.capability_ledger.v1",
            "ledger_ref": _sha("f"),
            "literature_evidence_required": True,
            "duties": [
                {
                    "capability": capability,
                    "state": "selected",
                    "owner": f"team-{capability}",
                    "evidence_ref": _sha(capability[0]),
                    "runtime_event_ref": f"event://layer2-s1/duty/{capability}",
                    "required": True,
                }
                for capability in (
                    "lex",
                    "fabric",
                    "scholar",
                    "foundry",
                    "scientist",
                    "compiler",
                    "review",
                    "publication",
                    "audit",
                )
            ],
        },
        intent_envelope=build_policy_intent_envelope(
            intent_id="intent-layer2-s1",
            run_id="run-layer2-s1",
            job_id="job-layer2-s1",
            tenant_id="tenant-layer2-s1",
            policy_problem="MSME credit access is constrained.",
            desired_outcome="Improve MSME survival.",
            proposed_intervention="Target credit guarantees to eligible MSMEs.",
            jurisdiction="UA",
            target_population="wartime MSMEs",
            policy_time="2026-05-30",
            data_time="2024-2026",
            requester_preferred_conclusion="expand credit guarantees",
            requested_authority_level="production",
            authoring_provenance={"capture_ref": _sha("e")},
        ),
        generated_at=NOW,
    )


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case.get("case_id") or case.get("id"))


def _claim_id(case: Mapping[str, Any]) -> str:
    claims = _sequence(_nested(case, ("claim_evidence_annotations", "claims")))
    for claim in claims:
        if isinstance(claim, Mapping) and claim.get("claim_id"):
            return str(claim["claim_id"])
    return f"claim:{_case_id(case)}:main"


def _expert_label(case: Mapping[str, Any]) -> str:
    return str(_nested(case, ("expert_adjudication", "case_label")) or "")


def _nested(mapping: Mapping[str, Any], path: Sequence[str]) -> object | None:
    current: object = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return ()


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _expect(condition: object, code: str) -> None:
    if not condition:
        raise ValueError(code)


if __name__ == "__main__":
    raise SystemExit(main())
