from __future__ import annotations

import copy
import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g0"
REFERENCE_DOC = REPO_ROOT / "docs/reference/policy-design-case-layer3-grounding-inventory.md"
INVENTORY_PATH = REPO_ROOT / "architecture/policy_design_case/inventory.json"
READINESS_MANIFEST_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer3_g0_readiness_manifest.json"
)
ADR_PATH = REPO_ROOT / "docs/adr/0175-layer3-grounding-subordination-discipline.md"

EXPECTED_SURFACE_AUDIENCES = {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"}


def _g0() -> Any:
    return import_module("polisyos.runtime.quality.proving_ground.pre_adapter_grounding_inventory")


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g0_readiness")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _issue_codes(report: Any) -> set[str]:
    payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
    return {str(issue["code"]) for issue in payload["issues"]}


def _issues_with(validation: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [issue for issue in validation["issues"] if issue["code"] == code]


def _bundle() -> Any:
    return _g0().build_layer3_g0_bundle(REPO_ROOT)


def _runtime_validation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    g0 = _g0()
    persisted = payload if payload is not None else _bundle()
    return g0.validate_layer3_g0_bundle(REPO_ROOT, persisted).model_dump(mode="json")


def _surface_validation() -> dict[str, Any]:
    g0 = _g0()
    bundle = _bundle()
    runtime_report = g0.validate_layer3_g0_bundle(REPO_ROOT, bundle).model_dump(
        mode="json"
    )
    issues = list(runtime_report["issues"])
    summary = dict(runtime_report["summary"])
    summary.update(
        {
            "closure_artifact_count": len(
                bundle.readiness_manifest.closure_artifact_paths
            ),
            "readiness_manifest_count": 1 if READINESS_MANIFEST_PATH.exists() else 0,
            "adr_id": "0175",
        }
    )

    _extend_surface_issues(issues)
    _extend_manifest_issues(issues, summary, bundle)
    _extend_adr_issues(issues, summary)

    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "summary": summary,
        "artifacts": {
            "import_firewall_lint": bundle.import_firewall_lint.model_dump(mode="json"),
            "readiness_manifest": bundle.readiness_manifest.model_dump(mode="json"),
        },
    }


def _extend_surface_issues(issues: list[dict[str, Any]]) -> None:
    doc_text = REFERENCE_DOC.read_text(encoding="utf-8") if REFERENCE_DOC.exists() else ""
    required_doc_tokens = [
        "PUBLIC",
        "REVIEWER",
        "EXPERT",
        "MACHINE",
        "policyos.policy_design_case.layer3_g0_discovery_search.v2",
        "policyos.layer3.g0.discovery_search_free_growth.v2",
        "discovery/search posture",
        "known-groundable recall seeds",
        "index freshness policy",
        "no-hardcode lint",
        "strangle backlog",
        "SourceContract readiness",
        "engineering-quality check",
        "zero-admission adapter registry",
        "quarantine and portless open questions",
        "SourceTouchpointRegistration",
        "source-truth adapter paths",
        "universal corpus fixtures",
        "docs/adr/0175-layer3-grounding-subordination-discipline.md",
    ]
    if any(token not in doc_text for token in required_doc_tokens):
        issues.append(
            _issue(
                "layer3_g0_public_surface_unsynced",
                "docs/reference/policy-design-case-layer3-grounding-inventory.md",
                "G0 reference surface must project authority, audiences, and registry crosswalks.",
            )
        )

    entry = _inventory_entry()
    audiences = set(entry.get("surface_audiences", [])) if entry else set()
    review_surface = set(entry.get("task5_review_surface", {}).keys()) if entry else set()
    expected_review_surface = {
        "discovery_search_posture",
        "known_groundable_recall_seeds",
        "index_freshness_policy",
        "no_hardcode_lint",
        "strangle_backlog",
        "five_health_metrics",
        "data_asset_source_contract_readiness",
        "engineering_quality_check",
        "zero_admission_adapter_registry",
        "quarantine_and_portless_open_questions",
    }
    if (
        not entry
        or entry.get("path")
        != "docs/reference/policy-design-case-layer3-grounding-inventory.md"
        or entry.get("schema_version")
        != "policyos.policy_design_case.layer3_g0_discovery_search.v2"
        or entry.get("rule_version")
        != "policyos.layer3.g0.discovery_search_free_growth.v2"
        or audiences != EXPECTED_SURFACE_AUDIENCES
        or entry.get("capability_reality_label") != "implemented"
        or set(entry.get("closure_artifact_paths", []))
        != set(_bundle().readiness_manifest.closure_artifact_paths)
        or review_surface != expected_review_surface
        or "domain_ceiling_claim_without_g1_search_adapter" not in entry.get(
            "may_not_use_for", []
        )
    ):
        issues.append(
            _issue(
                "layer3_g0_public_surface_unsynced",
                "architecture/policy_design_case/inventory.json",
                "G0 artifact family must be registered with all four audit audiences.",
            )
        )


def _extend_manifest_issues(
    issues: list[dict[str, Any]],
    summary: dict[str, Any],
    bundle: Any,
) -> None:
    if not READINESS_MANIFEST_PATH.exists():
        issues.append(
            _issue(
                "layer3_g0_manifest_runtime_drift",
                "architecture/policy_design_case/layer3_g0_readiness_manifest.json",
                "Task 5 must persist a readiness manifest matching runtime builder counts.",
            )
        )
        return

    manifest = json.loads(READINESS_MANIFEST_PATH.read_text(encoding="utf-8"))
    persisted_counts = manifest.get("counts") or manifest.get("readiness_manifest", {}).get(
        "counts"
    )
    summary["readiness_manifest_count"] = 1
    if persisted_counts != bundle.readiness_manifest.counts:
        issues.append(
            _issue(
                "layer3_g0_manifest_runtime_drift",
                "architecture/policy_design_case/layer3_g0_readiness_manifest.json",
                "Persisted readiness manifest counts must match runtime builder counts.",
            )
        )


def _extend_adr_issues(issues: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    g0 = _g0()
    adr_payload = _adr_payload()
    adr = adr_payload["adr"]
    summary.update(
        {
            "adr_status": adr["status"],
            "adr_human_acceptance_ref_present": bool(
                adr.get("accepted_by") and adr.get("accepted_at") and adr.get("acceptance_ref")
            ),
            "adr_open_questions_mode": adr["open_questions_mode"],
            "import_policy_constitution_conflict_recorded": adr[
                "import_policy_constitution_conflict_recorded"
            ],
            "policy_toml_pdc_allowlist_narrowing_followup_recorded": adr[
                "policy_toml_pdc_allowlist_narrowing_followup_recorded"
            ],
            "registry_crosswalk_clarification_recorded": adr[
                "registry_crosswalk_clarification_recorded"
            ],
            "v2_amendment_recorded": adr["v2_amendment_recorded"],
            "organizing_rules_recorded": adr["organizing_rules_recorded"],
            "rule12_t7_recorded": adr["rule12_t7_recorded"],
            "impact_note_recorded": adr["impact_note_recorded"],
            "rule_version_refs_recorded": adr["rule_version_refs_recorded"],
        }
    )

    adr_report = g0.validate_layer3_g0_adr(adr_payload).model_dump(mode="json")
    issues.extend(adr_report["issues"])
    current_codes = {issue["code"] for issue in issues}
    if (
        summary["adr_human_acceptance_ref_present"] is False
        and "layer3_g0_adr_human_acceptance_missing" not in current_codes
    ):
        issues.append(
            _issue(
                "layer3_g0_adr_human_acceptance_missing",
                "docs/adr/0175-layer3-grounding-subordination-discipline.md",
                "Task 5 must record human-principal acceptance fields for ADR-0175.",
            )
        )
    for field, message in {
        "v2_amendment_recorded": "ADR-0175 must record the v2 discovery/search amendment.",
        "organizing_rules_recorded": (
            "ADR-0175 must record constitution §5 and §7 Layer 3 discipline."
        ),
        "rule12_t7_recorded": "ADR-0175 must record amended Rule 12/T7 discipline.",
        "impact_note_recorded": (
            "ADR-0175 must include the constitution-required impact note."
        ),
        "rule_version_refs_recorded": (
            "ADR-0175 must include schema/rule version refs for replay and migration."
        ),
    }.items():
        if not adr.get(field):
            issues.append(
                _issue(
                    "layer3_g0_adr_v2_amendment_incomplete",
                    "docs/adr/0175-layer3-grounding-subordination-discipline.md",
                    message,
                )
            )


def _adr_payload() -> dict[str, Any]:
    if not ADR_PATH.exists():
        return {
            "adr": {
                "adr_id": "0175",
                "title": "Layer 3 Grounding Subordination Discipline",
                "status": "Proposed",
                "accepted_by": "",
                "accepted_at": "",
                "acceptance_ref": "",
                "open_questions_mode": "tracked_empirically_open",
                "import_policy_constitution_conflict_recorded": True,
                "policy_toml_pdc_allowlist_narrowing_followup_recorded": True,
                "registry_crosswalk_clarification_recorded": True,
            }
        }

    text = ADR_PATH.read_text(encoding="utf-8")
    status = _section_first_line(text, "Status") or _field(text, "status") or "Proposed"
    return {
        "adr": {
            "adr_id": "0175",
            "title": "Layer 3 Grounding Subordination Discipline",
            "status": "Accepted" if status.strip().lower() == "accepted" else status,
            "accepted_by": _field(text, "accepted_by") or _field(text, "Accepted by"),
            "accepted_at": _field(text, "accepted_at") or _field(text, "Accepted at"),
            "acceptance_ref": _field(text, "acceptance_ref")
            or _field(text, "Acceptance ref"),
            "open_questions_mode": "tracked_empirically_open"
            if "tracked_empirically_open" in text
            else "",
            "import_policy_constitution_conflict_recorded": "policy.toml" in text
            and "constitution" in text
            and "narrow" in text,
            "policy_toml_pdc_allowlist_narrowing_followup_recorded": "policy.toml"
            in text
            and "follow-up" in text
            and "narrow" in text,
            "registry_crosswalk_clarification_recorded": "preservation registry" in text
            and "admission registry" in text,
            "v2_amendment_recorded": "v2 discovery/search amendment" in text
            and "supplemental acceptance" in text,
            "organizing_rules_recorded": "§5 organizing rules" in text
            and "§7 ports/adapters/registry/conformance" in text,
            "rule12_t7_recorded": "Rule 12/T7" in text
            and "search-recall@known-seeds + index-staleness" in text,
            "impact_note_recorded": "status lattice" in text
            and "authority boundaries" in text
            and "replay behavior" in text
            and "affected slice plans" in text
            and "health signals" in text
            and "enforcement surfaces" in text,
            "rule_version_refs_recorded": "policyos.layer3.g0.discovery_search_free_growth.v2"
            in text
            and "policyos.policy_design_case.layer3_g0_discovery_search.v2" in text,
        }
    }


def _field(text: str, key: str) -> str:
    normalized = key.replace("_", " ").lower()
    variants = {key.lower(), normalized, key.replace("_", "-").lower()}
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        lowered = stripped.lower()
        if any(lowered.startswith(variant) for variant in variants) and ":" in stripped:
            return stripped.split(":", 1)[1].strip().strip("`")
    return ""


def _section_first_line(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    section = text[start + len(marker) :]
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    for line in section.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _inventory_entry() -> dict[str, Any] | None:
    if not INVENTORY_PATH.exists():
        return None
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    for entry in inventory.get("artifacts", []):
        if entry.get("id") == "layer3_g0_grounding_inventory_audit_surface":
            return entry
    return None


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def test_layer3_g0_readiness_fails_until_inventory_triage_ports_and_ledgers_are_frozen() -> None:
    validation = _surface_validation()
    summary = validation["summary"]

    assert summary["closure_artifact_count"] == 16
    assert summary["health_metric_ledger_count"] == 5
    assert summary["schema_version"] == "policyos.policy_design_case.layer3_g0_discovery_search.v2"
    assert summary["rule_version"] == "policyos.layer3.g0.discovery_search_free_growth.v2"
    assert summary["grounding_search_ledger_contract_count"] == 1
    assert summary["search_recall_seed_status"] == "pass"
    assert summary["index_freshness_status"] == "pass"
    assert summary["free_growth_fixture_status"] == "pass"
    assert summary["mechanism_generality_fixture_status"] == "pass"
    assert summary["no_hardcode_enumeration_lint_status"] == "pass"
    assert summary["engineering_quality_check_status"] == "pass"
    assert summary["admitted_adapter_count"] == 0
    assert summary["grounded_conversion_count"] == 0
    assert validation["status"] == "pass", validation["issues"]


def test_layer3_g0_inventory_covers_current_source_packages_and_data_assets() -> None:
    validation = _runtime_validation()
    summary = validation["summary"]

    assert validation["status"] == "pass", validation["issues"]
    assert summary["source_package_count"] == 25
    assert summary["required_data_asset_root_count"] == 6
    assert summary["data_asset_inventory_unclassified_discovered_count"] == 0
    assert summary["processing_transform_inventory_unclassified_discovered_count"] == 0
    assert summary["production_data_manifest_bundle_count"] == 5
    assert summary["ukraine_simulation_manifest_file_count"] == 40
    assert summary["academic_runtime_slim_split_file_count"] == 20
    assert summary["universal_corpus_fixture_count"] == 13
    assert summary["ukraine_ops_runner_script_count"] == 10


def test_layer3_g0_portless_capabilities_are_recorded_as_governed_open_questions() -> None:
    g0 = _g0()
    malformed = _fixture("malformed_portless_capability_missing_open_question.json")[
        "payload"
    ]

    report = g0.validate_capability_inventory_payload(malformed)

    assert report.status == "fail"
    assert "layer3_g0_portless_capability_missing_open_question" in _issue_codes(report)


def test_layer3_g0_data_inventory_is_manifest_backed_and_does_not_treat_corpus_fixtures_as_authority() -> None:
    g0 = _g0()
    malformed = _fixture("malformed_data_asset_missing_evidence.json")["payload"]

    report = g0.validate_data_asset_inventory_payload(malformed)

    assert report.status == "fail"
    assert "layer3_g0_data_asset_evidence_missing" in _issue_codes(report)
    assert "layer3_g0_manifest_backed_data_scan_bypassed" in _issue_codes(report)


def test_layer3_g0_import_firewall_blocks_pdc_source_imports_and_quarantined_adapters() -> None:
    g0 = _g0()
    malformed = _fixture("malformed_adapter_admission_quarantined_source.json")[
        "payload"
    ]

    admission_report = g0.validate_adapter_admission_registry(
        admission_records=malformed["adapter_admission_registry"]["records"],
        quarantine_registry=malformed["quarantine_registry"]["entries"],
    )
    firewall = g0.ImportFirewallReport.model_validate(malformed["import_firewall_lint"])

    assert admission_report.status == "fail"
    assert "layer3_g0_quarantined_source_admitted" in _issue_codes(admission_report)
    assert {violation.issue_code for violation in firewall.violations} == {
        "layer3_g0_pdc_non_waist_import"
    }


def test_layer3_g0_manifest_metrics_match_runtime_builder_output() -> None:
    payload = _bundle().model_dump(mode="json")
    stale = copy.deepcopy(payload)
    stale["readiness_manifest"]["counts"]["port_count"] = 26
    stale["readiness_manifest"]["counts"]["runtime_quality_touchpoint_count"] = 21

    report = _runtime_validation(stale)

    assert report["status"] == "fail"
    assert "layer3_g0_manifest_runtime_drift" in _issue_codes(report)


def test_layer3_g0_validator_loads_v2_persisted_artifacts_and_search_gate_statuses() -> None:
    validator = _validator()

    report = validator.validate_layer3_g0_readiness(REPO_ROOT)
    summary = report["summary"]
    manifest = json.loads(READINESS_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert report["status"] == "pass", report["issues"]
    assert summary["schema_version"] == "policyos.policy_design_case.layer3_g0_discovery_search.v2"
    assert summary["rule_version"] == "policyos.layer3.g0.discovery_search_free_growth.v2"
    assert summary["persisted_closure_artifact_count"] == 16
    assert summary["health_metric_ledger_count"] == 5
    assert summary["search_recall_seed_status"] == "pass"
    assert summary["index_freshness_status"] == "pass"
    assert summary["free_growth_fixture_status"] == "pass"
    assert summary["mechanism_generality_fixture_status"] == "pass"
    assert summary["data_asset_source_contract_readiness_status"] == "pass"
    assert summary["engineering_quality_check_status"] == "pass"
    assert (
        "architecture/policy_design_case/layer3_discovery_search_discipline.json"
        in manifest["closure_artifact_paths"]
    )
    assert (
        "architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json"
        in manifest["closure_artifact_paths"]
    )
    assert (
        "architecture/policy_design_case/layer3_engineering_quality_check.json"
        in manifest["closure_artifact_paths"]
    )


def test_layer3_g0_import_firewall_artifact_is_persisted_and_blocks_all_non_allowlisted_pdc_imports() -> None:
    validation = _runtime_validation()
    summary = validation["summary"]
    firewall = _bundle().import_firewall_lint.model_dump(mode="json")

    assert validation["status"] == "pass", validation["issues"]
    assert summary["import_firewall_artifact_count"] == 1
    assert summary["pdc_non_waist_import_count"] == 0
    assert firewall["allowlist_roots"] == ["core"]
    assert "ir" in firewall["forbidden_roots"]
    assert "runtime" in firewall["forbidden_roots"]
    assert "scientist" in firewall["forbidden_roots"]


def test_layer3_g0_empty_port_and_adapter_cost_maps_have_ranked_constraints() -> None:
    g0 = _g0()
    malformed = _fixture("malformed_empty_port_missing_constraint_rank.json")[
        "payload"
    ]
    issue_codes: set[str] = set()

    for entry in malformed["empty_port_map"]["entries"]:
        try:
            g0.EmptyPortMapEntry.model_validate(entry)
        except ValueError:
            issue_codes.add("layer3_g0_empty_port_map_missing_constraint_rank")
    for entry in malformed["adapter_cost_map"]["entries"]:
        try:
            g0.AdapterCostMapEntry.model_validate(entry)
        except ValueError:
            issue_codes.add("layer3_g0_adapter_cost_map_missing_near_typed_score")

    assert "layer3_g0_empty_port_map_missing_constraint_rank" in issue_codes
    assert "layer3_g0_adapter_cost_map_missing_near_typed_score" in issue_codes


def test_layer3_g0_adr_tracks_constitution_open_questions_and_human_acceptance() -> None:
    g0 = _g0()
    malformed = _fixture("malformed_adr_missing_open_questions.json")["payload"]

    report = g0.validate_layer3_g0_adr(malformed)
    validation = _surface_validation()
    summary = validation["summary"]

    assert report.status == "fail"
    assert "layer3_g0_adr_open_questions_missing" in _issue_codes(report)
    assert summary["adr_human_acceptance_ref_present"] is True, _issues_with(
        validation, "layer3_g0_adr_human_acceptance_missing"
    )


def test_layer3_g0_adr_validator_fails_without_v2_amendment_metadata() -> None:
    g0 = _g0()
    payload = _adr_payload()
    payload["adr"].update(
        {
            "v2_amendment_recorded": False,
            "organizing_rules_recorded": False,
            "rule12_t7_recorded": False,
            "impact_note_recorded": False,
            "rule_version_refs_recorded": False,
        }
    )

    report = g0.validate_layer3_g0_adr(payload)

    assert report.status == "fail"
    assert "layer3_g0_adr_v2_amendment_incomplete" in _issue_codes(report)


def test_layer3_g0_policy_and_registry_governance_followups_are_recorded() -> None:
    validation = _surface_validation()
    summary = validation["summary"]

    assert summary["adr_id"] == "0175"
    assert summary["adr_open_questions_mode"] == "tracked_empirically_open"
    assert summary["import_policy_constitution_conflict_recorded"] is True
    assert summary["policy_toml_pdc_allowlist_narrowing_followup_recorded"] is True
    assert summary["registry_crosswalk_clarification_recorded"] is True
    assert summary["adr_status"] == "Accepted", _issues_with(
        validation, "layer3_g0_adr_not_accepted"
    )
    assert summary["adr_human_acceptance_ref_present"] is True, _issues_with(
        validation, "layer3_g0_adr_human_acceptance_missing"
    )


def test_layer3_g0_task5_audit_surface_exposes_v2_reviewable_artifacts() -> None:
    validation = _surface_validation()
    entry = _inventory_entry()
    doc_text = REFERENCE_DOC.read_text(encoding="utf-8")

    assert validation["status"] == "pass", validation["issues"]
    assert entry is not None
    assert entry["schema_version"] == "policyos.policy_design_case.layer3_g0_discovery_search.v2"
    assert entry["rule_version"] == "policyos.layer3.g0.discovery_search_free_growth.v2"
    assert len(entry["closure_artifact_paths"]) == 16
    assert set(entry["closure_artifact_paths"]) == set(
        _bundle().readiness_manifest.closure_artifact_paths
    )
    assert set(entry["task5_review_surface"]) == {
        "discovery_search_posture",
        "known_groundable_recall_seeds",
        "index_freshness_policy",
        "no_hardcode_lint",
        "strangle_backlog",
        "five_health_metrics",
        "data_asset_source_contract_readiness",
        "engineering_quality_check",
        "zero_admission_adapter_registry",
        "quarantine_and_portless_open_questions",
    }
    assert "domain_ceiling_claim_without_g1_search_adapter" in entry["may_not_use_for"]
    for token in [
        "discovery/search posture",
        "known-groundable recall seeds",
        "index freshness policy",
        "no-hardcode lint",
        "strangle backlog",
        "SourceContract readiness",
        "engineering-quality check",
        "zero-admission adapter registry",
        "quarantine and portless open questions",
    ]:
        assert token in doc_text


def test_layer3_g0_adr_records_v2_amendment_rule12_t7_and_impact_note() -> None:
    validation = _surface_validation()
    adr = _adr_payload()["adr"]

    assert validation["status"] == "pass", validation["issues"]
    assert adr["status"] == "Accepted"
    assert adr["v2_amendment_recorded"] is True
    assert adr["organizing_rules_recorded"] is True
    assert adr["rule12_t7_recorded"] is True
    assert adr["impact_note_recorded"] is True
    assert adr["rule_version_refs_recorded"] is True
