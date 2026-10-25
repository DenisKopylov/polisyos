from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.authority import EvidenceAuthorityEnvelope
from polisyos.runtime.quality.refs import (
    KNOWN_QUALITY_REF_KEYS,
    REQUIRED_QUALITY_REF_KEYS,
    RuntimeQualityAuthorityRefs,
    _ref_aliases_for,
    resolve_quality_refs,
    strip_rejected_quality_ref_inputs,
)
from polisyos.runtime.quality.report_registry import (
    QUALITY_REPORT_RUNTIME_REFS,
    quality_report_ref_intake_registry,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _typed_envelope_with_optional_cas_ref_none() -> dict[str, object]:
    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "tests/fixtures/runtime_quality/authority_envelopes/serious_runtime_emitted_pass.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload = fixture["payload"]
    payload.pop("cas_ref")
    return EvidenceAuthorityEnvelope.model_validate(payload).model_dump(mode="json")


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
    assert refs.get("fabric_retrieval_trace_ref") is None
    assert nested_fixture_ref not in refs.refs.values()
    candidate_refs = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {
                "fabric_retrieval_trace": {
                    "ref_key": "fabric_retrieval_trace_ref",
                    "ref": _sha("2"),
                }
            }
        }
    )
    assert candidate_refs.get("fabric_retrieval_trace_ref") == _sha("2")


def test_runtime_quality_authority_refs_report_required_missing_refs() -> None:
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={"progress": {"details": {"runtime_quality_refs": {}}}},
        run_payload=None,
        quality_evidence={},
    )

    assert refs.missing_required() == tuple(REQUIRED_QUALITY_REF_KEYS)


def test_quality_ref_resolution_retains_malformed_optional_security_ref() -> None:
    supplied_ref = "Bearer secret-value-do-not-copy"
    resolution = resolve_quality_refs(
        artifacts={"security_assurance_report_ref": supplied_ref},
        control_progress={"security_assurance_report_ref": _sha("a")},
    )

    assert resolution.refs["security_assurance_report_ref"] == _sha("a")
    assert resolution.rejections[0].key == "security_assurance_report_ref"
    assert resolution.rejections[0].reason == "secret_marker"
    assert resolution.rejections[0].value_length == len(supplied_ref)
    assert supplied_ref not in str(resolution.to_evidence())
    assert resolution.to_evidence()["status"] == "invalid"


def test_runtime_quality_refs_keep_explicit_selected_profile_and_reject_malformed_map() -> None:
    selected_profile = "sha256:" + "b" * 64
    selected = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"security_assurance_report_ref": _sha("c")},
            "runtime_quality_artifact_refs": {
                "security_assurance_report_ref": {
                    "artifact_id": _sha("c"),
                    "kind": "runtime.security_assurance_report",
                    "media_type": "application/json",
                    "manifest_profile_sha256": selected_profile,
                }
            },
        }
    )
    assert selected.get("security_assurance_report_ref") == _sha("c")
    assert selected.get_selected_ref("security_assurance_report_ref") is not None
    assert (
        selected.get_selected_ref("security_assurance_report_ref").manifest_profile_sha256
        == selected_profile
    )
    assert selected.unrejected_refs() == {"security_assurance_report_ref": _sha("c")}
    assert set(selected.unrejected_selected_refs()) == {"security_assurance_report_ref"}
    assert selected.sources["security_assurance_report_ref"] == "job.runtime_quality_refs"
    assert (
        selected.selected_sources["security_assurance_report_ref"]
        == "job.runtime_quality_artifact_refs"
    )
    assert (
        selected.to_evidence()["selected_sources"]["security_assurance_report_ref"]
        == "job.runtime_quality_artifact_refs"
    )
    assert not selected.rejections

    malformed = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"security_assurance_report_ref": _sha("c")},
            "runtime_quality_artifact_refs": {
                "security_assurance_report_ref": {
                    "artifact_id": _sha("c"),
                    "kind": "runtime.security_assurance_report",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:invalid",
                }
            },
        }
    )
    assert malformed.get("security_assurance_report_ref") is None
    assert malformed.get_selected_ref("security_assurance_report_ref") is None
    assert any(item.key == "security_assurance_report_ref" for item in malformed.rejections)
    assert malformed.unrejected_refs() == {}


def test_runtime_authority_getters_reject_a_conflicted_required_role() -> None:
    valid_ref = _sha("b")
    conflicting_ref = _sha("c")
    selected_profile = "sha256:" + "d" * 64
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"normative_applicability_report_ref": valid_ref},
            "runtime_quality_artifact_refs": {
                "normative_applicability_report_ref": {
                    "artifact_id": conflicting_ref,
                    "kind": "runtime.normative_applicability_report",
                    "media_type": "application/json",
                    "manifest_profile_sha256": selected_profile,
                }
            },
        }
    )

    assert refs.refs["normative_applicability_report_ref"] == valid_ref
    assert refs.get("normative_applicability_report_ref") is None
    assert refs.get_selected_ref("normative_applicability_report_ref") is None
    assert "normative_applicability_report_ref" in refs.missing_required()
    assert refs.to_evidence()["refs"]["normative_applicability_report_ref"] == valid_ref
    assert any(
        item.key == "normative_applicability_report_ref" and item.reason == "conflicting_values"
        for item in refs.rejections
    )


