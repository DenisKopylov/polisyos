"""Exercise direct RetrievalService API custody and N9 semantics."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.core.contracts.control import DataResolveRequest, FetchPlan
    from polisyos.data_forge.read_api.catalog import DatasetCatalogGraph
    from polisyos.fabric.retrieval import RetrievalProviders, RetrievalService

ROOT = Path(__file__).resolve().parents[3]



class _WorldBankFetchOwner(Protocol):
    """Expose the real producer fixture's typed inputs without copying its setup."""

    graph: DatasetCatalogGraph
    plan: FetchPlan
    providers: RetrievalProviders
    store: ArtifactStore | None
    curated_dir: Path
    frame: Any
    http_requests: list[Any]


def _public_retrieval_service(
    owner: _WorldBankFetchOwner, *, dataset_catalog: DatasetCatalogGraph | None
) -> RetrievalService:
    """Build the public retrieval API over the fixture's real producer inputs."""
    from polisyos.fabric.retrieval import RetrievalService

    artifact_store = owner.store
    if artifact_store is None:
        raise AssertionError("producer fixture did not supply an artifact store")
    return RetrievalService(
        curated_dir=owner.curated_dir,
        artifact_store=artifact_store,
        dataset_catalog=dataset_catalog,
        providers=owner.providers,
    )


def _owner_request(owner: _WorldBankFetchOwner) -> DataResolveRequest:
    from polisyos.core.contracts.control import DataNeed, DataResolveRequest

    return DataResolveRequest(
        data_needs=[DataNeed(metric=owner.plan.metric_id)],
        mode="fastlane",
        allow_explore_fallback=False,
        catalog_run_profile="prod_full",
    )


def _resolved_plan(service: RetrievalService, owner: _WorldBankFetchOwner) -> FetchPlan:
    response = service.resolve(_owner_request(owner))
    assert len(response.fetch_plans) == 1
    plan = response.fetch_plans[0]
    assert plan.metric_id == owner.plan.metric_id
    assert plan.connector_id == owner.plan.connector_id
    assert plan.profile_id == owner.plan.profile_id
    assert plan.metadata["resolution_route"] == "catalog"
    return plan


def _full_worldbank_fetch_count(owner: _WorldBankFetchOwner) -> int:
    """Count actual unbounded World Bank data requests recorded by its transport."""
    return sum(
        exchange.kind == "data" and exchange.params.get("per_page") == "1000"
        for exchange in owner.http_requests
    )


