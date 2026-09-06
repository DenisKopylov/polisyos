"""End-to-end route binding through the concrete production acquisition port."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.http.services import (
    acquisition_surface_execution as acquisition_surface_execution_module,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionOwnerExecutionResult,
)
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
    build_production_world_bank_wdi_execution_port,
)
from polisyos.runtime.quality import acquisition_executor as acquisition_executor_module
from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _entry,
    _resolver,
    _write_family_receipt,
)
from tests.unit.runtime.quality.test_live_acquisition_executor import (
    _ATTEMPT_ID,
    _family_receipt,
    _route_closure,
)


class _ExecutorObserver:
    """Record the trusted executor boundary without touching a connector provider."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> object:
        self.calls.append(dict(kwargs))
        return SimpleNamespace(
            raw_artifact_id="sha256:" + "a" * 64,
            evidence_bundle_ref=SimpleNamespace(artifact_id="sha256:" + "b" * 64),
            data_snapshot_ref=SimpleNamespace(artifact_id="sha256:" + "c" * 64),
            normalized_data_artifact_id="sha256:" + "d" * 64,
        )


class _CostBasis:
    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "json"
        return {"record_content_hash": "sha256:" + "6" * 64}


class _FixturePort:
    def execute(self, _closure: object) -> object:
        return object()

    def reenter(self, _closure: object, _result: object) -> str:
        return "fixture-reentry"

    def resume_reentry(self, _closure: object, _owner_receipt_refs: object) -> str:
        return "fixture-resume"


def _projection_closure(
    *,
    variable_id: str = "government.balance",
    region: str = "UKR",
    data_time: str = "2024",
) -> object:
    route = _route_closure(
        variable_id=variable_id,
        region=region,
        data_time=data_time,
    )
    return SimpleNamespace(
        tenant_id=route.tenant_id,
        cell_id=route.cell_id,
        run_id=route.run_id,
        route_id=route.route_id,
        design_problem=route.design_problem,
        planner_report={"run_id": "planner-run"},
        planner_record=SimpleNamespace(
            **{
                **vars(route.planner_record),
                "acquisition_id": "acquisition-government-balance",
                "recommended_strategy": SimpleNamespace(
                    value="production_snapshot_build"
                ),
            }
        ),
        cost_basis_record=_CostBasis(),
        source_job_id="job-source",
        source_cycle=SimpleNamespace(cycle_index=1),
        compiled_ref="sha256:" + "2" * 64,
        compiled_content_hash="sha256:" + "3" * 64,
        terminal_event_id="event-terminal",
        design_problem_ref="sha256:" + "4" * 64,
        cost_basis_hash="sha256:" + "5" * 64,
    )


def _port_fixture(
    tmp_path: Path,
    *,
    with_attempt: bool = True,
    use_default_executor: bool = False,
) -> tuple[WorldBankWDIAcquisitionExecutionPort, _ExecutorObserver, Path]:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt_provisions: tuple[dict[str, str], ...] = ()
    if with_attempt:
        receipt_provisions = (
            _write_family_receipt(
                repo_root,
                entry_id=entry.entry_id,
                attempt_id=_ATTEMPT_ID,
                receipt=_family_receipt(),
            ),
        )
    authority, _ = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=receipt_provisions,
    )
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )
    runtime_state_root = tmp_path / "runtime-state"
    observer = _ExecutorObserver()
    port_kwargs: dict[str, object] = {}
    if not use_default_executor:
        port_kwargs["executor"] = observer
    return (
        WorldBankWDIAcquisitionExecutionPort(
            authority=authority,
            registry=registry,
            provision=authority.provision,
            provision_content_sha256=authority.provision_content_sha256,
            runtime_state_root=runtime_state_root,
            **port_kwargs,
        ),
        observer,
        runtime_state_root,
    )


def test_concrete_port_default_calls_the_production_executor_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = _ExecutorObserver()
    monkeypatch.setattr(
        acquisition_surface_execution_module,
        "execute_live_catalog_acquisition",
        observer,
    )
    monkeypatch.setattr(
        acquisition_executor_module,
        "run_orchestrated_ingestion",
        lambda **_kwargs: pytest.fail("captured default bypassed the production executor symbol"),
    )
    port, _, _ = _port_fixture(tmp_path, use_default_executor=True)

    result = port.execute(_route_closure())

    assert result.disposition == "quarantined_no_growth"
    assert len(observer.calls) == 1