def test_runtime_authority_getters_reject_malformed_sibling_sources() -> None:
    valid_ref = _sha("b")
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"normative_applicability_report_ref": valid_ref},
            "progress": {
                "details": {
                    "runtime_quality_refs": {
                        "normative_applicability_report_ref": "bad\nref",
                    }
                }
            },
        }
    )

    assert refs.refs["normative_applicability_report_ref"] == valid_ref
    assert refs.get("normative_applicability_report_ref") is None
    assert "normative_applicability_report_ref" in refs.missing_required()
    assert refs.rejections[0].reason == "control_character"


def test_profileless_legacy_ref_does_not_materialize_a_selected_view() -> None:
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"security_assurance_report_ref": _sha("d")},
        }
    )

    assert refs.get("security_assurance_report_ref") == _sha("d")
    assert refs.get_selected_ref("security_assurance_report_ref") is None
    assert not refs.rejections


def test_runtime_quality_refs_reject_explicit_null_selected_map() -> None:
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={"runtime_quality_artifact_refs": None}
    )

    assert refs.get_selected_ref("security_assurance_report_ref") is None
    assert len(refs.rejections) == 1
    assert refs.rejections[0].key == "runtime_quality_artifact_refs"
    assert refs.rejections[0].reason == "explicit_null"
    assert refs.unrejected_refs() == {}


def test_quality_ref_resolution_rejects_each_malformed_supplied_value() -> None:
    cases = (
        ("bad\nref", "control_character"),
        ("x" * 257, "value_too_long"),
        ({"artifact_id": None}, "explicit_null"),
        ({"artifact_id": None, "status": "pass"}, "explicit_null"),
        ({"unknown": "not-a-ref"}, "malformed_mapping"),
        (["not-a-ref-string"], "unsupported_type"),
    )
    for value, expected_reason in cases:
        resolution = resolve_quality_refs(artifacts={"security_assurance_report_ref": value})
        assert len(resolution.rejections) == 1
        assert resolution.rejections[0].reason == expected_reason
        assert resolution.to_evidence()["status"] == "invalid"


def test_unrejected_resolution_refs_exclude_only_the_rejected_role() -> None:
    security_ref = _sha("a")
    normative_ref = _sha("b")
    resolution = resolve_quality_refs(
        control_progress={
            "security_assurance_report_ref": security_ref,
            "normative_applicability_report_ref": normative_ref,
        },
        artifacts={"security_assurance_report_ref": "Bearer supplied-secret"},
    )

    assert resolution.refs["security_assurance_report_ref"] == security_ref
    assert resolution.unrejected_refs() == {
        "normative_applicability_report_ref": normative_ref,
    }
    assert resolution.to_evidence()["status"] == "invalid"


@pytest.mark.parametrize(
    "alias",
    [*_ref_aliases_for("report"), *KNOWN_QUALITY_REF_KEYS],
)
def test_present_null_generic_report_alias_blocks_valid_runtime_ref(alias: str) -> None:
    runtime_refs = {
        key: _sha(format(index, "x")) for index, key in enumerate(KNOWN_QUALITY_REF_KEYS, start=1)
    }
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={"runtime_quality_refs": runtime_refs},
        quality_evidence={
            "normative_applicability_report_ref": {alias: None},
        },
    )

    expected_rejection_key = (
        alias if alias in KNOWN_QUALITY_REF_KEYS else "normative_applicability_report_ref"
    )
    for key, valid_ref in runtime_refs.items():
        assert refs.refs[key] == valid_ref
        assert refs.get(key) == (None if key == expected_rejection_key else valid_ref)
    assert expected_rejection_key in {item.key for item in refs.rejections}
    assert any(
        item.key == expected_rejection_key and item.reason == "explicit_null"
        for item in refs.rejections
    )


@pytest.mark.parametrize("alias", _ref_aliases_for("authority_envelope"))
def test_present_null_authority_envelope_alias_blocks_valid_runtime_ref(
    alias: str,
) -> None:
    valid_ref = _sha("b")
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"normative_applicability_report_ref": valid_ref},
        },
        quality_evidence={
            "normative_applicability_report_ref": {
                "authority_envelope": {alias: None},
            },
        },
    )

    assert refs.get("normative_applicability_report_ref") is None
    assert "normative_applicability_report_ref" in refs.missing_required()
    assert any(
        item.key == "normative_applicability_report_ref"
        and item.reason == "explicit_null"
        and item.path.endswith(f"authority_envelope.{alias}")
        for item in refs.rejections
    )


def test_typed_authority_envelope_nullable_cas_ref_is_schema_defined_absence() -> None:
    envelope = _typed_envelope_with_optional_cas_ref_none()
    assert envelope["cas_ref"] is None

    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {
                "normative_applicability_report_ref": envelope["artifact_ref"],
            }
        },
        quality_evidence={
            "normative_applicability_report_ref": {
                "authority_envelope": envelope,
            }
        },
    )

    assert refs.get("normative_applicability_report_ref") == envelope["artifact_ref"]
    assert refs.sources["normative_applicability_report_ref"] == "job.runtime_quality_refs"
    assert refs.rejections == ()

    inline_only = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        quality_evidence={
            "normative_applicability_report_ref": {
                "authority_envelope": envelope,
            }
        }
    )
    assert inline_only.get("normative_applicability_report_ref") is None
    assert "normative_applicability_report_ref" in inline_only.missing_required()
    assert inline_only.rejections == ()


