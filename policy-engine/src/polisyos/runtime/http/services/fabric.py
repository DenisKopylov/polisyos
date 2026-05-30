"""Product-facing Fabric integration service for Runtime API closeout."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.core.contracts.runtime import (
    ApiMeta,
    FabricImpactAnalysisRequest,
    FabricImpactAnalysisResponse,
    FabricImpactRecord,
    FabricQualityBatchResponse,
    FabricReplayRunResponse,
    FabricSourceScorecardsResponse,
    FabricTrustBatchResponse,
    TemporalScope,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.fabric.evidence.decision_data import FabricDecisionData, FabricDecisionDataCoverage

    from .lineage import LineageService
    from .run_index import IndexedRunRecord


class FabricIntegrationService:
    """Build additive Fabric payloads consumed by downstream product surfaces."""

    def __init__(
        self,
        *,
        lineage_service: LineageService,
        source_scorecards_snapshot: Path | None = None,
    ) -> None:
        self._lineage = lineage_service
        self._source_scorecards_snapshot = source_scorecards_snapshot or _default_scorecards_path()

    def build_source_scorecards_response(
        self,
        *,
        meta: ApiMeta,
    ) -> FabricSourceScorecardsResponse:
        """Load the committed source-scorecard snapshot for dashboard/API consumers."""
        snapshot = _load_json(self._source_scorecards_snapshot)
        scorecards = snapshot.get("scorecards")
        if not isinstance(scorecards, dict):
            scorecards = {}
        generated_at = _parse_datetime(snapshot.get("generated_at"))
        return FabricSourceScorecardsResponse(
            meta=meta,
            schema_version=str(snapshot.get("schema_version") or "fabric.source_scorecard.v1"),
            generated_at=generated_at,
            count=len(scorecards),
            scorecards={
                str(contract_id): dict(payload)
                for contract_id, payload in sorted(scorecards.items())
                if isinstance(payload, dict)
            },
        )

    def build_quality_batch_response(
        self,
        *,
        meta: ApiMeta,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None = None,
        decision_data_ids: list[str] | None = None,
    ) -> FabricQualityBatchResponse:
        """Return Fabric quality refs for one run in a single lookup."""
        decision_data, coverage = self._decision_data_for_run(
            run,
            temporal_scope=temporal_scope,
            decision_data_ids=decision_data_ids,
        )
        return FabricQualityBatchResponse(
            meta=meta,
            run_id=run.run_id,
            temporal_scope=temporal_scope,
            quality_refs={
                item_id: quality.model_dump(mode="json")
                for item_id, quality in self._lineage.build_quality_refs_batch(
                    decision_data
                ).items()
            },
            coverage=coverage.model_dump(mode="json"),
        )

    def build_trust_batch_response(
        self,
        *,
        meta: ApiMeta,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None = None,
        decision_data_ids: list[str] | None = None,
    ) -> FabricTrustBatchResponse:
        """Return Fabric quality/access/lineage/replay/time refs in one lookup."""
        decision_data, coverage = self._decision_data_for_run(
            run,
            temporal_scope=temporal_scope,
            decision_data_ids=decision_data_ids,
        )
        return FabricTrustBatchResponse(
            meta=meta,
            run_id=run.run_id,
            temporal_scope=temporal_scope,
            trust_refs=self._lineage.build_trust_refs_batch(decision_data),
            coverage=coverage.model_dump(mode="json"),
        )

    def build_replay_response(
        self,
        *,
        meta: ApiMeta,
        run: IndexedRunRecord,
        temporal_scope: TemporalScope | None = None,
    ) -> FabricReplayRunResponse:
        """Return replay refs for all decision-bearing Fabric values in a run."""
        decision_data, coverage = self._lineage.build_fabric_decision_data_for_run(
            run,
            temporal_scope=temporal_scope,
        )
        replay_refs = {
            item.id: item.replay.model_dump(mode="json")
            for item in sorted(decision_data, key=lambda row: row.id)
        }
        status_counts = Counter(str(ref.get("status") or "unknown") for ref in replay_refs.values())
        return FabricReplayRunResponse(
            meta=meta,
            run_id=run.run_id,
            temporal_scope=temporal_scope,
            replay_refs=replay_refs,
            status_counts=dict(sorted(status_counts.items())),
            coverage=coverage.model_dump(mode="json"),
        )

    def build_impact_response(
        self,
        *,
        meta: ApiMeta,
        request: FabricImpactAnalysisRequest,
        run: IndexedRunRecord | None = None,
        temporal_scope: TemporalScope | None = None,
    ) -> FabricImpactAnalysisResponse:
        """Build compact impact rows for lineage refs and source contracts."""
        decision_data: list[FabricDecisionData] = []
        if run is not None:
            decision_data, _coverage = self._lineage.build_fabric_decision_data_for_run(
                run,
                temporal_scope=temporal_scope,
            )
        lineage_ids = list(dict.fromkeys(request.lineage_ids))
        if not lineage_ids and decision_data:
            lineage_ids = list(dict.fromkeys(item.lineage.id for item in decision_data))
        lineages = self._lineage.build_runtime_lineage_batch(lineage_ids)
        data_by_lineage: defaultdict[str, list[FabricDecisionData]] = defaultdict(list)
        data_by_source_contract: defaultdict[str, list[FabricDecisionData]] = defaultdict(list)
        for item in decision_data:
            data_by_lineage[item.lineage.id].append(item)
            data_by_source_contract[item.source_contract.id].append(item)

        impacts: list[FabricImpactRecord] = []
        for lineage in lineages:
            linked_data = data_by_lineage.get(lineage.id, [])
            impacts.append(
                FabricImpactRecord(
                    subject_id=lineage.id,
                    subject_kind="lineage",
                    lineage_status=lineage.status,
                    quality_status=_single_status(item.quality.status for item in linked_data),
                    replay_status=_single_status(item.replay.status for item in linked_data),
                    downstream_refs=sorted({edge.target_id for edge in lineage.edges}),
                    upstream_refs=sorted({edge.source_id for edge in lineage.edges}),
                    affected_decision_data_ids=sorted(item.id for item in linked_data),
                    source_contract_ids=sorted(
                        {item.source_contract.id for item in linked_data}
                    ),
                    evidence_refs=sorted(
                        {
                            evidence_ref
                            for item in linked_data
                            for evidence_ref in item.lineage.raw_evidence_refs
                        }
                    ),
                    notes=["lineage graph loaded lazily through /api/v1/lineage/{lineage_id}"],
                )
            )

        for source_contract_id in dict.fromkeys(request.source_contract_ids):
            linked_data = data_by_source_contract.get(source_contract_id, [])
            scorecard = self._scorecard_for(source_contract_id)
            evidence_refs = []
            if scorecard is not None:
                evidence = scorecard.get("evidence")
                if isinstance(evidence, dict):
                    evidence_refs = [
                        str(value)
                        for value in evidence.values()
                        if isinstance(value, str) and value
                    ]
            impacts.append(
                FabricImpactRecord(
                    subject_id=source_contract_id,
                    subject_kind="source_contract",
                    lineage_status="verified" if linked_data else "pending",
                    quality_status=_single_status(item.quality.status for item in linked_data),
                    replay_status=_single_status(item.replay.status for item in linked_data),
                    affected_decision_data_ids=sorted(item.id for item in linked_data),
                    source_contract_ids=[source_contract_id],
                    evidence_refs=evidence_refs,
                    notes=[
                        (
                            f"source scorecard grade={scorecard.get('grade')}"
                            if scorecard is not None
                            else "source scorecard not found in committed snapshot"
                        )
                    ],
                )
            )

        return FabricImpactAnalysisResponse(
            meta=meta,
            temporal_scope=temporal_scope,
            impacts=impacts,
            summary={
                "run_id": run.run_id if run is not None else None,
                "lineage_count": len(lineage_ids),
                "source_contract_count": len(request.source_contract_ids),
                "decision_data_count": len(decision_data),
                "impact_count": len(impacts),
            },
        )

    def _decision_data_for_run(
        self,
        run: IndexedRunRecord,
        *,
        temporal_scope: TemporalScope | None,
        decision_data_ids: list[str] | None,
    ) -> tuple[list[FabricDecisionData], FabricDecisionDataCoverage]:
        decision_data, coverage = self._lineage.build_fabric_decision_data_for_run(
            run,
            temporal_scope=temporal_scope,
        )
        ids = {item_id for item_id in decision_data_ids or [] if item_id}
        if ids:
            decision_data = [item for item in decision_data if item.id in ids]
            coverage = coverage.model_copy(
                update={
                    "decision": len(decision_data),
                    "total": len(decision_data),
                    "traced": sum(item.lineage.status != "untraced" for item in decision_data),
                    "untraced": sum(item.lineage.status == "untraced" for item in decision_data),
                }
            )
        return decision_data, coverage

    def _scorecard_for(self, source_contract_id: str) -> dict[str, object] | None:
        snapshot = _load_json(self._source_scorecards_snapshot)
        scorecards = snapshot.get("scorecards")
        if not isinstance(scorecards, dict):
            return None
        row = scorecards.get(source_contract_id)
        return dict(row) if isinstance(row, dict) else None


def _single_status(values: Iterable[object]) -> str | None:
    unique = sorted({str(value) for value in values if value is not None})
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _default_scorecards_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "schemas" / "snapshots" / "fabric" / "source_scorecards.json"
        if candidate.exists():
            return candidate
    return Path("schemas/snapshots/fabric/source_scorecards.json")


__all__ = ["FabricIntegrationService"]