def test_production_factory_owns_authority_files_runtime_root_and_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt_provisions = (
        _write_family_receipt(
            repo_root,
            entry_id=entry.entry_id,
            attempt_id=_ATTEMPT_ID,
            receipt=_family_receipt(),
        ),
    )
    _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=receipt_provisions,
    )
    runtime_state_root = tmp_path / "runtime-state"
    observer = _ExecutorObserver()
    monkeypatch.setattr(
        acquisition_surface_execution_module,
        "__file__",
        str(repo_root / "src/polisyos/runtime/http/services/acquisition_surface_execution.py"),
    )
    monkeypatch.setattr(
        acquisition_surface_execution_module,
        "execute_live_catalog_acquisition",
        observer,
    )
    control_service = SimpleNamespace(
        _policy_resolver=SimpleNamespace(default_profile="production"),
        _cas_root=runtime_state_root,
    )

    port = build_production_world_bank_wdi_execution_port(control_service=control_service)

    assert type(port) is WorldBankWDIAcquisitionExecutionPort
    assert port is not None
    port.reserve_route_binding(_route_closure())
    result = port.execute(_route_closure())
    assert result.disposition == "quarantined_no_growth"
    assert len(observer.calls) == 1
    assert observer.calls[0]["journal_path"].is_relative_to(runtime_state_root)
    assert observer.calls[0]["cas_root"].is_relative_to(runtime_state_root)


def test_concrete_port_binds_route_and_governed_storage_before_executor(
    tmp_path: Path,
) -> None:
    port, observer, runtime_state_root = _port_fixture(tmp_path)

    reservation = port.reserve_route_binding(_route_closure())
    result = port.execute(_route_closure())

    assert reservation.attempt_id == _ATTEMPT_ID
    assert isinstance(result, AcquisitionOwnerExecutionResult)
    assert result.disposition == "quarantined_no_growth"
    assert result.owner_receipt_refs == tuple(
        "sha256:" + letter * 64 for letter in ("a", "b", "c", "d")
    )
    assert len(observer.calls) == 1
    call = observer.calls[0]
    assert call["entry_id"].startswith("acquisition-authority:sha256:")
    assert call["attempt_id"] == _ATTEMPT_ID
    assert call["constraints"].country_code == "UKR"
    assert call["constraints"].start_year == call["constraints"].end_year == 2024
    journal_path = call["journal_path"]
    cas_root = call["cas_root"]
    assert isinstance(journal_path, Path)
    assert isinstance(cas_root, Path)
    assert journal_path.is_relative_to(runtime_state_root)
    assert cas_root.is_relative_to(runtime_state_root)
    assert journal_path.name == "evidence-journal.jsonl"
    assert cas_root.name == "cas"
    assert "tenant-a" not in journal_path.as_posix()
    lease_paths = tuple(
        (runtime_state_root / "runtime" / "acquisition" / "worldbank-wdi" / "attempt-leases").glob(
            "*.json"
        )
    )
    assert len(lease_paths) == 1


def test_concrete_port_refuses_replay_and_scope_gaps_before_executor(
    tmp_path: Path,
) -> None:
    port, observer, _ = _port_fixture(tmp_path / "complete")
    port.execute(_route_closure())

    with pytest.raises(AcquisitionActionServiceError) as replay:
        port.execute(
            SimpleNamespace(
                **{
                    **vars(_route_closure()),
                    "tenant_id": "tenant-b",
                }
            )
        )
    assert replay.value.code == "acquisition_live_attempt_exhausted"
    assert len(observer.calls) == 1

    for name, route in (
        ("entry", _route_closure(variable_id="inflation")),
        ("constraints", _route_closure(region="POL")),
    ):
        isolated_port, isolated_observer, _ = _port_fixture(tmp_path / name)
        with pytest.raises(LiveAcquisitionExecutionError):
            isolated_port.execute(route)
        assert isolated_observer.calls == []

    no_attempt_port, no_attempt_observer, _ = _port_fixture(
        tmp_path / "attempt",
        with_attempt=False,
    )
    with pytest.raises(LiveAcquisitionExecutionError) as missing_attempt:
        no_attempt_port.execute(_route_closure())
    assert missing_attempt.value.code == "live_route_authority_attempt_missing"
    assert no_attempt_observer.calls == []


def test_route_projection_states_world_bank_only_scope_without_contract_change(
    tmp_path: Path,
) -> None:
    injected_port, _, _ = _port_fixture(tmp_path / "injected")
    production_port, _, _ = _port_fixture(
        tmp_path / "production",
        use_default_executor=True,
    )
    service = object.__new__(AcquisitionActionService)
    service._authority_provider = SimpleNamespace(
        for_request=lambda **_kwargs: None,
        for_job=lambda **_kwargs: None,
    )
    service._execution_port = injected_port
    service._production_execution_port = None

    injected = service._projection(_projection_closure())
    assert injected.authority_capability == "producer_missing"
    assert injected.execution_capability == "producer_missing"

    service._execution_port = production_port
    externally_supplied = service._projection(_projection_closure())
    assert externally_supplied.authority_capability == "producer_missing"
    assert externally_supplied.execution_capability == "producer_missing"

    service._production_execution_port = production_port
    ready = service._projection(_projection_closure())

    assert ready.authority_capability == "ready"
    assert ready.execution_capability == "ready"
    assert (
        "connector_families_except_worldbank.wdi:surface_out_of_scope"
        in ready.external_nonclosures
    )
    assert "non_fixture_n13b_owner_port:bridge_missing" not in ready.external_nonclosures
    assert ready.authority_badge == "behavioral_fixture_not_production"

    service._authority_provider = None
    service._execution_port = None
    missing = service._projection(_projection_closure())
    assert missing.authority_capability == "producer_missing"
    assert missing.execution_capability == "producer_missing"
    assert "non_fixture_n13b_owner_port:bridge_missing" in missing.external_nonclosures