def _measurement(
    service: RetrievalService,
    *,
    catalog: DatasetCatalogGraph,
    plan: FetchPlan,
    providers: RetrievalProviders,
    ledger_root: Path,
    promotion_input: Any,
    design_problem: Any,
    persist_payload: bool = True,
    replay_n9: bool = True,
) -> dict[str, Any]:
    """Exercise real custody and optionally replay its N9 consumer obligation."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.fabric.retrieval.custody import FabricFetchCustodyError, resolve_persisted_fetch
    from polisyos.pdc import PromotionObligationClass
    from polisyos.runtime.quality.confidence_ledger import (
        ConfidenceLedgerSession,
        ConfidenceRiskBudgetScope,
    )
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootProducer,
        build_fabric_measurement_requirement,
    )
    from polisyos.runtime.quality.promotion_sequence import (
        CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        PROMOTION_SEQUENCE_REF,
        N9PromotionEvidenceBridgeRepository,
        _run_canonical_promotion_sequence_for_verification,
    )
    from tests._helpers.measurement_execution_binding import measurement_execution_binding

    execution_scope_binding = measurement_execution_binding(ledger_root.parent)
    store = service.artifact_store
    if store is None:
        raise FabricFetchCustodyError("fabric_fetch_store_missing")
    repository = N9PromotionEvidenceBridgeRepository(
        store=store,
        execution_scope_binding=execution_scope_binding,
        measurement_catalog=catalog,
        measurement_providers=providers,
    )
    roots = ()
    refusal = None
    binding = None
    data = None
    try:
        outcome = service.execute_fetch_plans(
            [plan], persist_payload=persist_payload, allow_fallback=False
        )
        execution = outcome.previews[0]
        if execution.fetch_receipt_ref is None:
            raise FabricFetchCustodyError("fabric_fetch_receipt_absent")
        fetched = resolve_persisted_fetch(
            store=store,
            fetch_receipt_ref=execution.fetch_receipt_ref,
            catalog=catalog,
            providers=providers,
        )
        data = fetched.result.data
        selected = fetched.used_plan
        requirement = build_fabric_measurement_requirement(
            catalog=catalog,
            catalog_binding=catalog.bind_fetch_target(
                metric_id=selected.metric_id,
                connector_id=selected.connector_id,
                request_dataset_id=selected.dataset_id,
                profile_id=selected.profile_id,
                filters=selected.filters,
            ),
            design_problem=design_problem,
        )
        envelope = MeasurementRootProducer(
            artifact_store=store,
            execution_scope_binding=execution_scope_binding,
        ).produce_from_fabric_fetch(
            fetch_receipt_ref=execution.fetch_receipt_ref,
            catalog=catalog,
            providers=providers,
            design_problem=design_problem,
            source_requirement=requirement,
        )
        bridge = repository.persist_measurement_root(
            promotion_input=promotion_input,
            envelope=envelope,
        )
        roots = (bridge,)
        binding = {
            "fetch_receipt_ref": execution.fetch_receipt_ref.model_dump(mode="json"),
            "payload_ref": execution.payload_ref.model_dump(mode="json"),
            "measurement_payload_ref": envelope.payload_ref,
            "n9_bridge_ref": bridge.model_dump(mode="json"),
        }
    except FabricFetchCustodyError as exc:
        refusal = exc.code
    if not replay_n9:
        return {
            "custody_refusal": refusal,
            "bindings": binding,
            "data": data,
        }
    current = promotion_input.model_copy(update={"producer_root_refs": roots})
    owner_binding = current.design_problem_binding
    scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{owner_binding.design_problem_id}",
        owner_projection_hash=owner_binding.problem_content_hash,
        epoch_ref=None,
        model_ref=owner_binding.model_spec_ref,
        rule_ref=CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        schema_ref=owner_binding.problem_schema_version,
    )
    ledger = ConfidenceLedgerSession._for_verification(
        ROOT,
        risk_scope=scope,
        artifact_store=FileSystemCAS(ledger_root / "cas"),
        state_root=ledger_root / "state",
    )
    receipt = _run_canonical_promotion_sequence_for_verification(
        current,
        confidence_ledger_session=ledger,
        promotion_evidence_resolver=repository,
    )
    measurement = next(
        row
        for row in receipt.obligations
        if row.obligation_role == "class_gate"
        and row.obligation_class == PromotionObligationClass.MEASUREMENT
    )
    return {
        "measurement_status": measurement.status.value,
        "measurement_detail": measurement.detail,
        "consumer_promotable": receipt.consumer_promotable,
        "custody_refusal": refusal,
        "bindings": binding,
        "data": data,
    }


def test_public_retrieval_constructor_resolves_published_catalog(tmp_path) -> None:
    """A canonical batch-produced graph yields a plan through the public API."""

    from tests.unit.fabric.test_retrieval_fetch_custody import build_worldbank_fetch_owner

    with build_worldbank_fetch_owner(tmp_path) as owner:
        service = _public_retrieval_service(owner, dataset_catalog=owner.graph)
        plan = _resolved_plan(service, owner)
        assert service.artifact_store is owner.store
        assert plan.dataset_id == owner.plan.dataset_id


def test_catalog_removal_refuses_real_fetch(tmp_path) -> None:
    """Removing the public catalog input blocks receipt issuance and full fetch."""
    import pandas as pd

    from polisyos.pdc import PromotionObligationStatus
    from polisyos.runtime.quality.promotion_sequence import N9DesignProblemBinding
    from tests.unit.fabric.test_retrieval_fetch_custody import build_worldbank_fetch_owner
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _d1_worldbank_problem,
        _promotion_input,
    )

    with build_worldbank_fetch_owner(tmp_path) as owner:
        service = _public_retrieval_service(owner, dataset_catalog=owner.graph)
        plan = _resolved_plan(service, owner)
        problem = _d1_worldbank_problem(owner)
        initial = _promotion_input(
            design_problem_binding=N9DesignProblemBinding.from_problem(problem)
        )
        baseline = _measurement(
            service,
            catalog=owner.graph,
            plan=plan,
            providers=owner.providers,
            ledger_root=tmp_path / "baseline-ledger",
            promotion_input=initial,
            design_problem=problem,
        )
        assert baseline["measurement_status"] == PromotionObligationStatus.SATISFIED.value
        assert baseline["custody_refusal"] is None
        assert baseline["bindings"] is not None
        pd.testing.assert_frame_equal(baseline["data"], owner.frame)

        full_fetch_count = _full_worldbank_fetch_count(owner)
        removed = _public_retrieval_service(owner, dataset_catalog=None)
        assert not removed.resolve(_owner_request(owner)).fetch_plans
        negative = _measurement(
            removed,
            catalog=owner.graph,
            plan=plan,
            providers=owner.providers,
            ledger_root=tmp_path / "removed-ledger",
            promotion_input=initial,
            design_problem=problem,
            replay_n9=False,
        )
        assert negative["custody_refusal"] == "catalog_fetch_owner_missing"
        assert negative["bindings"] is None
        assert _full_worldbank_fetch_count(owner) == full_fetch_count


def test_persistence_removal_does_not_satisfy_n9(tmp_path) -> None:
    """A real full fetch without persisted custody cannot satisfy measurement."""
    from polisyos.pdc import PromotionObligationStatus
    from polisyos.runtime.quality.promotion_sequence import N9DesignProblemBinding
    from tests.unit.fabric.test_retrieval_fetch_custody import build_worldbank_fetch_owner
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _d1_worldbank_problem,
        _promotion_input,
    )

    with build_worldbank_fetch_owner(tmp_path) as owner:
        service = _public_retrieval_service(owner, dataset_catalog=owner.graph)
        plan = _resolved_plan(service, owner)
        problem = _d1_worldbank_problem(owner)
        initial = _promotion_input(
            design_problem_binding=N9DesignProblemBinding.from_problem(problem)
        )
        result = _measurement(
            service,
            catalog=owner.graph,
            plan=plan,
            providers=owner.providers,
            ledger_root=tmp_path / "no-persistence-ledger",
            promotion_input=initial,
            design_problem=problem,
            persist_payload=False,
        )
        assert result["data"] is None
        assert result["custody_refusal"] == "fabric_fetch_receipt_absent"
        assert result["measurement_status"] != PromotionObligationStatus.SATISFIED.value
        assert result["consumer_promotable"] is False
        assert _full_worldbank_fetch_count(owner) == len(owner.http_responses)
