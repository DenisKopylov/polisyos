"""Exercise input binding and persisted Lex comparison through real consumers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.legal_evaluation.impact_diff import (
    ComplianceTransition,
    NormImpactAnalyzer,
    NormImpactReport,
)
from polisyos.lex.normpack.diff import NormDiff
from polisyos.lex.simulator.cli import render_impact_markdown
from tools.ops_runners.runtime_cli import main


def _pack(pack_id: str, threshold: int) -> NormPack:
    return NormPack(
        pack_id=pack_id,
        jurisdiction="ua",
        norms=[
            NormRule(
                norm_id="n.income",
                description="Income floor",
                rule_type=RuleType.OBLIGATION,
                backend_refs=["expr_ast"],
                backend_metadata={"must": f"income >= {threshold}"},
            )
        ],
    )


def _read_report(cas: FileSystemCAS, report: NormImpactReport) -> NormImpactReport:
    assert report.cas_artifact_id is not None
    return NormImpactReport.model_validate(
        from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(report.cas_artifact_id)))
    )


@pytest.mark.parametrize("override", [None, "empty", "permissive", "restrictive"])
def test_report_checks_the_compared_packs_despite_context_norm_pack(
    tmp_path: Path, override: str | None
) -> None:
    """The compared packs, rather than a caller context entry, supply legal rules."""
    cas = FileSystemCAS(tmp_path / "cas")
    old_pack, new_pack = _pack("pack.old", 1), _pack("pack.new", 3)
    context: dict[str, object] = {"income": 2}
    if override == "empty":
        context["norm_pack"] = NormPack(pack_id="pack.empty", jurisdiction="ua")
    elif override is not None:
        context["norm_pack"] = _pack("pack.override", 0 if override == "permissive" else 5)
    report = NormImpactAnalyzer(cas, passes=("legal",), legal_backend="expr_ast").analyze(
        old_pack, new_pack, context=context, decision_packet_ref="decision.test"
    )
    persisted = _read_report(cas, report)
    assert persisted.old_pack_id == old_pack.pack_id
    assert persisted.new_pack_id == new_pack.pack_id
    assert persisted.new_blockers == 1
    assert persisted.resolved_blockers == 0
    assert len(persisted.compliance_deltas) == 1
    delta = persisted.compliance_deltas[0]
    assert delta.norm_id == "n.income"
    assert delta.transition is ComplianceTransition.NEW_ISSUE
    assert delta.new_issue is not None and delta.new_issue.code == "n.income"
    assert delta.old_issue is None
    assert persisted.passes_executed == ["legal"]
    assert persisted.decision_packet_ref == "decision.test"
    assert persisted.norm_diff_ref is not None
    diff = NormDiff.model_validate(
        from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(persisted.norm_diff_ref)))
    )
    assert diff.modified_count == 1 and diff.affected_norm_ids == ["n.income"]
    topic = persisted.affected_kpis[0]
    assert topic.kpi_id == "compliance_cost"
    assert topic.estimated_direction == "unknown"
    assert "Candidate Impact Topics" in render_impact_markdown(persisted)


def test_identical_policy_has_no_compliance_transition(tmp_path: Path) -> None:
    """A failing unchanged obligation produces no invented transition or topic."""
    cas = FileSystemCAS(tmp_path / "cas")
    pack = _pack("pack.same", 3)
    report = NormImpactAnalyzer(cas, passes=("legal",), legal_backend="expr_ast").analyze(
        pack, pack, context={"income": 2}
    )
    persisted = _read_report(cas, report)
    assert persisted.metadata["old_issues_total"] == 1
    assert persisted.metadata["new_issues_total"] == 1
    assert persisted.norms_modified == 0
    assert persisted.compliance_deltas == []
    assert persisted.affected_kpis == []


@pytest.mark.parametrize("passes", [("legal", "legal"), ("legal", "safety", "legal", "safety")])
def test_duplicate_pass_plan_preserves_single_execution_report(
    tmp_path: Path, passes: tuple[str, ...]
) -> None:
    """Duplicate plan entries cannot manufacture additional compliance blockers."""
    cas = FileSystemCAS(tmp_path / "cas")
    canonical = tuple(dict.fromkeys(passes))
    old_pack, new_pack = _pack("pack.old", 1), _pack("pack.new", 3)
    expected = NormImpactAnalyzer(cas, passes=canonical, legal_backend="expr_ast").analyze(
        old_pack, new_pack, context={"income": 2}
    )
    actual = NormImpactAnalyzer(cas, passes=passes, legal_backend="expr_ast").analyze(
        old_pack, new_pack, context={"income": 2}
    )
    persisted = _read_report(FileSystemCAS(tmp_path / "cas"), actual)
    assert persisted.new_blockers == 1
    assert persisted.passes_executed == list(canonical)
    assert persisted.metadata["new_issues_total"] == expected.metadata["new_issues_total"]
    assert persisted.compliance_deltas == expected.compliance_deltas
    assert persisted.report_id == expected.report_id
    assert persisted.norm_diff_ref == expected.norm_diff_ref
    assert actual.cas_artifact_id == expected.cas_artifact_id


def test_cli_duplicate_pass_plan_is_canonical_after_persistence(tmp_path: Path, capsys) -> None:
    """The actual CLI consumer uses the admitted unique pass sequence."""
    paths = [tmp_path / "old.json", tmp_path / "new.json"]
    for path, pack in zip(paths, [_pack("pack.old", 1), _pack("pack.new", 3)], strict=True):
        path.write_text(pack.model_dump_json(), encoding="utf-8")
    code = main(
        [
            "lex",
            "impact",
            *(str(p) for p in paths),
            "--passes",
            "legal,legal,safety,legal,safety",
            "--format",
            "json",
            "--cas-root",
            str(tmp_path / "cas"),
        ]
    )
    assert code == 0
    report = NormImpactReport.model_validate(json.loads(capsys.readouterr().out))
    persisted = _read_report(FileSystemCAS(tmp_path / "cas"), report)
    assert persisted.passes_executed == ["legal", "safety"]
    assert persisted.schema_version == "1.0"


def test_explicit_empty_pass_plan_is_preserved(tmp_path: Path) -> None:
    """An empty API plan performs a norm comparison without silently adding checks."""
    cas = FileSystemCAS(tmp_path / "cas")
    report = NormImpactAnalyzer(cas, passes=(), legal_backend="expr_ast").analyze(
        _pack("pack.old", 1), _pack("pack.new", 3), context={"income": 2}
    )
    persisted = _read_report(cas, report)
    assert persisted.passes_executed == []
    assert persisted.metadata["new_issues_total"] == 0
    assert persisted.norms_modified == 1


def test_pass_plan_is_frozen_at_admission(tmp_path: Path) -> None:
    """An accepted mutable caller container cannot change the validated dispatch plan."""
    cas = FileSystemCAS(tmp_path / "cas")
    requested = ["legal"]
    analyzer = NormImpactAnalyzer(cas, passes=requested)  # type: ignore[arg-type]
    requested.append("legla")
    persisted = _read_report(cas, analyzer.analyze(_pack("pack.old", 1), _pack("pack.new", 3)))
    assert persisted.passes_executed == ["legal"]


@pytest.mark.parametrize("passes", [("unknown",), ("legal", "legla"), ("",)])
def test_unknown_pass_cannot_be_attested_as_executed(
    tmp_path: Path, passes: tuple[str, ...]
) -> None:
    """Unsupported configuration is refused before a plausible report is produced."""
    cas = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="Unsupported impact pass"):
        NormImpactAnalyzer(cas, passes=passes).analyze(_pack("pack.old", 1), _pack("pack.new", 3))


def test_cli_refuses_unknown_pass_without_publishing_report(tmp_path: Path, capsys) -> None:
    """The real CLI turns an unsupported pass into an error without report output."""
    old_path, new_path = tmp_path / "old.json", tmp_path / "new.json"
    old_path.write_text(_pack("pack.old", 1).model_dump_json(), encoding="utf-8")
    new_path.write_text(_pack("pack.new", 3).model_dump_json(), encoding="utf-8")
    output_path = tmp_path / "report.json"
    code = main(
        [
            "lex",
            "impact",
            str(old_path),
            str(new_path),
            "--passes",
            "legal,legla",
            "--format",
            "json",
            "--output",
            str(output_path),
            "--cas-root",
            str(tmp_path / "cas"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "Unsupported impact pass" in captured.err
    assert not output_path.exists()
    assert captured.out == ""


def test_cli_native_valid_plan_keeps_historical_json_schema(tmp_path: Path, capsys) -> None:
    """A supported CLI invocation emits the same versioned report for CAS readback."""
    paths = [tmp_path / "old.json", tmp_path / "new.json"]
    for path, pack in zip(paths, [_pack("pack.old", 1), _pack("pack.new", 3)], strict=True):
        path.write_text(pack.model_dump_json(), encoding="utf-8")
    code = main(
        [
            "lex",
            "impact",
            *(str(p) for p in paths),
            "--passes",
            "legal",
            "--format",
            "json",
            "--cas-root",
            str(tmp_path / "cas"),
        ]
    )
    assert code == 0
    report = NormImpactReport.model_validate(json.loads(capsys.readouterr().out))
    assert report.schema_version == "1.0"
    assert report.passes_executed == ["legal"]
    assert report.norms_modified == 1
    assert (
        _read_report(FileSystemCAS(tmp_path / "cas"), report).norm_diff_ref == report.norm_diff_ref
    )