def test_fixture_port_stays_missing_and_public_route_refuses_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls: list[str] = []
    service = object.__new__(AcquisitionActionService)
    service._authority_provider = SimpleNamespace(
        for_request=lambda **_kwargs: provider_calls.append("for_request"),
        for_job=lambda **_kwargs: provider_calls.append("for_job"),
    )
    service._execution_port = _FixturePort()
    closure = _projection_closure()

    projection = service._projection(closure)

    assert projection.authority_capability == "producer_missing"
    assert projection.execution_capability == "producer_missing"
    assert "non_fixture_n13b_owner_port:bridge_missing" in projection.external_nonclosures
    monkeypatch.setattr(service, "_validated_mutation", lambda **_kwargs: closure)
    with pytest.raises(AcquisitionActionServiceError) as exc_info:
        service.execute(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-acquisition",
            route_id=closure.route_id,
            request=object(),
            bound_permission=object(),
            request_id=None,
            principal=None,
        )
    assert exc_info.value.code == "acquisition_execution_bridge_missing"
    assert provider_calls == []


def test_missing_authority_owner_refuses_before_attempt_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port, _, runtime_state_root = _port_fixture(
        tmp_path,
        use_default_executor=True,
    )
    closure = _projection_closure()
    service = object.__new__(AcquisitionActionService)
    service._authority_provider = None
    service._execution_port = port
    service._production_execution_port = port
    monkeypatch.setattr(service, "_validated_mutation", lambda **_kwargs: closure)

    with pytest.raises(AcquisitionActionServiceError) as exc_info:
        service.execute(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-acquisition",
            route_id=closure.route_id,
            request=object(),
            bound_permission=object(),
            request_id=None,
            principal=None,
        )

    assert exc_info.value.code == "acquisition_authority_producer_missing"
    lease_root = (
        runtime_state_root
        / "runtime"
        / "acquisition"
        / "worldbank-wdi"
        / "attempt-leases"
    )
    assert not lease_root.exists()


@pytest.mark.parametrize(
    ("gap", "expected_code"),
    [
        ("entry", "live_route_authority_entry_missing"),
        ("constraints", "live_request_outside_authority_countries"),
        ("attempt", "live_route_authority_attempt_missing"),
        ("replay", "acquisition_live_attempt_exhausted"),
    ],
)
def test_public_route_binding_gaps_refuse_before_authority_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gap: str,
    expected_code: str,
) -> None:
    provider_calls: list[str] = []
    port, _, _ = _port_fixture(
        tmp_path / gap,
        with_attempt=gap != "attempt",
        use_default_executor=True,
    )
    closure = _projection_closure(
        variable_id="inflation" if gap == "entry" else "government.balance",
        region="POL" if gap == "constraints" else "UKR",
    )
    if gap == "replay":
        observer = _ExecutorObserver()
        monkeypatch.setattr(
            acquisition_surface_execution_module,
            "execute_live_catalog_acquisition",
            observer,
        )
        port.execute(closure)
        assert len(observer.calls) == 1
    service = object.__new__(AcquisitionActionService)
    service._authority_provider = SimpleNamespace(
        for_request=lambda **_kwargs: provider_calls.append("for_request"),
        for_job=lambda **_kwargs: provider_calls.append("for_job"),
    )
    service._execution_port = port
    service._production_execution_port = port
    monkeypatch.setattr(service, "_validated_mutation", lambda **_kwargs: closure)
    request = SimpleNamespace(
        planner_report_hash="sha256:" + "7" * 64,
        replay_pins=SimpleNamespace(model_dump=lambda **_kwargs: {}),
        idempotency_key=f"route-gap-{gap}",
        human_decision_record_ref=None,
    )

    projection = service._projection(closure)
    assert projection.authority_capability == "producer_missing"
    assert projection.execution_capability == "producer_missing"
    assert "worldbank.wdi_route_binding:producer_missing" in projection.external_nonclosures
    assert "non_fixture_n13b_owner_port:bridge_missing" not in projection.external_nonclosures

    with pytest.raises(AcquisitionActionServiceError) as exc_info:
        service.execute(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-acquisition",
            route_id=closure.route_id,
            request=request,
            bound_permission=object(),
            request_id=None,
            principal=None,
        )

    assert exc_info.value.code == expected_code
    assert provider_calls == []
