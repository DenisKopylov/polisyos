from __future__ import annotations

from datetime import UTC, datetime

from polisyos.runtime.quality.assurance_case import (
    build_policy_design_case_profile,
    build_policy_intent_envelope,
)


def sha(char: str) -> str:
    return "sha256:" + char * 64


def runtime_authority() -> dict[str, object]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "cas_ref": sha("a"),
        "runtime_event_ref": "event://policy_design_case/profile/run-24",
        "same_input_closure_ref": sha("b"),
        "effective_mode_ref": sha("c"),
        "schema_compatibility_ref": sha("d"),
    }


def policy_design_case() -> dict[str, object]:
    return build_policy_design_case_profile(
        case_id="pdc-wave-24",
        run_id="run-24",
        job_id="job-24",
        tenant_id="tenant-sensitive",
        effective_execution_profile="production",
        runtime_authority=runtime_authority(),
        capability_ledger={
            "schema_version": "policyos.runtime.policy_design_case.capability_ledger.v1",
            "ledger_ref": sha("f"),
            "literature_evidence_required": True,
            "duties": [
                {
                    "capability": capability,
                    "state": "selected",
                    "owner": f"team-{capability}",
                    "evidence_ref": sha(capability[0]),
                    "runtime_event_ref": f"event://policy_design_case/duty/{capability}",
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
            intent_id="intent-wave-24",
            run_id="run-24",
            job_id="job-24",
            tenant_id="tenant-sensitive",
            policy_problem="MSME credit access is constrained.",
            desired_outcome="Improve MSME survival.",
            proposed_intervention="Target credit guarantees to eligible MSMEs.",
            jurisdiction="UA",
            target_population="wartime MSMEs",
            policy_time="2026-05-18",
            data_time="2024-2026",
            requester_preferred_conclusion="expand credit guarantees",
            requested_authority_level="production",
            authoring_provenance={"capture_ref": sha("e")},
        ),
        generated_at=datetime(2026, 5, 18, 8, 0, tzinfo=UTC),
    )