def test_incomplete_authority_envelope_cannot_use_typed_nullable_cas_exception() -> None:
    fake_ref = _sha("d")
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {
                "normative_applicability_report_ref": fake_ref,
            }
        },
        quality_evidence={
            "normative_applicability_report_ref": {
                "authority_envelope": {
                    "cas_ref": None,
                    "artifact_ref": fake_ref,
                }
            }
        },
    )

    assert refs.refs["normative_applicability_report_ref"] == fake_ref
    assert refs.get("normative_applicability_report_ref") is None
    assert "normative_applicability_report_ref" in refs.missing_required()
    assert any(
        item.key == "normative_applicability_report_ref"
        and item.reason == "malformed_authority_envelope"
        for item in refs.rejections
    )
    assert any(
        item.key == "normative_applicability_report_ref"
        and item.reason == "explicit_null"
        and item.path.endswith("authority_envelope.cas_ref")
        for item in refs.rejections
    )


def test_unmodeled_null_alias_in_valid_authority_envelope_is_rejected() -> None:
    envelope = _typed_envelope_with_optional_cas_ref_none()
    envelope["ref"] = None
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        quality_evidence={
            "normative_applicability_report_ref": {
                "authority_envelope": envelope,
            }
        }
    )

    assert refs.get("normative_applicability_report_ref") is None
    assert any(
        item.key == "normative_applicability_report_ref"
        and item.reason == "explicit_null"
        and item.path.endswith("authority_envelope.ref")
        for item in refs.rejections
    )


@pytest.mark.parametrize(
    "null_key",
    _ref_aliases_for("nested"),
)
def test_present_null_nested_generic_value_blocks_wrapper_candidate(
    null_key: str,
) -> None:
    valid_ref = _sha("b")
    valid_key = next(key for key in _ref_aliases_for("nested") if key != null_key)
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"normative_applicability_report_ref": valid_ref},
        },
        quality_evidence={
            "normative_applicability_report_ref": {
                "ref": {
                    "value": {valid_key: _sha("c"), null_key: None},
                },
            },
        },
    )

    assert refs.refs["normative_applicability_report_ref"] == valid_ref
    assert refs.get("normative_applicability_report_ref") is None
    assert "normative_applicability_report_ref" in refs.missing_required()
    assert any(
        item.key == "normative_applicability_report_ref" and item.reason == "explicit_null"
        for item in refs.rejections
    )


def test_absent_generic_alias_and_clean_mapping_do_not_create_rejections() -> None:
    valid_ref = _sha("b")
    runtime_refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {"normative_applicability_report_ref": valid_ref},
        },
        quality_evidence={"normative_applicability_report_ref": {"status": "pass"}},
    )
    resolution = resolve_quality_refs(
        artifacts={
            "role": "normative_applicability_report_ref",
            "artifact_id": valid_ref,
        }
    )

    assert runtime_refs.rejections == ()
    assert runtime_refs.get("normative_applicability_report_ref") == valid_ref
    assert resolution.rejections == ()
    assert resolution.unrejected_refs() == {
        "normative_applicability_report_ref": valid_ref,
    }
    assert resolution.to_evidence()["status"] == "missing"


@pytest.mark.parametrize("null_key", _ref_aliases_for("nested"))
def test_present_null_deep_generic_alias_blocks_quality_resolution_admission(
    null_key: str,
) -> None:
    valid_ref = _sha("b")
    valid_key = next(key for key in _ref_aliases_for("nested") if key != null_key)
    resolution = resolve_quality_refs(
        artifacts=[
            {
                "role": "normative_applicability_report_ref",
                "artifact_id": valid_ref,
                "value": {valid_key: valid_ref, null_key: None},
            }
        ]
    )

    assert resolution.refs["normative_applicability_report_ref"] == valid_ref
    assert resolution.unrejected_refs() == {}
    assert resolution.to_evidence()["status"] == "invalid"
    assert any(
        item.key == "normative_applicability_report_ref" and item.reason == "explicit_null"
        for item in resolution.rejections
    )


def test_explicit_malformed_ref_container_blocks_unrejected_resolution_projection() -> None:
    normative_ref = _sha("b")
    resolution = resolve_quality_refs(
        control_progress={"normative_applicability_report_ref": normative_ref},
        run_params={"runtime_quality_refs": None},
    )

    assert resolution.refs["normative_applicability_report_ref"] == normative_ref
    assert resolution.to_evidence()["status"] == "invalid"
    assert resolution.rejections[0].key == "runtime_quality_refs"
    assert resolution.unrejected_refs() == {}


def test_runtime_ref_rejections_filter_by_role_and_preserve_clean_selected_refs() -> None:
    security_ref = _sha("a")
    normative_ref = _sha("b")
    selected_profile = "sha256:" + "c" * 64
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {
                "security_assurance_report_ref": security_ref,
                "normative_applicability_report_ref": normative_ref,
            },
            "runtime_quality_artifact_refs": {
                "security_assurance_report_ref": {
                    "artifact_id": _sha("d"),
                    "kind": "runtime.security_assurance_report",
                    "media_type": "application/json",
                    "manifest_profile_sha256": selected_profile,
                },
                "normative_applicability_report_ref": {
                    "artifact_id": normative_ref,
                    "kind": "runtime.normative_applicability_report",
                    "media_type": "application/json",
                    "manifest_profile_sha256": selected_profile,
                },
            },
        }
    )

    assert any(rejection.key == "security_assurance_report_ref" for rejection in refs.rejections)
    assert refs.get("security_assurance_report_ref") is None
    assert refs.get("normative_applicability_report_ref") == normative_ref
    assert refs.get_selected_ref("normative_applicability_report_ref") is not None
    assert refs.unrejected_refs() == {"normative_applicability_report_ref": normative_ref}
    assert set(refs.unrejected_selected_refs()) == {"normative_applicability_report_ref"}


