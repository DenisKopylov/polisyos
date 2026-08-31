from __future__ import annotations

import ast
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous.incident import (
    IncidentReport,
    IncidentSeverity,
    persist_incident_monitor_event,
    persist_incident_report,
)
from tools.quality.validation import decomposition_preflight


def test_incident_monitor_bridge_removes_exactly_its_static_scc(monkeypatch) -> None:
    incident = "polisyos.scientist.governance.continuous.incident"
    monitors = "polisyos.scientist.governance.continuous.monitors"

    graph = decomposition_preflight.collect_import_graph()
    canonical_edges = {
        (str(edge["source"]), str(edge["target"])) for edge in graph["edges"]
    }
    canonical_cycles = {
        tuple(sorted(str(module) for module in cycle["modules"]))
        for cycle in graph["cycles"]
    }

    assert (incident, monitors) in canonical_edges
    assert (monitors, incident) not in canonical_edges
    assert not any({incident, monitors}.issubset(cycle) for cycle in canonical_cycles)

    original_parse = decomposition_preflight._parse_python
    monitors_path = (
        decomposition_preflight.SRC_ROOT
        / "polisyos"
        / "scientist"
        / "governance"
        / "continuous"
        / "monitors.py"
    ).resolve()

    def _parse_with_counter_edge(path: Path) -> ast.Module | None:
        tree = original_parse(path)
        if tree is not None and path.resolve() == monitors_path:
            counter_edge = ast.parse(
                "from polisyos.scientist.governance.continuous.incident "
                "import IncidentReport"
            ).body[0]
            tree.body.insert(0, counter_edge)
        return tree

    monkeypatch.setattr(decomposition_preflight, "_parse_python", _parse_with_counter_edge)
    counterfactual_cycles = {
        tuple(sorted(str(module) for module in cycle["modules"]))
        for cycle in decomposition_preflight.collect_import_graph()["cycles"]
    }

    assert counterfactual_cycles - canonical_cycles == {tuple(sorted((incident, monitors)))}
    assert canonical_cycles - counterfactual_cycles == set()


def test_incident_owner_persists_content_bound_monitor_event(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    decision_ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="scientist.decision_packet",
        media_type="application/json",
    )
    incident = IncidentReport(
        incident_id="incident-import-governance",
        decision_packet_ref=decision_ref,
        severity=IncidentSeverity.WARNING,
        reason="A post-publication observation requires review.",
        affected_claim_ids=["claim-import-governance"],
    )
    incident_ref = persist_incident_report(store, incident)

    persisted = persist_incident_monitor_event(
        store,
        incident_report_ref=incident_ref,
        sequence=3,
    )

    assert persisted.event.decision_packet_ref == decision_ref
    assert persisted.event.reason == incident.reason
    assert persisted.event.affected_claim_ids == incident.affected_claim_ids
    assert persisted.event.advisory_posture == "review_required"
    assert persisted.event.perturbation is not None
    assert persisted.event.perturbation.source_class == "incident"
    assert persisted.event.perturbation.incident_report_ref == incident_ref
