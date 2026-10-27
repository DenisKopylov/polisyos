"""Exercise candidate impact topics through real comparison and fresh CAS readers."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ConfigDict, ValidationError, create_model

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.contracts import ComplianceIssue, IssueSeverity
from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.legal_evaluation.impact_diff import (
    ComplianceTransition,
    NormImpactAnalyzer,
    NormImpactReport,
    load_norm_impact_report,
)
from polisyos.lex.normpack.diff import NormChangeType, NormDiff
from polisyos.lex.simulator.cli import render_impact_markdown
from polisyos.runtime.quality.authority import authority_surface_decision
from tools.ops_runners.runtime_cli import main


def _rule(norm_id: str, rule_type: RuleType, expression: str) -> NormRule:
    expression_key = "must_not" if rule_type is RuleType.PROHIBITION else "must"
    return NormRule(
        norm_id=norm_id,
        rule_type=rule_type,
        description=f"Rule {norm_id}",
        backend_refs=["expr_ast"],
        backend_metadata={expression_key: expression},
    )


def _packs(
    *, changed_expression: str | None = None, context_variable: bool = False
) -> tuple[NormPack, NormPack]:
    """The CLI fixture uses literals; the API fixture exercises actual context."""
    subject = "income" if context_variable else "2"
    changed_expression = changed_expression or f"{subject} >= 3"
    same = _rule("n.same", RuleType.PERMISSION, f"{subject} >= 1")
    return (
        NormPack(
            pack_id="pack.old",
            jurisdiction="ua",
            norms=[
                same,
                _rule("n.modified", RuleType.OBLIGATION, f"{subject} >= 1"),
                _rule("n.removed", RuleType.PROHIBITION, f"{subject} > 1"),
            ],
        ),
        NormPack(
            pack_id="pack.new",
            jurisdiction="ua",
            norms=[
                same,
                _rule("n.modified", RuleType.OBLIGATION, changed_expression),
                _rule("n.added", RuleType.PERMISSION, f"{subject} >= 1"),
            ],
        ),
    )


def _read_fresh_chain(cas_root: Path, report_ref: ArtifactRef) -> tuple[NormImpactReport, NormDiff]:
    """The canonical reader follows only the selected ref recovered from the report."""
    result = load_norm_impact_report(FileSystemCAS(cas_root), report_ref)
    assert result.diff_binding == "exact_selected"
    assert result.diff is not None
    return result.report, result.diff


def _assert_real_comparison(report: NormImpactReport, diff: NormDiff) -> None:
    assert report.schema_version == "1.1"
    assert report.norm_diff_artifact_ref is not None
    assert report.norm_diff_artifact_ref.manifest_profile_sha256 is not None
    assert report.passes_executed == ["legal"]
    assert report.metadata["legal_backend"] == "expr_ast"
    assert report.metadata["legal_evaluation_scope"] == "selected_backend_rules_only"
    assert report.metadata["comparison_context_binding"] == "not_established"
    assert report.metadata["declared_old_jurisdiction"] == "ua"
    assert report.metadata["declared_new_jurisdiction"] == "ua"
    assert (report.metadata["old_issues_total"], report.metadata["new_issues_total"]) == (1, 1)
    assert (report.norms_added, report.norms_modified, report.norms_removed) == (1, 1, 1)
    assert [(change.norm_id, change.change_type) for change in diff.changes] == [
        ("n.added", NormChangeType.ADDED),
        ("n.modified", NormChangeType.MODIFIED),
        ("n.removed", NormChangeType.REMOVED),
        ("n.same", NormChangeType.UNCHANGED),
    ]
    assert len(report.compliance_deltas) == 2
    deltas = {delta.norm_id: delta for delta in report.compliance_deltas}
    assert set(deltas) == {"n.modified", "n.removed"}
    assert deltas["n.modified"].transition is ComplianceTransition.NEW_ISSUE
    assert deltas["n.modified"].new_issue is not None
    assert deltas["n.modified"].new_issue.code == "n.modified"
    assert deltas["n.modified"].new_issue.pass_id == report.passes_executed[0]
    assert deltas["n.removed"].transition is ComplianceTransition.RESOLVED_ISSUE
    assert deltas["n.removed"].old_issue is not None
    assert deltas["n.removed"].old_issue.code == "n.removed"
    assert deltas["n.removed"].old_issue.pass_id == report.passes_executed[0]
    assert (report.new_blockers, report.resolved_blockers) == (1, 1)

    # This is an explicit expected public value, not an authority gate or a
    # general natural-language classifier. The mapping follows LA-017 and
    # distinguishes each old assertive producer description from the candidate.
    expected = {
        "compliance_cost": (
            ["n.modified"],
            "Candidate topic inferred from an obligation rule type; no cost or effect "
            "has been measured.",
        ),
        "operational_restrictions": (
            ["n.removed"],
            "Candidate topic inferred from a prohibition rule type; no restriction or "
            "effect has been measured.",
        ),
        "regulatory_flexibility": (
            ["n.added"],
            "Candidate topic inferred from a permission rule type; no flexibility or "
            "effect has been measured.",
        ),
    }
    assert {topic.kpi_id for topic in report.affected_kpis} == set(expected)
    for topic in report.affected_kpis:
        norm_ids, description = expected[topic.kpi_id]
        assert topic.model_dump(mode="json") == {
            "kpi_id": topic.kpi_id,
            "description": description,
            "affected_norm_ids": norm_ids,
            "estimated_direction": "unknown",
        }
    decision = authority_surface_decision(report.model_dump(mode="json"), surface="lex_impact")
    assert decision.blocking is True
    assert decision.status == "blocked"
    assert decision.reason == "authority_surface_signal_missing"


def test_real_impact_report_reopens_its_diff_and_preserves_issue_and_topic_semantics(
    tmp_path: Path,
) -> None:
    """A genuine expr_ast pass survives duplicate-plan admission and fresh consumption."""
    cas = FileSystemCAS(tmp_path / "cas")
    old_pack, new_pack = _packs(context_variable=True)
    one = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
    ).analyze(old_pack, new_pack, context={"income": 2}, decision_packet_ref="decision.test")
    duplicate = NormImpactAnalyzer(
        cas, passes=("legal", "legal"), legal_backend="expr_ast", report_schema_version="1.1"
    ).analyze(old_pack, new_pack, context={"income": 2}, decision_packet_ref="decision.test")
    assert duplicate.report_id == one.report_id
    assert duplicate.cas_artifact_id == one.cas_artifact_id
    assert duplicate.cas_artifact_id is not None
    assert duplicate.cas_artifact_ref is not None
    report, diff = _read_fresh_chain(cas.root, duplicate.cas_artifact_ref)
    assert report.cas_artifact_id is None  # persisted bytes are not self-referential
    assert report.decision_packet_ref == "decision.test"
    _assert_real_comparison(report, diff)
    markdown = render_impact_markdown(report)
    assert "## Candidate Impact Topics" in markdown
    assert "not measured effects or legal conclusions" in markdown
    assert "The report records expr_ast" in markdown
    assert "comparison-context binding are not established" in markdown


def test_impact_cli_emits_real_backend_report_and_fresh_json_and_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI backend selection and both formats use the persisted comparison's values."""
    old_pack, new_pack = _packs()
    old_path, new_path = tmp_path / "old.json", tmp_path / "new.json"
    old_path.write_text(old_pack.model_dump_json(), encoding="utf-8")
    new_path.write_text(new_pack.model_dump_json(), encoding="utf-8")
    cas_root = tmp_path / "cas"
    argv = [
        "lex",
        "impact",
        str(old_path),
        str(new_path),
        "--passes",
        "legal,legal",
        "--legal-backend",
        "expr_ast",
        "--report-schema-version",
        "1.1",
        "--cas-root",
        str(cas_root),
    ]
    assert main([*argv, "--format", "json"]) == 0
    cli_report = NormImpactReport.model_validate(json.loads(capsys.readouterr().out))
    assert cli_report.cas_artifact_id is not None
    assert cli_report.cas_artifact_ref is not None
    report, diff = _read_fresh_chain(cas_root, cli_report.cas_artifact_ref)
    external_refs = {"cas_artifact_id", "cas_artifact_ref"}
    assert report.model_dump(exclude=external_refs) == cli_report.model_dump(exclude=external_refs)
    _assert_real_comparison(report, diff)
    assert main([*argv, "--format", "md"]) == 0
    assert capsys.readouterr().out == render_impact_markdown(report) + "\n"


