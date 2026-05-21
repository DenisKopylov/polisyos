# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID,
    validate_policy_design_case_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "policy_design_case"
README_PATH = FIXTURE_ROOT / "README.md"

CONTRACTS = {
    "runtime_assurance_profile": {
        "adr": "ADR-0156",
        "contract_name": "policy_design_case.runtime_assurance_profile.v1",
        "families": frozenset({"claim_argument_evidence_case.v1"}),
        "fixtures": {
            "runtime_assurance_profile_pass.json",
            "runtime_assurance_profile_static_inventory_rejected.json",
        },
    },
    "intent_capability_authority_profile": {
        "adr": "ADR-0157",
        "contract_name": "policy_design_case.intent_capability_authority_profile.v1",
        "families": frozenset(
            {
                "intent_authoring_and_capture_risk.v1",
                "capability_mode_and_fallback_selection.v1",
            }
        ),
        "fixtures": {
            "intent_capability_authority_profile_pass.json",
            "intent_capability_authority_profile_static_inventory_rejected.json",
        },
    },
    "concept_jurisdiction_spine": {
        "adr": "ADR-0158",
        "contract_name": "policy_design_case.concept_jurisdiction_spine.v1",
        "families": frozenset({"concept_and_jurisdiction_spine.v1"}),
        "fixtures": {
            "concept_jurisdiction_spine_pass.json",
            "concept_jurisdiction_spine_static_inventory_rejected.json",
        },
    },
    "producer_evidence_contracts": {
        "adr": "ADR-0159",
        "contract_name": "policy_design_case.producer_evidence_contracts.v1",
        "families": frozenset(
            {
                "legal_authority_and_competence.v1",
                "data_source_semantic_lineage.v1",
                "scholar_academic_evidence.v1",
            }
        ),
        "fixtures": {
            "producer_evidence_contracts_pass.json",
            "producer_evidence_contracts_static_inventory_rejected.json",
        },
    },
    "portfolio_synthesis_contract": {
        "adr": "ADR-0160",
        "contract_name": "policy_design_case.portfolio_synthesis_contract.v1",
        "families": frozenset({"evidence_portfolio_and_synthesis.v1"}),
        "fixtures": {
            "portfolio_synthesis_contract_pass.json",
            "portfolio_synthesis_contract_static_inventory_rejected.json",
        },
    },
    "claim_argument_closeout_gate": {
        "adr": "ADR-0161",
        "contract_name": "policy_design_case.claim_argument_closeout_gate.v1",
        "families": frozenset({"claim_argument_evidence_case.v1"}),
        "fixtures": {
            "claim_argument_closeout_gate_pass.json",
            "claim_argument_closeout_gate_static_inventory_rejected.json",
        },
    },
}

STATUS_TOKENS = frozenset({"pass", "rejected"})


def _read_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.relative_to(REPO_ROOT)} must be an object"
    return payload


def _fixture_status(path: Path) -> str:
    for token in STATUS_TOKENS:
        if path.stem.endswith(f"_{token}"):
            return token
    raise AssertionError(
        f"{path.relative_to(REPO_ROOT)} must end with one of: {sorted(STATUS_TOKENS)}"
    )


