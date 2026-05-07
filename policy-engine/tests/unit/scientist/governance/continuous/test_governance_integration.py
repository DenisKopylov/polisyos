from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.governance.report import GovernanceReport, GovernanceReportLinks


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_governance_report_links_continuous_governance_sidecars() -> None:
    report_ref = _ref("1", kind="scientist.continuous_governance_report")
    reissue_ref = _ref("2", kind="scientist.reissue_packet")
    withdrawal_ref = _ref("3", kind="scientist.withdrawal_record")

    report = GovernanceReport(
        verdict="human_gate",
        links=GovernanceReportLinks(
            continuous_governance_report_ref=report_ref,
            reissue_packet_ref=reissue_ref,
            withdrawal_record_ref=withdrawal_ref,
        ),
    )

    assert report.links.continuous_governance_report_ref == report_ref
    assert report.links.reissue_packet_ref == reissue_ref
    assert report.links.withdrawal_record_ref == withdrawal_ref
