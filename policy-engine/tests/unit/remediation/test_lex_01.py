from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex import NormImpactAnalyzer as RootNormImpactAnalyzer
from polisyos.lex.legal_evaluation.impact_diff import (
    AffectedKPI,
    ComplianceDelta,
    ComplianceTransition,
    NormImpactAnalyzer,
    NormImpactReport,
)
from polisyos.lex.normpack.diff import (
    FieldDelta,
    NormChange,
    NormChangeType,
    NormDiff,
    diff_norm_packs,
)
from polisyos.lex.simulator import NormImpactAnalyzer as SimulatorNormImpactAnalyzer
from polisyos.lex.simulator.cli import render_impact_markdown
from polisyos.lex.simulator.diff import (
    FieldDelta as SimulatorFieldDelta,
    NormChange as SimulatorNormChange,
    NormChangeType as SimulatorNormChangeType,
    NormDiff as SimulatorNormDiff,
    diff_norm_packs as simulator_diff_norm_packs,
)
from polisyos.lex.simulator.engine import (
    NormImpactAnalyzer as SimulatorEngineNormImpactAnalyzer,
)
from polisyos.lex.simulator.report import (
    AffectedKPI as SimulatorAffectedKPI,
    ComplianceDelta as SimulatorComplianceDelta,
    ComplianceTransition as SimulatorComplianceTransition,
    NormImpactReport as SimulatorNormImpactReport,
)
from polisyos.runtime.quality.authority import authority_surface_decision


def _rule(
    norm_id: str,
    description: str,
    *,
    rule_type: RuleType = RuleType.OBLIGATION,
) -> NormRule:
    return NormRule(norm_id=norm_id, rule_type=rule_type, description=description)


def _pack_pair() -> tuple[NormPack, NormPack]:
    old_pack = NormPack(
        pack_id="normpack.old",
        jurisdiction="ua",
        norms=[
            _rule("n.keep", "keep"),
            _rule("n.modified", "before"),
            _rule("n.removed", "remove"),
        ],
    )
    new_pack = NormPack(
        pack_id="normpack.new",
        jurisdiction="ua",
        norms=[
            _rule("n.keep", "keep"),
            _rule("n.modified", "after"),
            _rule("n.added", "added"),
        ],
    )
    return old_pack, new_pack


def _candidate_topic_report() -> NormImpactReport:
    return NormImpactReport(
        report_id="lex.impact_report.test",
        old_pack_id="normpack.old",
        new_pack_id="normpack.new",
        jurisdiction="ua",
        affected_kpis=[
            AffectedKPI(
                kpi_id="compliance_cost",
                description="Candidate impact topic inferred from an obligation rule type.",
                affected_norm_ids=["n.obligation"],
            )
        ],
    )


def test_move21_legacy_simulator_addresses_alias_canonical_owners_and_behavior() -> None:
    """MOVE-21 keeps old imports identical while moving real owners to Lex packages."""
    assert SimulatorFieldDelta is FieldDelta
    assert SimulatorNormChange is NormChange
    assert SimulatorNormChangeType is NormChangeType
    assert SimulatorNormDiff is NormDiff
    assert simulator_diff_norm_packs is diff_norm_packs
    assert SimulatorEngineNormImpactAnalyzer is NormImpactAnalyzer
    assert SimulatorAffectedKPI is AffectedKPI
    assert SimulatorComplianceDelta is ComplianceDelta
    assert SimulatorComplianceTransition is ComplianceTransition
    assert SimulatorNormImpactReport is NormImpactReport
    assert SimulatorNormImpactAnalyzer is NormImpactAnalyzer
    assert RootNormImpactAnalyzer is NormImpactAnalyzer

    old_pack, new_pack = _pack_pair()
    diff = diff_norm_packs(old_pack, new_pack)

    assert diff.added_count == 1
    assert diff.removed_count == 1
    assert diff.modified_count == 1
    assert diff.unchanged_count == 1
    assert diff.affected_norm_ids == ["n.added", "n.modified", "n.removed"]
    assert [change.change_type for change in diff.changes] == [
        NormChangeType.ADDED,
        NormChangeType.UNCHANGED,
        NormChangeType.MODIFIED,
        NormChangeType.REMOVED,
    ]

    legacy_diff = simulator_diff_norm_packs(old_pack, new_pack)
    assert legacy_diff.model_dump(mode="json") == diff.model_dump(mode="json")


def test_move21_persisted_report_binds_diff_ref_without_self_reference(tmp_path: Path) -> None:
    """The report bytes carry the persisted diff ref, not an impossible CAS self-ref."""
    cas = FileSystemCAS(tmp_path / ".polisyos")
    old_pack, new_pack = _pack_pair()

    report = NormImpactAnalyzer(cas=cas, passes=("legal",)).analyze(old_pack, new_pack)

    assert report.norm_diff_ref is not None
    assert report.cas_artifact_id is not None

    report_payload = from_canonical_bytes(
        cas.get_bytes(ArtifactID.model_validate(report.cas_artifact_id))
    )
    diff_payload = from_canonical_bytes(
        cas.get_bytes(ArtifactID.model_validate(report.norm_diff_ref))
    )

    assert report_payload["norm_diff_ref"] == report.norm_diff_ref
    assert report_payload["cas_artifact_id"] is None
    assert diff_payload["old_pack_id"] == "normpack.old"
    assert diff_payload["new_pack_id"] == "normpack.new"


def test_lex_impact_cli_labels_topic_tags_as_candidate_impact_topics() -> None:
    """CLI display must not present heuristic topic tags as measured KPIs."""
    rendered = render_impact_markdown(_candidate_topic_report())

    assert "## Candidate Impact Topics" in rendered
    assert "## Affected KPIs" not in rendered
    assert "`compliance_cost`" in rendered
    assert "n.obligation" in rendered
    assert "effect_size" not in rendered.lower()


def test_lex_impact_topic_payload_is_blocked_by_real_authority_surface_gate() -> None:
    """A heuristic topic tag alone cannot satisfy an authority-bearing surface."""
    decision = authority_surface_decision(
        _candidate_topic_report().model_dump(mode="json"),
        surface="lex_impact",
    )

    assert decision.blocking is True
    assert decision.status == "blocked"
    assert decision.reason == "authority_surface_signal_missing"