def test_explicit_null_legacy_ref_container_is_not_treated_as_absent() -> None:
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": None,
            "progress": {
                "details": {
                    "runtime_quality_refs": {
                        "normative_applicability_report_ref": _sha("b"),
                    }
                }
            },
        }
    )

    assert refs.refs["normative_applicability_report_ref"] == _sha("b")
    assert refs.get("normative_applicability_report_ref") is None
    assert refs.missing_required() == tuple(REQUIRED_QUALITY_REF_KEYS)
    assert refs.rejections[0].key == "runtime_quality_refs"
    assert refs.unrejected_refs() == {}


def test_absent_legacy_ref_container_keeps_other_valid_refs_admissible() -> None:
    normative_ref = _sha("b")
    refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "progress": {
                "details": {
                    "runtime_quality_refs": {
                        "normative_applicability_report_ref": normative_ref,
                    }
                }
            }
        }
    )

    assert refs.rejections == ()
    assert refs.unrejected_refs() == {"normative_applicability_report_ref": normative_ref}


def test_present_null_ref_is_rejected_while_absent_ref_is_not() -> None:
    resolution = resolve_quality_refs(
        artifacts={
            "security_assurance_report_ref": None,
            "normative_applicability_report_ref": _sha("b"),
        }
    )

    assert resolution.to_evidence()["status"] == "invalid"
    assert resolution.rejections[0].key == "security_assurance_report_ref"
    assert resolution.rejections[0].reason == "explicit_null"
    assert resolution.unrejected_refs() == {"normative_applicability_report_ref": _sha("b")}

    absent = resolve_quality_refs(artifacts={"normative_applicability_report_ref": _sha("b")})
    assert absent.rejections == ()
    assert absent.unrejected_refs() == {"normative_applicability_report_ref": _sha("b")}

    runtime_refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={
            "runtime_quality_refs": {
                "security_assurance_report_ref": None,
                "normative_applicability_report_ref": _sha("b"),
            }
        }
    )
    assert any(
        item.key == "security_assurance_report_ref" and item.reason == "explicit_null"
        for item in runtime_refs.rejections
    )
    assert runtime_refs.unrejected_refs() == {"normative_applicability_report_ref": _sha("b")}


def test_from_sources_unions_rejections_across_labeled_payloads_and_report_bodies() -> None:
    invalid_inputs = (
        "bad\nsecurity-ref-from-run",
        "bad\nnormative-ref-from-agents",
        "bad\nnormative-ref-from-request-body",
        "bad\nsecurity-ref-from-quality-evidence",
    )
    source_payloads = {
        "job": {
            "progress": {
                "details": {
                    "runtime_quality_refs": {
                        "security_assurance_report_ref": _sha("a"),
                    }
                }
            }
        },
        "run": {
            "params": {
                "runtime_quality_refs": {
                    "security_assurance_report_ref": invalid_inputs[0],
                }
            }
        },
        "agents": {
            "artifacts": {
                "normative_applicability_report_ref": invalid_inputs[1],
            }
        },
        "timeline": {
            "events": [{"normative_applicability_report_ref": None}],
        },
        "lineage": {
            "nodes": [{"security_assurance_report_ref": "x" * 257}],
        },
        "request": {
            "normative_evidence": {
                "status": "pass",
                "marker": "request-report-body-must-not-be-retained",
                "cas_ref": invalid_inputs[2],
            }
        },
        "quality_evidence": {
            "security_assurance_report_ref": invalid_inputs[3],
        },
    }

    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads=source_payloads)

    rejection_sources = {item.source for item in intake.rejections}
    assert {"run", "agents", "timeline", "lineage", "request", "quality_evidence"} <= (
        rejection_sources
    )
    assert "security_assurance_report_ref" in intake.refs
    assert "security_assurance_report_ref" not in intake.unrejected_refs()
    assert "normative_applicability_report_ref" not in intake.unrejected_refs()
    evidence = repr(intake.to_evidence())
    assert all(value not in evidence for value in invalid_inputs)
    assert "request-report-body-must-not-be-retained" not in evidence