def test_phase_1_1_policy_design_case_contract_fixtures_are_frozen() -> None:
    assert README_PATH.is_file()
    readme = README_PATH.read_text(encoding="utf-8")

    for dir_name, contract in CONTRACTS.items():
        fixture_dir = FIXTURE_ROOT / dir_name
        assert fixture_dir.is_dir(), (
            f"missing fixture directory: {fixture_dir.relative_to(REPO_ROOT)}"
        )

        fixture_paths = sorted(fixture_dir.glob("*.json"))
        assert {path.name for path in fixture_paths} >= contract["fixtures"]

        seen_statuses: set[str] = set()
        for path in fixture_paths:
            status_from_name = _fixture_status(path)
            fixture = _read_fixture(path)
            seen_statuses.add(status_from_name)

            assert fixture["fixture_id"] == path.stem
            assert fixture["adr"] == contract["adr"]
            assert fixture["contract_name"] == contract["contract_name"]
            assert fixture["expected_status"] == status_from_name
            assert fixture["sdd_record_families"]
            assert set(fixture["sdd_record_families"]) <= contract["families"]
            assert set(fixture["sdd_record_families"]) & contract["families"]
            assert fixture["fixture_id"] in readme
            for family in fixture["sdd_record_families"]:
                assert family in readme

            envelope = fixture["runtime_authority_envelope"]
            assert envelope["reader_contract"] == contract["contract_name"]
            assert envelope["runtime_event_ref"].startswith("event://")
            assert envelope["tenant_id"]
            assert envelope["run_id"]
            assert envelope["job_id"]
            assert envelope["requested_execution_profile"] in {
                "research",
                "governed",
                "production",
            }
            assert envelope["effective_execution_profile"] in {
                "research",
                "governed",
                "production",
            }
            assert envelope["same_input_closure"]["policy_intent_ref"].startswith(
                "cas://sha256/"
            )
            assert isinstance(fixture["payload"], dict)

            if status_from_name == "pass":
                assert fixture["expected_failure_code"] is None
                assert envelope["authority_role"] == "producer_authority"
                assert envelope["provenance_kind"] == "runtime_emitted"
                assert envelope["validation_status"] == "pass"
                assert envelope["cas_ref"].startswith("cas://sha256/")
                assert envelope["artifact_ref"] == envelope["cas_ref"]
                assert envelope["same_input_closure"]["status"] == "closed"
                assert "static_inventory_ref" not in envelope
                assert "static_inventory_candidate" not in fixture["payload"]
            else:
                assert fixture["expected_failure_code"]
                assert envelope["provenance_kind"] in {
                    "static_inventory",
                    "runtime_blocker",
                }
                assert envelope["validation_status"] in {"blocked", "fail"}
                assert envelope["same_input_closure"]["status"] != "closed"
                assert envelope["rejection"]["failure_code"] == fixture[
                    "expected_failure_code"
                ]
                if envelope["provenance_kind"] == "static_inventory":
                    assert envelope["authority_role"] == "not_authoritative"
                    assert envelope["cas_ref"] is None
                    assert envelope["static_inventory_ref"].startswith("repo://")
                    assert fixture["payload"]["static_inventory_candidate"]
                else:
                    assert envelope["authority_role"] == "runtime_blocker"
                    assert envelope["cas_ref"].startswith("cas://sha256/")
                    assert fixture["payload"]["blockers"]

        assert seen_statuses == {"pass", "rejected"}


def test_wave_6_walking_skeleton_case_fixture_is_research_only_runtime_authority() -> None:
    path = (
        FIXTURE_ROOT
        / "walking_skeleton_case_contract"
        / "walking_skeleton_case_contract_pass.json"
    )
    case = _read_fixture(path)

    validated = validate_policy_design_case_profile(case)

    contract = validated["walking_skeleton_contract"]
    assert contract["contract_id"] == POLICY_DESIGN_WALKING_SKELETON_CONTRACT_ID
    assert contract["profile"] == "research"
    assert contract["non_production"] is True
    nodes = {str(node["node_type"]): node for node in validated["nodes"]}
    assert nodes["producer_evidence"]["real_domain_producer"] is False
    assert nodes["producer_evidence"]["stub_record"] is True
    assert nodes["claim"]["producer_evidence_refs"] == [nodes["producer_evidence"]["cas_ref"]]
    assert nodes["claim"]["accepted_deficit_refs"] == [nodes["deficit"]["cas_ref"]]
    assert nodes["deficit"]["deficit_kind"] == "single_line_evidence_deficit"
    assert nodes["deficit"]["rejected_profiles"] == ["governed", "production"]
    for node in nodes.values():
        assert node["runtime_authority_envelope"]["provenance_kind"] == "runtime_emitted"
        assert node["runtime_authority_envelope"]["cas_ref"] == node["cas_ref"]
        assert node["runtime_authority_envelope"]["diagnostic_event_ref"] == (
            node["diagnostic_event_ref"]
        )