def test_impact_cli_default_stub_is_explicitly_limited_and_bad_backend_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The historical default is retained without implying a real rule evaluation."""
    old_pack, new_pack = _packs()
    old_path, new_path = tmp_path / "old.json", tmp_path / "new.json"
    old_path.write_text(old_pack.model_dump_json(), encoding="utf-8")
    new_path.write_text(new_pack.model_dump_json(), encoding="utf-8")
    cas_root = tmp_path / "cas"
    argv = [
        "lex",
        "impact",
        str(old_path),
        str(new_path),
        "--passes",
        "legal",
        "--cas-root",
        str(cas_root),
    ]
    assert main([*argv, "--format", "json"]) == 0
    report = NormImpactReport.model_validate(json.loads(capsys.readouterr().out))
    assert report.metadata["legal_backend"] == "stub"
    assert report.metadata["legal_evaluation_scope"] == "not_implemented"
    assert report.schema_version == "1.0"
    assert report.cas_artifact_ref is None and report.cas_artifact_id is not None
    assert report.norm_diff_artifact_ref is None
    loaded = load_norm_impact_report(FileSystemCAS(cas_root), report.cas_artifact_id)
    assert loaded.diff_binding == "legacy_unbound" and loaded.diff is not None
    persisted = loaded.report
    assert persisted.metadata["legal_backend"] == "stub"
    assert (persisted.metadata["old_issues_total"], persisted.metadata["new_issues_total"]) == (
        3,
        3,
    )
    assert {delta.norm_id for delta in persisted.compliance_deltas} == {"n.added", "n.removed"}
    assert all(
        issue.code == "NORM_NOT_IMPLEMENTED"
        for delta in persisted.compliance_deltas
        for issue in (delta.old_issue, delta.new_issue)
        if issue is not None
    )
    assert main([*argv, "--format", "md"]) == 0
    assert (
        "The report records the stub backend, which does not evaluate legal rules."
        in capsys.readouterr().out
    )
    assert main([*argv, "--legal-backend", "expr_ast", "--format", "json"]) == 0
    evaluated = NormImpactReport.model_validate(json.loads(capsys.readouterr().out))
    assert evaluated.report_id == report.report_id
    assert evaluated.cas_artifact_id != report.cas_artifact_id

    absent_root = tmp_path / "invalid-backend-cas"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "lex",
                "impact",
                str(old_path),
                str(new_path),
                "--legal-backend",
                "invalid",
                "--cas-root",
                str(absent_root),
            ]
        )
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert not absent_root.exists()


def test_historical_report_without_backend_metadata_stays_readable(tmp_path: Path) -> None:
    """An old schema-1.0 report is not silently assigned a new backend."""
    cas = FileSystemCAS(tmp_path / "cas")
    legacy = NormImpactReport(
        report_id="lex.impact_report.legacy",
        old_pack_id="pack.old",
        new_pack_id="pack.new",
        jurisdiction="ua",
        passes_executed=["legal"],
        metadata={"profile": "strict", "old_issues_total": 0, "new_issues_total": 0},
    )
    ref = cas.put_json(
        legacy.model_dump(mode="json"),
        PutOptions(
            kind="lex.norm_impact_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.lex.NormImpactReport", version="1.0"),
        ),
    )
    loaded = load_norm_impact_report(FileSystemCAS(cas.root), str(ref.artifact_id))
    assert loaded.diff_binding == "legacy_absent"
    assert loaded.report.metadata == legacy.metadata
    assert "backend or its evaluation scope is not established" in render_impact_markdown(
        loaded.report
    )


def test_legacy_report_id_is_coarse_while_diff_and_report_cas_ids_bind_content(
    tmp_path: Path,
) -> None:
    """Do not silently change historical IDs when equal-count diffs differ."""
    cas = FileSystemCAS(tmp_path / "cas")
    analyzer = NormImpactAnalyzer(cas, passes=(), report_schema_version="1.1")
    first = analyzer.analyze(*_packs(changed_expression="2 >= 3"))
    second = analyzer.analyze(*_packs(changed_expression="2 >= 4"))
    assert first.cas_artifact_ref is not None and second.cas_artifact_ref is not None
    first_report, first_diff = _read_fresh_chain(cas.root, first.cas_artifact_ref)
    second_report, second_diff = _read_fresh_chain(cas.root, second.cas_artifact_ref)
    assert first_diff.modified_count == second_diff.modified_count == 1
    assert first_report.report_id == second_report.report_id
    assert first_report.norm_diff_ref != second_report.norm_diff_ref
    assert first.cas_artifact_id != second.cas_artifact_id


def test_selected_diff_profile_is_reconciled_with_issued_report_manifest(tmp_path: Path) -> None:
    """One payload with a different manifest view cannot be substituted for the issued edge."""
    cas = FileSystemCAS(tmp_path / "cas")
    produced = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
    ).analyze(*_packs())
    assert produced.cas_artifact_ref is not None
    assert produced.norm_diff_artifact_ref is not None
    issued = produced.norm_diff_artifact_ref
    received = load_norm_impact_report(FileSystemCAS(cas.root), produced.cas_artifact_ref)
    assert received.diff_binding == "exact_selected" and received.diff is not None

    alternative = cas.put_json(
        load_core_json_artifact(cas, issued),
        PutOptions(
            kind=NormDiff.ARTIFACT_KIND,
            media_type=NormDiff.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormDiff.ARTIFACT_SCHEMA_NAME, version="1.0"),
            producer=ProducerInfo(component="polisyos.tests.lex.alternative", version="1"),
        ),
        return_selected_profile=True,
    )
    assert alternative.artifact_id == issued.artifact_id
    assert alternative.manifest_profile_sha256 != issued.manifest_profile_sha256

    # Preserve the original report payload, ID and markers, but select a
    # counterfeit report manifest whose input edge points to another view.
    report_payload = received.report.model_dump(mode="json")
    forged_report = cas.put_json(
        report_payload,
        PutOptions(
            kind=NormImpactReport.ARTIFACT_KIND,
            media_type=NormImpactReport.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormImpactReport.ARTIFACT_SCHEMA_NAME, version="1.1"),
            inputs=[input_ref_from_artifact_ref(alternative, role="norm_diff")],
        ),
        return_selected_profile=True,
    )
    assert forged_report.artifact_id == produced.cas_artifact_ref.artifact_id
    assert (
        forged_report.manifest_profile_sha256 != produced.cas_artifact_ref.manifest_profile_sha256
    )
    with pytest.raises(ValueError, match="report_norm_diff_input_mismatch"):
        load_norm_impact_report(FileSystemCAS(cas.root), forged_report)
    assert (
        load_norm_impact_report(FileSystemCAS(cas.root), produced.cas_artifact_ref).diff
        == received.diff
    )

    # The converse forgery changes only the payload's selected profile while
    # preserving the original manifest edge and common content ID.
    replaced_payload = dict(report_payload)
    replaced_payload["norm_diff_artifact_ref"] = alternative.model_dump(mode="json")
    replaced_report = cas.put_json(
        replaced_payload,
        PutOptions(
            kind=NormImpactReport.ARTIFACT_KIND,
            media_type=NormImpactReport.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormImpactReport.ARTIFACT_SCHEMA_NAME, version="1.1"),
            inputs=[input_ref_from_artifact_ref(issued, role="norm_diff")],
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="report_norm_diff_input_mismatch"):
        load_norm_impact_report(FileSystemCAS(cas.root), replaced_report)

    # Profile presence, kind and payload/edge identity are all load-bearing.
    missing_profile = produced.cas_artifact_ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(ValueError, match="selected_report_profile_required"):
        load_norm_impact_report(FileSystemCAS(cas.root), missing_profile)
    wrong_kind = produced.cas_artifact_ref.model_copy(update={"kind": "other.kind"})
    with pytest.raises(ValueError):
        load_norm_impact_report(FileSystemCAS(cas.root), wrong_kind)
    missing_ref_payload = dict(report_payload)
    missing_ref_payload.pop("norm_diff_artifact_ref")
    missing_ref = cas.put_json(
        missing_ref_payload,
        PutOptions(
            kind=NormImpactReport.ARTIFACT_KIND,
            media_type=NormImpactReport.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormImpactReport.ARTIFACT_SCHEMA_NAME, version="1.1"),
            inputs=[input_ref_from_artifact_ref(issued, role="norm_diff")],
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="selected_norm_diff_reference_required"):
        load_norm_impact_report(FileSystemCAS(cas.root), missing_ref)


def _persist_selected_report_payload(
    cas: FileSystemCAS, payload: dict[str, object], diff_ref: ArtifactRef
) -> ArtifactRef:
    return cas.put_json(
        payload,
        PutOptions(
            kind=NormImpactReport.ARTIFACT_KIND,
            media_type=NormImpactReport.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormImpactReport.ARTIFACT_SCHEMA_NAME, version="1.1"),
            inputs=[input_ref_from_artifact_ref(diff_ref, role="norm_diff")],
        ),
        return_selected_profile=True,
    )


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("norms_added", "report_norm_diff_counts_mismatch"),
        ("norms_removed", "report_norm_diff_counts_mismatch"),
        ("norms_modified", "report_norm_diff_counts_mismatch"),
        ("topic_norm_ids", "report_norm_diff_topics_mismatch"),
        ("topic_description", "report_norm_diff_topics_mismatch"),
        ("topic_direction", "report_norm_diff_topics_mismatch"),
        ("topic_omitted", "report_norm_diff_topics_mismatch"),
        ("report_id", "report_norm_diff_id_mismatch"),
        ("passes_executed", "report_pass_plan_invalid"),
        ("delta_transition", "report_compliance_delta_inconsistent"),
        ("delta_pass_id", "report_compliance_delta_inconsistent"),
        ("delta_fingerprint", "report_compliance_delta_inconsistent"),
        ("delta_norm_id", "report_compliance_delta_inconsistent"),
        ("delta_missing_issue", "report_compliance_delta_inconsistent"),
        ("delta_reordered", "report_compliance_delta_inconsistent"),
        ("issue_pass_not_run", "report_issue_pass_plan_mismatch"),
        ("old_issue_total", "report_issue_total_below_carried_issues"),
        ("new_issue_total", "report_issue_total_below_carried_issues"),
        ("new_blockers", "report_compliance_delta_counts_mismatch"),
        ("resolved_blockers", "report_compliance_delta_counts_mismatch"),
        ("new_warnings", "report_compliance_delta_counts_mismatch"),
        ("resolved_warnings", "report_compliance_delta_counts_mismatch"),
        ("severity_changed", "report_compliance_delta_counts_mismatch"),
        ("jurisdiction", "report_norm_diff_scope_mismatch"),
        ("old_pack_id", "report_norm_diff_scope_mismatch"),
        ("new_pack_id", "report_norm_diff_scope_mismatch"),
        ("declared_new_jurisdiction", "report_declared_jurisdiction_mismatch"),
    ],
)
def test_selected_report_refuses_forged_derived_values(
    tmp_path: Path, field: str, error: str
) -> None:
    """A correct selected edge cannot launder false locally derivable report values."""
    cas = FileSystemCAS(tmp_path / "cas")
    produced = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
    ).analyze(*_packs())
    assert produced.cas_artifact_ref is not None and produced.norm_diff_artifact_ref is not None
    received = load_norm_impact_report(FileSystemCAS(cas.root), produced.cas_artifact_ref)
    assert received.diff_binding == "exact_selected" and received.diff is not None
    payload = received.report.model_dump(mode="json")
    if field == "topic_norm_ids":
        payload["affected_kpis"][0]["affected_norm_ids"] = ["n.fake"]
    elif field == "topic_description":
        payload["affected_kpis"][0]["description"] = "Measured effect"
    elif field == "topic_direction":
        payload["affected_kpis"][0]["estimated_direction"] = "increasing"
    elif field == "topic_omitted":
        payload["affected_kpis"] = []
    elif field == "delta_transition":
        delta = next(d for d in payload["compliance_deltas"] if d["transition"] == "new_issue")
        delta["transition"] = "pass_to_fail"
    elif field == "delta_pass_id":
        safety_label = "safety"
        payload["compliance_deltas"][0]["pass_id"] = safety_label
    elif field == "delta_fingerprint":
        payload["compliance_deltas"][0]["fingerprint"] = "counterfeit"
    elif field == "delta_norm_id":
        payload["compliance_deltas"][0]["norm_id"] = "n.counterfeit"
    elif field == "delta_missing_issue":
        delta = payload["compliance_deltas"][0]
        delta["old_issue"] = None
        delta["new_issue"] = None
    elif field == "delta_reordered":
        payload["compliance_deltas"].reverse()
    elif field == "issue_pass_not_run":
        delta = payload["compliance_deltas"][0]
        safety_label = "safety"
        delta["pass_id"] = safety_label
        for issue in (delta["old_issue"], delta["new_issue"]):
            if issue is not None:
                issue["pass_id"] = safety_label
    elif field == "old_issue_total":
        payload["metadata"]["old_issues_total"] = 0
    elif field == "new_issue_total":
        payload["metadata"]["new_issues_total"] = 0
    elif field == "passes_executed":
        payload[field].append("legal")
    elif field == "declared_new_jurisdiction":
        payload["metadata"][field] = "us"
    elif field in {"jurisdiction", "old_pack_id", "new_pack_id", "report_id"}:
        payload[field] = "counterfeit"
    else:
        payload[field] += 99
    forged = _persist_selected_report_payload(cas, payload, produced.norm_diff_artifact_ref)
    with pytest.raises(ValueError, match=error):
        load_norm_impact_report(FileSystemCAS(cas.root), forged)


def test_selected_issue_replay_preserves_omitted_unchanged_pairs(tmp_path: Path) -> None:
    """Replaying carried issues preserves a severity change amid matching pairs.

    This intentionally uses a synthetic backend to exercise multiset pairing;
    the independent expr_ast fixture supplies the actual legal-backend positive.
    """

    class MixedIssueBackend:
        def evaluate(
            self, norm_pack: NormPack | None, context: dict[str, object]
        ) -> list[ComplianceIssue]:
            assert norm_pack is not None
            severities = (
                [IssueSeverity.BLOCKER, IssueSeverity.WARNING, IssueSeverity.WARNING]
                if norm_pack.pack_id == "pack.old"
                else [IssueSeverity.BLOCKER, IssueSeverity.BLOCKER, IssueSeverity.WARNING]
            )
            backend_label = "backend-provided-label"
            return [
                ComplianceIssue(
                    pass_id=backend_label,
                    path=["norm_pack", "n.modified"],
                    message="same issue key",
                    severity=severity,
                    code="MULTISET",
                )
                for severity in severities
            ]

    cas = FileSystemCAS(tmp_path / "cas")
    produced = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend=MixedIssueBackend(), report_schema_version="1.1"
    ).analyze(*_packs())
    assert produced.cas_artifact_ref is not None
    read = load_norm_impact_report(FileSystemCAS(cas.root), produced.cas_artifact_ref)
    assert read.diff_binding == "exact_selected"
    assert read.report.metadata["old_issues_total"] == 3
    assert read.report.metadata["new_issues_total"] == 3
    assert len(read.report.compliance_deltas) == 1
    delta = read.report.compliance_deltas[0]
    assert delta.transition == ComplianceTransition.SEVERITY_CHANGE
    legal_label = "legal"
    assert delta.pass_id == legal_label  # LegalPass normalizes the backend's label.
    assert delta.old_issue is not None and delta.old_issue.severity == IssueSeverity.WARNING
    assert delta.new_issue is not None and delta.new_issue.severity == IssueSeverity.BLOCKER
    assert read.report.metadata["legal_evaluation_scope"] == "backend_semantics_not_established"


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_added_rule",
        "mismatched_norm_id",
        "duplicate_norm_id",
        "false_unchanged",
        "field_delta",
        "diff_summary_count",
    ],
)
def test_selected_report_refuses_incoherent_embedded_diff(tmp_path: Path, corruption: str) -> None:
    """Changes and summary counts are reconstructed from the embedded actual rules."""
    cas = FileSystemCAS(tmp_path / "cas")
    produced = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
    ).analyze(*_packs())
    assert produced.cas_artifact_ref is not None
    read = load_norm_impact_report(FileSystemCAS(cas.root), produced.cas_artifact_ref)
    assert read.diff is not None
    diff_payload = read.diff.model_dump(mode="json")
    changes = diff_payload["changes"]
    by_id = {change["norm_id"]: change for change in changes}
    if corruption == "missing_added_rule":
        by_id["n.added"]["new_rule"] = None
    elif corruption == "mismatched_norm_id":
        by_id["n.added"]["norm_id"] = "n.counterfeit"
    elif corruption == "duplicate_norm_id":
        changes.append(deepcopy(by_id["n.added"]))
    elif corruption == "false_unchanged":
        by_id["n.modified"]["change_type"] = "unchanged"
    elif corruption == "field_delta":
        by_id["n.modified"]["field_deltas"][0]["new_value"] = "counterfeit"
    elif corruption == "diff_summary_count":
        diff_payload["added_count"] = 99
    forged_diff = cas.put_json(
        diff_payload,
        PutOptions(
            kind=NormDiff.ARTIFACT_KIND,
            media_type=NormDiff.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormDiff.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        return_selected_profile=True,
    )
    report_payload = read.report.model_dump(mode="json")
    report_payload["norm_diff_ref"] = str(forged_diff.artifact_id)
    report_payload["norm_diff_artifact_ref"] = forged_diff.model_dump(mode="json")
    forged_report = _persist_selected_report_payload(cas, report_payload, forged_diff)
    with pytest.raises(ValueError, match="selected_norm_diff_inconsistent"):
        load_norm_impact_report(FileSystemCAS(cas.root), forged_report)


def test_cross_jurisdiction_is_declared_for_legacy_and_refused_for_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A legacy comparison may proceed but must not silently hide the new scope."""
    cas = FileSystemCAS(tmp_path / "cas")
    old_pack, new_pack = _packs()
    foreign_pack = new_pack.model_copy(update={"jurisdiction": "us"})
    legacy = NormImpactAnalyzer(cas, passes=()).analyze(old_pack, foreign_pack)
    assert legacy.schema_version == "1.0" and legacy.cas_artifact_id is not None
    received = load_norm_impact_report(FileSystemCAS(cas.root), legacy.cas_artifact_id)
    assert received.diff_binding == "legacy_unbound"
    assert received.report.jurisdiction == "ua"
    assert received.report.metadata["declared_old_jurisdiction"] == "ua"
    assert received.report.metadata["declared_new_jurisdiction"] == "us"
    assert "Input pack declarations differ (old: `ua`, new: `us`)" in render_impact_markdown(
        received.report
    )

    def forbidden_write(*args: object, **kwargs: object) -> None:
        raise AssertionError("mismatched selected report must not persist anything")

    monkeypatch.setattr(cas, "put_json", forbidden_write)
    with pytest.raises(ValueError, match="selected_report_jurisdiction_mismatch"):
        NormImpactAnalyzer(cas, passes=(), report_schema_version="1.1").analyze(
            old_pack, foreign_pack
        )