def test_canonical_report_registry_rejects_every_role_across_supported_sources() -> None:
    ref_keys, body_ref_keys = quality_report_ref_intake_registry()
    assert set(QUALITY_REPORT_RUNTIME_REFS.values()) <= set(ref_keys)
    assert set(QUALITY_REPORT_RUNTIME_REFS) <= set(body_ref_keys)
    assert set(body_ref_keys.values()) <= set(ref_keys)

    source_names = (
        "job",
        "run",
        "agents",
        "timeline",
        "lineage",
        "request",
        "quality_evidence",
    )
    source_payloads: dict[str, object] = {}
    for source_name in source_names:
        refs: dict[str, object] = {}
        for index, (body_alias, _ref_key) in enumerate(sorted(body_ref_keys.items())):
            refs[f"body_alias_{index}"] = {
                "name": body_alias,
                "ref": f"bad\nbody-{index}",
            }
        for index, ref_key in enumerate(ref_keys):
            refs[f"role_alias_{index}"] = {
                "role": ref_key,
                "artifact_ref": f"bad\nrole-{index}",
            }
        source_payloads[source_name] = refs

    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads=source_payloads)
    for source_name in source_names:
        source_rejections = {item.key for item in intake.rejections if item.source == source_name}
        assert set(ref_keys) <= source_rejections, source_name
    assert set(ref_keys) <= {item.key for item in intake.rejections}

    privacy_ref_key = QUALITY_REPORT_RUNTIME_REFS["privacy_compliance_report"]
    clean_ref = _sha("p")
    clean = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {
                "privacy_body": {
                    "name": "privacy_compliance_report",
                    "ref": clean_ref,
                }
            }
        }
    )
    assert clean.rejections == ()
    assert clean.unrejected_refs()[privacy_ref_key] == clean_ref

    direct = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        quality_evidence={
            "privacy_compliance_report": {"status": "pass", "issues": []},
            "supplied_alias": {
                "name": "privacy_compliance_report",
                "ref": "bad\nprivacy-ref",
            },
        }
    )
    assert any(
        item.key == privacy_ref_key and item.source == "quality_evidence"
        for item in direct.rejections
    )
    assert privacy_ref_key not in direct.unrejected_refs()


def test_ambiguous_registry_role_hints_reject_every_role_and_multirole_text() -> None:
    ref_keys, body_ref_keys = quality_report_ref_intake_registry()
    registry_roles = set(body_ref_keys.values()) & set(ref_keys)
    report_roles = tuple(
        dict.fromkeys(
            role for role in QUALITY_REPORT_RUNTIME_REFS.values() if role in registry_roles
        )
    )
    assert len(report_roles) >= 2
    first_role, second_role = report_roles[:2]
    first_report = next(
        report_key for report_key, role in QUALITY_REPORT_RUNTIME_REFS.items() if role == first_role
    )
    clean_refs = {first_role: _sha("a"), second_role: _sha("b")}
    malformed = "bad\nambiguous-role-ref"
    conflicting_hints = {
        "name": first_report,
        "role": second_role,
        "ref": malformed,
    }

    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "clean_sibling": {"runtime_quality_refs": clean_refs},
            "ambiguous_mapping": {"artifact_candidate": conflicting_hints},
        }
    )
    ambiguous_rows = {row.key for row in intake.rejections if row.reason == "ambiguous_role_hints"}
    assert {first_role, second_role} <= ambiguous_rows
    assert first_role not in intake.unrejected_refs()
    assert second_role not in intake.unrejected_refs()

    second_report = next(
        report_key
        for report_key, role in QUALITY_REPORT_RUNTIME_REFS.items()
        if role == second_role
    )
    multi_role_text = f"candidate-{first_report}-{second_report}"
    text_intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "clean_sibling": {"runtime_quality_refs": clean_refs},
            "ambiguous_text": {"artifact_candidate": {"kind": multi_role_text, "ref": malformed}},
        }
    )
    text_rejections = {
        row.key for row in text_intake.rejections if row.reason == "ambiguous_role_hints"
    }
    assert {first_role, second_role} <= text_rejections
    assert first_role not in text_intake.unrejected_refs()
    assert second_role not in text_intake.unrejected_refs()

    path_intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "clean_sibling": {"runtime_quality_refs": clean_refs},
            "ambiguous_path": {f"candidate-{first_report}-{second_report}": {"ref": malformed}},
        }
    )
    path_rejections = {
        row.key for row in path_intake.rejections if row.reason == "ambiguous_role_hints"
    }
    assert {first_role, second_role} <= path_rejections
    assert first_role not in path_intake.unrejected_refs()
    assert second_role not in path_intake.unrejected_refs()

    ambiguous_report_key = f"candidate-{first_report}-{second_report}"
    runtime_payload_intake = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        quality_evidence={
            ambiguous_report_key: {
                "name": first_report,
                "status": "pass",
                "ref": malformed,
            }
        }
    )
    runtime_rejections = {
        row.key for row in runtime_payload_intake.rejections if row.reason == "ambiguous_role_hints"
    }
    assert {first_role, second_role} <= runtime_rejections
    assert first_role not in runtime_payload_intake.unrejected_refs()
    assert second_role not in runtime_payload_intake.unrejected_refs()


def test_runtime_payload_ref_intake_uses_every_canonical_role_and_alias() -> None:
    ref_keys, body_ref_keys = quality_report_ref_intake_registry()
    valid_overlay = {key: _sha(chr(97 + index % 26)) for index, key in enumerate(ref_keys)}
    malformed_values: set[str] = set()
    malformed_roles = {}
    for index, key in enumerate(ref_keys):
        value = f"bad\nquality-evidence-role-{index}"
        malformed_roles[key] = value
        malformed_values.add(value)
    quality_evidence: dict[str, object] = {"runtime_quality_refs": malformed_roles}
    for index, (alias, _ref_key) in enumerate(sorted(body_ref_keys.items())):
        name_ref = f"bad\nquality-evidence-name-{index}"
        role_ref = f"bad\nquality-evidence-role-hint-{index}"
        malformed_values.update((name_ref, role_ref))
        quality_evidence[f"named-report-{index}"] = {"name": alias, "ref": name_ref}
        quality_evidence[f"hinted-report-{index}"] = {
            "role": alias,
            "artifact_ref": role_ref,
        }

    intake = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        job_payload={"progress": {"details": {"runtime_quality_refs": valid_overlay}}},
        quality_evidence=quality_evidence,
    )

    rejected_keys = {item.key for item in intake.rejections if item.source == "quality_evidence"}
    assert set(ref_keys) <= rejected_keys
    assert not (set(ref_keys) & set(intake.unrejected_refs()))
    assert set(intake.refs) & set(ref_keys) == set(ref_keys)
    evidence = json.dumps(intake.to_evidence(), sort_keys=True)
    assert all(value not in evidence for value in malformed_values)


