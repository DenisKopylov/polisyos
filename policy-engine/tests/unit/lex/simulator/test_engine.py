from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.simulator.engine import NormImpactAnalyzer

if TYPE_CHECKING:
    from pathlib import Path


def _rule(norm_id: str, desc: str) -> NormRule:
    return NormRule(norm_id=norm_id, rule_type=RuleType.OBLIGATION, description=desc)


def test_norm_impact_analyzer_persists_report_and_diff(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / ".polisyos")
    old_pack = NormPack(
        pack_id="normpack.old",
        jurisdiction="ua",
        norms=[_rule("n.a", "A"), _rule("n.b", "B")],
    )
    new_pack = NormPack(
        pack_id="normpack.new",
        jurisdiction="ua",
        norms=[_rule("n.a", "A+"), _rule("n.c", "C")],
    )

    analyzer = NormImpactAnalyzer(cas=cas, passes=("legal",))
    report = analyzer.analyze(old_pack, new_pack)

    assert report.norms_added == 1
    assert report.norms_removed == 1
    assert report.norms_modified == 1
    assert report.norm_diff_ref is not None
    assert report.cas_artifact_id is not None