def test_cli_refuses_cross_jurisdiction_in_opt_in_selected_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI signals the incompatible scopes without writing a report."""
    old_pack, new_pack = _packs()
    paths = [tmp_path / "old.json", tmp_path / "new.json"]
    paths[0].write_text(old_pack.model_dump_json(), encoding="utf-8")
    paths[1].write_text(
        new_pack.model_copy(update={"jurisdiction": "us"}).model_dump_json(), encoding="utf-8"
    )
    output = tmp_path / "report.json"
    code = main(
        [
            "lex",
            "impact",
            *(str(path) for path in paths),
            "--report-schema-version",
            "1.1",
            "--format",
            "json",
            "--output",
            str(output),
            "--cas-root",
            str(tmp_path / "cas"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "selected_report_jurisdiction_mismatch" in captured.err
    assert captured.out == "" and not output.exists()


def test_versioned_reader_first_and_explicit_legacy_writer_rollback(tmp_path: Path) -> None:
    """A new reader accepts 1.0 and 1.1; a strict 1.0 reader rejects the new field."""
    cas = FileSystemCAS(tmp_path / "cas")
    old, new = _packs()
    # No schema option is deliberate: readers must be deployable before any
    # existing writer starts emitting the new schema.
    legacy_writer = NormImpactAnalyzer(cas, passes=("legal",), legal_backend="expr_ast")
    first = legacy_writer.analyze(old, new)
    assert first.schema_version == "1.0" and first.cas_artifact_id is not None
    assert first.norm_diff_artifact_ref is None and first.cas_artifact_ref is None
    legacy_read = load_norm_impact_report(FileSystemCAS(cas.root), first.cas_artifact_id)
    assert legacy_read.diff_binding == "legacy_unbound" and legacy_read.diff is not None
    assert "does not bind the issued manifest profile" in render_impact_markdown(legacy_read.report)

    # Pin the historical 1.0 field set to the base model; its strict extra rule
    # rejects the new payload instead of silently interpreting it as 1.0.
    legacy_names = (
        "schema_version",
        "report_id",
        "old_pack_id",
        "new_pack_id",
        "jurisdiction",
        "norm_diff_ref",
        "norms_added",
        "norms_removed",
        "norms_modified",
        "compliance_deltas",
        "new_blockers",
        "resolved_blockers",
        "new_warnings",
        "resolved_warnings",
        "severity_changed",
        "affected_kpis",
        "passes_executed",
        "decision_packet_ref",
        "cas_artifact_id",
        "metadata",
    )
    legacy_fields = {
        name: (
            NormImpactReport.model_fields[name].annotation,
            deepcopy(NormImpactReport.model_fields[name]),
        )
        for name in legacy_names
    }
    legacy_fields["schema_version"] = (str, "1.0")
    legacy_reader = create_model(
        "StrictLegacyNormImpactReport", __config__=ConfigDict(extra="forbid"), **legacy_fields
    )
    legacy_reader.model_validate(legacy_read.report.model_dump(mode="json"))

    modern = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
    ).analyze(old, new)
    assert modern.schema_version == "1.1" and modern.cas_artifact_ref is not None
    modern_read = load_norm_impact_report(FileSystemCAS(cas.root), modern.cas_artifact_ref)
    assert modern_read.diff_binding == "exact_selected"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        legacy_reader.model_validate(modern_read.report.model_dump(mode="json"))
    with pytest.raises(ValueError, match="selected_report_profile_required"):
        load_norm_impact_report(FileSystemCAS(cas.root), modern.cas_artifact_id)

    rollback_writer = NormImpactAnalyzer(
        cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.0"
    )
    after_rollback = rollback_writer.analyze(old, new)
    assert after_rollback.cas_artifact_id == first.cas_artifact_id
    assert after_rollback.report_id == modern.report_id == first.report_id
    assert (
        load_norm_impact_report(
            FileSystemCAS(cas.root), after_rollback.cas_artifact_id
        ).diff_binding
        == "legacy_unbound"
    )


def test_unpersisted_custom_backend_never_becomes_verified_backend_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A custom self-label cannot turn a candidate object into issued evidence."""

    class CustomBackend:
        @property
        def backend_id(self) -> str:
            return "expr_ast"

        def evaluate(self, norm_pack: NormPack | None, context: dict[str, object]) -> list[object]:
            return []

    cas = FileSystemCAS(tmp_path / "cas")

    def forbidden_write(*args: object, **kwargs: object) -> None:
        raise AssertionError("persist=False must not write a diff or report")

    monkeypatch.setattr(cas, "put_json", forbidden_write)
    report = NormImpactAnalyzer(cas, passes=("legal",), legal_backend=CustomBackend()).analyze(
        *_packs(), persist=False
    )
    assert report.schema_version == "1.0"
    assert report.norm_diff_ref is None and report.norm_diff_artifact_ref is None
    assert report.cas_artifact_id is None and report.cas_artifact_ref is None
    assert report.metadata["legal_backend"] == "custom"
    assert report.metadata["legal_evaluation_scope"] == "backend_semantics_not_established"
    assert report.metadata["comparison_context_binding"] == "not_established"
    assert authority_surface_decision(report.model_dump(mode="json"), surface="lex_impact").blocking

    with pytest.raises(ValueError, match="Unsupported impact report schema version"):
        NormImpactAnalyzer(cas, report_schema_version="2.0")  # type: ignore[arg-type]