def test_quality_role_labels_require_complete_alias_boundaries() -> None:
    role = "security_assurance_report_ref"
    valid_ref = _sha("e")
    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "clean": {"runtime_quality_refs": {role: valid_ref}},
            "composite_marker": {
                f"ambiguous_role_marker_{role}": "not-a-reference",
            },
        }
    )

    assert intake.rejections == ()
    assert intake.unrejected_refs() == {role: valid_ref}


def test_registered_report_body_matrix_accepts_markerless_content() -> None:
    from polisyos.runtime.quality.report_registry import QUALITY_REPORT_BODY_KEYS

    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {
                body_key: {"producer_content": {"member": body_key}}
                for body_key in QUALITY_REPORT_BODY_KEYS
            }
        }
    )

    assert intake.refs == {}
    assert intake.rejections == ()


def test_registered_runtime_report_body_without_markers_is_not_a_ref_wrapper() -> None:
    body = {"claims": [{"claim_id": "claim-1"}], "basis": {"count": 1}}
    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={"quality_evidence": {"policy_grounding_matrix": body}}
    )

    assert intake.get("policy_grounding_matrix_ref") is None
    assert intake.rejections == ()


def test_registered_runtime_report_malformed_wrapper_stays_a_typed_refusal() -> None:
    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {"policy_grounding_matrix": {"artifact_id": "bad\nreport-ref"}}
        }
    )

    assert any(
        item.key == "policy_grounding_matrix_ref" and item.reason == "control_character"
        for item in intake.rejections
    )


def test_registered_runtime_report_malformed_wrapper_with_unknown_field_is_refused() -> None:
    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {
                "policy_grounding_matrix": {
                    "artifact_id": "bad\nreport-ref",
                    "unexpected": "x",
                }
            }
        }
    )

    assert intake.get("policy_grounding_matrix_ref") is None
    assert "policy_grounding_matrix_ref" not in intake.unrejected_refs()
    assert any(
        item.key == "policy_grounding_matrix_ref" and item.reason == "control_character"
        for item in intake.rejections
    )


def test_typed_refusal_records_survive_admission_ref_stripping() -> None:
    rejection = {
        "key": "security_assurance_report_ref",
        "source": "job.runtime_quality_refs",
        "path": "$.job.runtime_quality_refs.security_assurance_report_ref",
        "reason": "unsupported_type",
        "input_type": "builtins.int",
        "value_sha256": "a" * 64,
        "value_length": None,
    }
    payload = {
        "security_report_intake": {
            "security_assurance_report_ref": _sha("b"),
            "resolution_rejections": [rejection],
        }
    }

    admitted = strip_rejected_quality_ref_inputs(
        payload,
        rejected_ref_keys={"security_assurance_report_ref"},
        report_body_ref_keys=quality_report_ref_intake_registry()[1],
    )

    assert admitted["security_report_intake"]["resolution_rejections"] == [rejection]
    assert "security_assurance_report_ref" not in admitted["security_report_intake"]


def test_registry_body_without_runtime_ref_has_no_synthetic_role() -> None:
    from polisyos.runtime.quality.report_registry import QUALITY_REPORT_BODY_KEYS

    ref_keys, body_ref_keys = quality_report_ref_intake_registry()
    assert "golden_scenario_contract" in QUALITY_REPORT_BODY_KEYS
    assert "golden_scenario_contract" not in body_ref_keys
    assert "golden_scenario_contract_ref" not in ref_keys

    valid = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {
                "golden_scenario_contract": {
                    "scenario_id": "case-1",
                    "expected_evidence_contract": {"status": "pass"},
                }
            }
        }
    )
    malformed = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "quality_evidence": {"golden_scenario_contract": {"artifact_id": _sha("f")}}
        }
    )

    assert valid.rejections == ()
    assert "golden_scenario_contract_ref" not in valid.refs
    assert any(
        item.key == "golden_scenario_contract" and item.reason == "malformed_report_body_wrapper"
        for item in malformed.rejections
    )
    assert "golden_scenario_contract_ref" not in malformed.refs


def test_report_body_cross_role_ref_is_candidate_data_not_runtime_authority() -> None:
    cross_ref = _sha("a")
    report_body = {
        "security_assurance_report": {
            "status": "pass",
            "normative_applicability_report_ref": cross_ref,
        }
    }
    runtime_intake = RuntimeQualityAuthorityRefs.from_runtime_payloads(quality_evidence=report_body)
    candidate_intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={"quality_evidence": report_body}
    )

    assert runtime_intake.get("normative_applicability_report_ref") is None
    assert runtime_intake.get("security_assurance_report_ref") is None
    assert runtime_intake.rejections == ()
    assert candidate_intake.get("normative_applicability_report_ref") == cross_ref


