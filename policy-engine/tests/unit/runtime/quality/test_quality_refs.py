from __future__ import annotations

from polisyos.runtime.quality.refs import (
    REQUIRED_QUALITY_REF_KEYS,
    RuntimeQualityAuthorityRefs,
    resolve_quality_refs,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def test_resolve_quality_refs_discovers_required_refs_from_runtime_surfaces() -> None:
    resolution = resolve_quality_refs(
        run_params={
            "runtime_quality_refs": {
                "normative_applicability_report_ref": _sha("1"),
            }
        },
        artifacts={
            "outputs": [
                {
                    "name": "fabric_retrieval_trace_ref",
                    "artifact_id": _sha("2"),
                }
            ],
            "quality": {
                "role": "foundry_method_report_ref",
                "ref": _sha("3"),
            },
        },
        timeline={
            "events": [
                {
                    "event": "policy_grounding_matrix.persisted",
                    "details": {
                        "quality_refs": {
                            "policy_grounding_matrix_ref": {
                                "artifact_id": _sha("4"),
                            }
                        }
                    },
                }
            ]
        },
        lineage={
            "nodes": [
                {
                    "kind": "lex.conflict_check",
                    "metadata": {
                        "conflict_check_ref": _sha("5"),
                    },
                }
            ]
        },
        control_progress={
            "details": {
                "production_data_quality_report_ref": _sha("0"),
            }
        },
    )

    assert resolution.refs == {
        "production_data_quality_report_ref": _sha("0"),
        "normative_applicability_report_ref": _sha("1"),
        "fabric_retrieval_trace_ref": _sha("2"),
        "foundry_method_report_ref": _sha("3"),
        "policy_grounding_matrix_ref": _sha("4"),
        "conflict_check_ref": _sha("5"),
    }
    assert resolution.missing == ()
    assert [match.source for match in resolution.matches] == [
        "control_progress",
        "run_params",
        "artifacts",
        "artifacts",
        "timeline",
        "lineage",
    ]
    assert [match.key for match in resolution.matches] == list(REQUIRED_QUALITY_REF_KEYS)


def test_resolve_quality_refs_reports_stable_missing_evidence_diagnostics() -> None:
    resolution = resolve_quality_refs(
        control_progress={
            "details": {
                "normative_applicability_report_ref": _sha("1"),
                "optional_runtime_quality_refs": {
                    "fabric_retrieval_trace_ref": "fixture intentionally omits Fabric",
                },
            }
        }
    )

    expected_missing = tuple(
        key for key in REQUIRED_QUALITY_REF_KEYS if key != "normative_applicability_report_ref"
    )
    assert resolution.refs == {"normative_applicability_report_ref": _sha("1")}
    assert resolution.missing == expected_missing
    assert resolution.missing_evidence == tuple(
        {
            "code": f"{key}_missing",
            "missing_evidence_type": key,
            "message": f"Runtime quality ref {key} was not found.",
            "next_action": (
                f"Persist {key} from the owning runtime layer before production approval."
            ),
        }
        for key in expected_missing
    )

    evidence = resolution.to_evidence()
    assert evidence["status"] == "missing"
    assert evidence["refs"] == {"normative_applicability_report_ref": _sha("1")}
    assert evidence["missing"] == list(expected_missing)
    assert evidence["missing_evidence"] == list(resolution.missing_evidence)


def test_runtime_quality_authority_refs_read_only_typed_runtime_surfaces() -> None:
    nested_fixture_ref = _sha("9")
    runtime_ref = _sha("1")

    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "progress": {
                "details": {
                    "runtime_quality_refs": {
                        "normative_applicability_report_ref": runtime_ref,
                    },
                    "legacy_projection": {
                        "normative_applicability_report_ref": nested_fixture_ref,
                    },
                }
            }
        },
        run_payload={
            "metadata": {
                "fabric_retrieval_trace_ref": nested_fixture_ref,
            }
        },
        quality_evidence={
            "fabric_retrieval_trace": {
                "ref_key": "fabric_retrieval_trace_ref",
                "ref": _sha("2"),
            }
        },
    )

    assert refs.get("normative_applicability_report_ref") == runtime_ref
    assert refs.get("fabric_retrieval_trace_ref") == _sha("2")
    assert nested_fixture_ref not in refs.refs.values()


def test_runtime_quality_authority_refs_report_required_missing_refs() -> None:
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={"progress": {"details": {"runtime_quality_refs": {}}}},
        run_payload=None,
        quality_evidence={},
    )

    assert refs.missing_required() == tuple(REQUIRED_QUALITY_REF_KEYS)