def test_schema_owned_security_bundle_locator_is_not_a_runtime_ref(monkeypatch) -> None:
    from polisyos.runtime.quality import report_registry

    role = "security_assurance_report_ref"
    locator = "quality_evidence/security_assurance_report.json"
    report = {
        "schema_version": "policyos.security_assurance_report.v1",
        "status": "pass",
        "issues": [],
        role: locator,
    }
    payload = {"security_assurance_report": report}

    runtime_intake = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        quality_evidence=payload,
    )
    shared_intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={"quality_evidence": payload},
    )
    assert runtime_intake.rejections == ()
    assert runtime_intake.get(role) is None
    assert shared_intake.rejections == ()
    assert shared_intake.get(role) is None

    # Removing the registered semantic while retaining schema/role/field markers
    # makes the same value visible as a ref candidate.
    monkeypatch.setattr(report_registry, "QUALITY_REPORT_BODY_LOCATORS", ())
    without_locator_semantics = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={"quality_evidence": payload},
    )
    assert without_locator_semantics.get(role) == locator


@pytest.mark.parametrize(
    ("locator", "expected_reason"),
    [
        ("quality_evidence/other-report.json", "logical_locator_mismatch"),
        ("attestation://report/security", "logical_locator_mismatch"),
        (None, "explicit_null"),
        ([], "unsupported_type"),
    ],
)
def test_schema_owned_security_locator_rejects_malformed_or_conflicting_values(
    locator: object,
    expected_reason: str,
) -> None:
    role = "security_assurance_report_ref"
    payload = {
        "security_assurance_report": {
            "schema_version": "policyos.security_assurance_report.v1",
            "status": "pass",
            "issues": [],
            role: locator,
        }
    }
    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={"quality_evidence": payload},
    )
    assert intake.get(role) is None
    assert any(row.key == role and row.reason == expected_reason for row in intake.rejections)


def test_schema_owned_locator_requires_its_declared_schema_and_preserves_cas_conflicts() -> None:
    role = "security_assurance_report_ref"
    selected_ref = _sha("a")
    locator = "quality_evidence/security_assurance_report.json"
    report = {
        "schema_version": "policyos.security_assurance_report.v2",
        "status": "pass",
        "issues": [],
        role: locator,
    }
    intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "selected_runtime_refs": {"runtime_quality_refs": {role: selected_ref}},
            "cas_report.security_assurance_report": report,
        },
    )
    assert intake.get(role) is None
    assert any(row.key == role and row.reason == "conflicting_values" for row in intake.rejections)


def test_schema_owned_security_slot_accepts_only_the_selected_cas_identity() -> None:
    role = "security_assurance_report_ref"
    selected_ref = _sha("a")
    selected_body = {
        "schema_version": "policyos.security_assurance_report.v1",
        "status": "pass",
        "issues": [],
        role: selected_ref,
    }
    selected = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "selected_runtime_refs": {"runtime_quality_refs": {role: selected_ref}},
            "cas_report.security_assurance_report": selected_body,
        },
    )
    assert selected.rejections == ()
    assert selected.get(role) == selected_ref

    conflicting_body = {**selected_body, role: _sha("b")}
    conflicting = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={
            "selected_runtime_refs": {"runtime_quality_refs": {role: selected_ref}},
            "cas_report.security_assurance_report": conflicting_body,
        },
    )
    assert conflicting.get(role) is None
    assert any(
        row.key == role
        and row.reason == "conflicting_values"
        and row.source == "cas_report.security_assurance_report"
        for row in conflicting.rejections
    )


def test_runtime_report_body_explicit_refs_keep_registered_role_identity() -> None:
    ref_keys, body_ref_keys = quality_report_ref_intake_registry()
    owner_aliases: dict[str, str] = {}
    for alias, role_key in sorted(body_ref_keys.items()):
        owner_aliases.setdefault(role_key, alias)
    assert set(ref_keys) <= set(owner_aliases)

    expected = {
        role_key: f"sha256:{index + 1:064x}" for index, role_key in enumerate(sorted(ref_keys))
    }
    quality_evidence: dict[str, object] = {}
    for owner_role, body_alias in sorted(owner_aliases.items()):
        report = {
            "name": body_alias,
            "status": "pass",
            "ref": expected[owner_role],
            **expected,
        }
        quality_evidence[body_alias] = report

    intake = RuntimeQualityAuthorityRefs.from_runtime_payloads(
        quality_evidence=quality_evidence,
    )
    candidate_intake = RuntimeQualityAuthorityRefs.from_sources(
        source_payloads={"quality_evidence": quality_evidence}
    )

    assert intake.rejections == ()
    assert intake.unrejected_refs() == {}
    assert candidate_intake.unrejected_refs() == expected


@pytest.mark.parametrize(
    "source_name",
    ["job", "run", "agents", "timeline", "lineage", "request", "quality_evidence"],
)
def test_role_hinted_wrappers_recurse_for_every_registered_ref_key(
    source_name: str,
) -> None:
    ref_keys, _ = quality_report_ref_intake_registry()
    expected = {key: _sha(str(index % 10)) for index, key in enumerate(ref_keys)}
    source_payloads = {
        source_name: {
            f"lineage_node_{index}": {
                "kind": key,
                "metadata": {key: expected[key]},
            }
            for index, key in enumerate(ref_keys)
        }
    }

    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads=source_payloads)

    assert intake.rejections == ()
    assert intake.unrejected_refs() == expected


def test_role_hinted_lineage_wrapper_is_not_a_ref_value() -> None:
    ref_key = "policy_grounding_matrix_ref"
    expected_ref = _sha("a")
    lineage = {
        "nodes": [
            {
                "kind": "scientist.policy_grounding_matrix",
                "metadata": {ref_key: expected_ref},
            }
        ]
    }

    resolution = resolve_quality_refs(lineage=lineage)
    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads={"lineage": lineage})

    assert resolution.refs[ref_key] == expected_ref
    assert resolution.rejections == ()
    assert resolution.unrejected_refs() == {ref_key: expected_ref}
    assert intake.rejections == ()
    assert intake.unrejected_refs() == {ref_key: expected_ref}


def test_role_hinted_wrapper_keeps_explicit_null_fail_closed() -> None:
    ref_key = "policy_grounding_matrix_ref"
    lineage = {
        "nodes": [
            {
                "kind": "scientist.policy_grounding_matrix",
                "metadata": {ref_key: None},
            }
        ]
    }

    resolution = resolve_quality_refs(lineage=lineage)
    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads={"lineage": lineage})

    assert any(
        item.key == ref_key and item.reason == "explicit_null" for item in resolution.rejections
    )
    assert ref_key not in resolution.unrejected_refs()
    assert any(item.key == ref_key and item.reason == "explicit_null" for item in intake.rejections)
    assert ref_key not in intake.unrejected_refs()


def test_role_hinted_wrapper_with_malformed_generic_value_stays_rejected() -> None:
    ref_key = "policy_grounding_matrix_ref"
    lineage = {
        "nodes": [
            {
                "kind": "scientist.policy_grounding_matrix",
                "artifact_id": None,
                "metadata": {ref_key: _sha("a")},
            }
        ]
    }

    resolution = resolve_quality_refs(lineage=lineage)
    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads={"lineage": lineage})

    assert any(
        item.key == ref_key and item.reason == "explicit_null" for item in resolution.rejections
    )
    assert ref_key not in resolution.unrejected_refs()
    assert any(item.key == ref_key and item.reason == "explicit_null" for item in intake.rejections)
    assert ref_key not in intake.unrejected_refs()


def test_role_hinted_wrapper_without_nested_ref_stays_missing() -> None:
    ref_key = "policy_grounding_matrix_ref"
    lineage = {
        "nodes": [
            {
                "kind": "scientist.policy_grounding_matrix",
                "metadata": {"status": "pass"},
            }
        ]
    }

    resolution = resolve_quality_refs(lineage=lineage)
    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads={"lineage": lineage})

    assert ref_key not in resolution.refs
    assert ref_key in resolution.missing
    assert resolution.rejections == ()
    assert ref_key not in intake.refs
    assert intake.rejections == ()


def test_role_hinted_report_wrapper_rejects_null_generic_value_and_reads_metadata() -> None:
    ref_key = "policy_grounding_matrix_ref"
    lineage = {
        "nodes": [
            {
                "kind": "scientist.policy_grounding_matrix",
                "status": "pass",
                "artifact_id": None,
                "metadata": {ref_key: _sha("d")},
            }
        ]
    }

    resolution = resolve_quality_refs(lineage=lineage)
    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads={"lineage": lineage})

    assert resolution.refs[ref_key] == _sha("d")
    assert any(
        item.key == ref_key and item.reason == "explicit_null" for item in resolution.rejections
    )
    assert resolution.unrejected_refs() == {}
    assert any(item.key == ref_key and item.reason == "explicit_null" for item in intake.rejections)
    assert intake.unrejected_refs() == {}


def test_role_hinted_wrapper_conflicts_and_sibling_refs_stay_scoped() -> None:
    ref_key = "policy_grounding_matrix_ref"
    sibling_ref_key = "conflict_check_ref"
    lineage = {
        "nodes": [
            {
                "kind": "scientist.policy_grounding_matrix",
                "metadata": {ref_key: _sha("a")},
            },
            {
                "kind": "scientist.policy_grounding_matrix",
                "metadata": {ref_key: _sha("b")},
            },
            {
                "kind": "scientist.policy_grounding_matrix",
                "metadata": {sibling_ref_key: "invalid\nref"},
            },
        ]
    }

    resolution = resolve_quality_refs(lineage=lineage)
    intake = RuntimeQualityAuthorityRefs.from_sources(source_payloads={"lineage": lineage})

    assert any(
        item.key == ref_key and item.reason == "conflicting_values"
        for item in resolution.rejections
    )
    assert any(
        item.key == sibling_ref_key and item.reason == "control_character"
        for item in resolution.rejections
    )
    assert any(
        item.key == ref_key and item.reason == "conflicting_values" for item in intake.rejections
    )
    assert any(
        item.key == sibling_ref_key and item.reason == "control_character"
        for item in intake.rejections
    )
    assert ref_key not in resolution.unrejected_refs()
    assert sibling_ref_key not in resolution.unrejected_refs()
    assert ref_key not in intake.unrejected_refs()
    assert sibling_ref_key not in intake.unrejected_refs()
