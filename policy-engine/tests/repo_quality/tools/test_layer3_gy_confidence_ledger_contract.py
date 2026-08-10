from __future__ import annotations

import faulthandler
import json
import os
import signal
import time
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import asdict, replace
from multiprocessing.connection import Connection
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.quality.validation import check_layer3_gy_confidence_ledger as checker
from tools.quality.validation import layer3_gy_confidence_ledger_contract as adapter

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = (
    POLICY_ENGINE_ROOT
    / "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
L5_PATH = (
    POLICY_ENGINE_ROOT
    / "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/"
    "runtime_calibration_internals/calibration/d2/measurement_registry.json"
)


def _spawn_ready_then_stall(
    connection: Connection,
    *,
    profile_path: str,
    **_kwargs: object,
) -> None:
    """Spawn-safe E9 probe that reaches readiness but never objective work."""

    with Path(profile_path).open("w", encoding="utf-8") as profile_handle:
        faulthandler.register(signal.SIGUSR1, file=profile_handle, all_threads=True)
        connection.send({"kind": "worker_ready", "pid": os.getpid()})
        while True:
            pass


def _send_stage_result(
    connection: Connection,
    *,
    stage: str,
    result_role: str,
    ordinal_start: int,
    contract_bytes: bytes,
) -> int:
    """Emit one exact objective stage followed by its result."""

    milestones = checker._expected_objective_milestones(stage)
    for offset, milestone in enumerate(milestones):
        connection.send(
            {
                "kind": "objective_progress",
                "stage": stage,
                "ordinal": ordinal_start + offset,
                "milestone": milestone,
            }
        )
    cache = {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1}
    connection.send(
        {
            "kind": "stage_result",
            "stage": stage,
            "result_role": result_role,
            "worker_pid": os.getpid(),
            "wall_time_seconds": 0.01,
            "contract_bytes": contract_bytes,
            "cache_before": cache,
            "cache_after_warmup": None,
            "cache_after_first": cache,
            "cache_after": cache,
        }
    )
    return ordinal_start + len(milestones)


@pytest.fixture(autouse=True)
def _clear_owner_bundle_cache() -> Iterator[None]:
    adapter.load_owner_bundle.cache_clear()
    yield
    adapter.load_owner_bundle.cache_clear()


def test_real_owner_bundle_projects_narrow_n10_and_n13b_evidence_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        DEFAULT_N13B_CONTRACT,
        N13bAcquisitionExecutorContract,
    )

    capstone_path = POLICY_ENGINE_ROOT / adapter.DEFAULT_N10_CAPSTONE
    n13b_path = POLICY_ENGINE_ROOT / DEFAULT_N13B_CONTRACT
    capstone = json.loads(capstone_path.read_text(encoding="utf-8"))
    n13b = N13bAcquisitionExecutorContract.model_validate_json(n13b_path.read_bytes())
    calls = {"n10": 0, "n13b": 0}
    first_inputs = _sealed_owner_inputs("sha256:" + "1" * 64)
    changed_inputs = _sealed_owner_inputs("sha256:" + "2" * 64)
    consumed_input_derivations = iter(
        (
            first_inputs,
            first_inputs,
            first_inputs,
            first_inputs,
            changed_inputs,
            changed_inputs,
        )
    )

    def recompute_n10(_: Path) -> dict[str, object]:
        calls["n10"] += 1
        return capstone

    def recompute_n13b(
        _: Path,
        *,
        catalog_path: Path,
        l5_path: Path,
    ) -> N13bAcquisitionExecutorContract:
        assert catalog_path == CATALOG_PATH.resolve()
        assert l5_path == L5_PATH.resolve()
        calls["n13b"] += 1
        return n13b

    monkeypatch.setattr(adapter, "_recompute_n10_capstone", recompute_n10)
    monkeypatch.setattr(adapter, "_recompute_n13b_contract", recompute_n13b)
    monkeypatch.setattr(
        adapter,
        "_owner_consumed_input_set",
        lambda *_args, **_kwargs: next(consumed_input_derivations),
    )

    first = adapter.load_owner_bundle(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    second = adapter.load_owner_bundle(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    changed = adapter.load_owner_bundle(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    assert first is second
    assert changed is not first
    assert calls == {"n10": 2, "n13b": 2}
    assert first.consumed_inputs == first_inputs
    assert changed.consumed_inputs == changed_inputs
    assert first.n10.route_count == 3
    assert tuple(row.witness_kind for row in first.n10.routes) == (
        "estimand_binding_refusal",
        "owner_acquisition_route",
        "owner_acquisition_route",
    )
    assert first.n10.witness_kind_counts == (
        ("estimand_binding_refusal", 1),
        ("owner_acquisition_route", 2),
    )
    assert first.n10.owner_data_gap_count == 0
    assert first.n13b.baseline_sha256 == adapter._file_sha256(CATALOG_PATH)
    assert first.n13b.l5_measurement_registry_sha256 == adapter._file_sha256(L5_PATH)
    assert first.n13b.journal_event_count == 44
    assert first.n13b.journal_request_count == 5
    assert first.n13b.live_attempt_count == 5
    assert first.n13b.raw_response_count == 2
    assert first.n13b.response_admitted_count == 0
    assert first.n13b.overlay_admitted_observation_count == 0
    assert first.n13b.passport_count == 0
    assert first.n13b.passports == ()
    assert first.n13b.terminal_without_response_count == 3
    assert first.n13b.world_growth_status == "no_growth"
    assert first.projection_sha256.startswith("sha256:")
    assert not hasattr(first, "n10_contract_sha256")
    assert not hasattr(first, "n13b_contract_sha256")


def test_owner_bundle_rejects_source_change_during_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "catalog.duckdb"
    l5 = tmp_path / "l5.json"
    catalog.write_bytes(b"catalog")
    l5.write_bytes(b"l5")
    inputs = iter(
        (
            _sealed_owner_inputs(
                "sha256:" + "1" * 64,
                member_id="owner-source",
                member_kind="source",
            ),
            _sealed_owner_inputs(
                "sha256:" + "2" * 64,
                member_id="owner-source",
                member_kind="source",
            ),
        )
    )
    monkeypatch.setattr(
        adapter,
        "_owner_consumed_input_set",
        lambda *_args, **_kwargs: next(inputs),
    )
    monkeypatch.setattr(adapter, "_load_owner_bundle_cached", lambda *_args: object())

    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter.load_owner_bundle(
            tmp_path,
            catalog_path=catalog,
            l5_path=l5,
        )

    assert exc_info.value.code == "consumed_input_member_substituted"
    assert "source:owner-source" in exc_info.value.detail


def test_n10_recompute_bridge_preserves_only_self_describing_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N11 retains the safe replay diagnostic but still redacts arbitrary errors."""

    from polisyos.pdc import reconcile_gy_operational_leaves
    from polisyos.pdc._impl.gy_waist import GyOperationalReconciliationError
    from tools.quality.validation.check_layer3_gy_depth_n_universality_contract import (
        UniversalityContractError,
    )

    stored = {"route": "stable"}
    monkeypatch.setattr(adapter, "_read_json_mapping", lambda *args, **kwargs: stored)
    monkeypatch.setattr(adapter, "_validate_n10_payload", lambda payload: None)
    monkeypatch.setattr(adapter, "_extract_n10_route_projection", lambda payload: payload)
    typed_drift: GyOperationalReconciliationError | None = None
    try:
        reconcile_gy_operational_leaves(
            {"compiled_run": {"node_ref": "expected-secret"}},
            {"compiled_run": {"node_ref": "observed-secret"}},
            recording_role="education",
            admission_arm="migrated",
            require_exact_match=True,
        )
    except GyOperationalReconciliationError as exc:
        typed_drift = exc
    assert typed_drift is not None
    safe_detail = (
        "authority_source_controlled_replay_recording_drift:"
        + typed_drift.safe_detail
    )

    def _raise_safe_drift(_: Path) -> dict[str, object]:
        raise UniversalityContractError("sk-outer-secret", replay_drift=typed_drift)

    monkeypatch.setattr(adapter, "_build_n10_cached_payload", _raise_safe_drift)
    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter._recompute_n10_capstone(POLICY_ENGINE_ROOT)

    assert exc_info.value.code == "n10_capstone_recompute_failed"
    assert exc_info.value.detail == safe_detail
    assert "sk-outer-secret" not in str(exc_info.value)
    assert "expected-secret" not in str(exc_info.value)
    assert "observed-secret" not in str(exc_info.value)

    def _raise_forged_drift(_: Path) -> dict[str, object]:
        raise UniversalityContractError(
            "authority_source_controlled_replay_recording_drift:sk-forged-secret"
        )

    monkeypatch.setattr(adapter, "_build_n10_cached_payload", _raise_forged_drift)
    with pytest.raises(adapter.OwnerProjectionError) as forged_exc:
        adapter._recompute_n10_capstone(POLICY_ENGINE_ROOT)

    assert forged_exc.value.detail == "UniversalityContractError"
    assert "sk-forged-secret" not in str(forged_exc.value)

    class _ForgedReplayDrift:
        safe_detail = "sk-forged-object-secret"

    def _raise_forged_object(_: Path) -> dict[str, object]:
        raise UniversalityContractError(
            "ignored",
            replay_drift=_ForgedReplayDrift(),  # type: ignore[arg-type]
        )

    monkeypatch.setattr(adapter, "_build_n10_cached_payload", _raise_forged_object)
    with pytest.raises(adapter.OwnerProjectionError) as forged_object_exc:
        adapter._recompute_n10_capstone(POLICY_ENGINE_ROOT)

    assert forged_object_exc.value.detail == "TypeError"
    assert "sk-forged-object-secret" not in str(forged_object_exc.value)

    def _raise_arbitrary(_: Path) -> dict[str, object]:
        raise RuntimeError("sk-arbitrary-secret")

    monkeypatch.setattr(adapter, "_build_n10_cached_payload", _raise_arbitrary)
    with pytest.raises(adapter.OwnerProjectionError) as arbitrary_exc:
        adapter._recompute_n10_capstone(POLICY_ENGINE_ROOT)

    assert arbitrary_exc.value.detail == "RuntimeError"
    assert "sk-arbitrary-secret" not in str(arbitrary_exc.value)


def _sealed_owner_inputs(
    identity: str,
    *,
    member_id: str = "outside-old-context-key",
    member_kind: str = "environment",
) -> object:
    from polisyos.runtime.quality.authority import (
        ConsumedInputMember,
        SameInputClosure,
        seal_consumed_input_set,
    )

    closure = SameInputClosure(
        closure_id="gy-n11-owner-inputs",
        status="closed",
        run_id="gy-n11",
        job_id="owner-bundle",
        tenant_id="policy-engine",
        closure_sha256="sha256:" + "1" * 64,
    )
    return seal_consumed_input_set(
        closure=closure,
        members=(
            ConsumedInputMember(
                member_id=member_id,
                member_kind=member_kind,
                declared_identity=identity,
                resolved_identity=identity,
                predicate_class="recomputed",
            ),
        ),
    )


def test_owner_bundle_rejects_consumed_input_change_during_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing a declared member is a named input mismatch, not value drift."""

    catalog = tmp_path / "catalog.duckdb"
    l5 = tmp_path / "l5.json"
    catalog.write_bytes(b"catalog")
    l5.write_bytes(b"l5")
    inputs = iter(
        (
            _sealed_owner_inputs("sha256:" + "1" * 64),
            _sealed_owner_inputs("sha256:" + "2" * 64),
        )
    )
    monkeypatch.setattr(
        adapter,
        "_owner_consumed_input_set",
        lambda *_args, **_kwargs: next(inputs),
    )
    monkeypatch.setattr(adapter, "_load_owner_bundle_cached", lambda *_args: object())

    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter.load_owner_bundle(
            tmp_path,
            catalog_path=catalog,
            l5_path=l5,
        )

    assert exc_info.value.code == "consumed_input_member_substituted"
    assert "environment:outside-old-context-key" in exc_info.value.detail


def test_n10_cache_fence_generically_binds_every_declared_source_ref(tmp_path: Path) -> None:
    first = tmp_path / "owners/first.json"
    second = tmp_path / "owners/second.toml"
    first.parent.mkdir(parents=True)
    first.write_text('{"value":1}', encoding="utf-8")
    second.write_text("value = 2\n", encoding="utf-8")
    source_refs = {
        "first_owner": first.relative_to(tmp_path).as_posix(),
        "novel_future_owner": second.relative_to(tmp_path).as_posix(),
        "first_owner_sha256": "sha256:" + "1" * 64,
    }
    payload = {
        "source_refs": source_refs,
        "provenance_stability": {"source_refs": dict(source_refs)},
    }

    before = adapter._n10_declared_source_fence(tmp_path, payload)
    second.write_text("value = 3\n", encoding="utf-8")
    after = adapter._n10_declared_source_fence(tmp_path, payload)

    assert before != after
    assert {key for key, _value in after} == {
        "n10_source_ref:first_owner",
        "n10_source_ref:first_owner_sha256",
        "n10_source_ref:novel_future_owner",
    }


def test_n10_cache_fence_rejects_divergent_source_ref_projections(tmp_path: Path) -> None:
    payload = {
        "source_refs": {"owner": "owners/first.json"},
        "provenance_stability": {"source_refs": {"owner": "owners/other.json"}},
    }

    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter._n10_declared_source_fence(tmp_path, payload)

    assert exc_info.value.code == "n10_source_refs_projection_drift"


def test_n10_recomputation_rejects_route_projection_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capstone_path = tmp_path / adapter.DEFAULT_N10_CAPSTONE
    capstone_path.parent.mkdir(parents=True)
    capstone_path.write_text('{"owner":"stored"}', encoding="utf-8")
    monkeypatch.setattr(adapter, "_validate_n10_payload", lambda _: None)
    monkeypatch.setattr(
        adapter,
        "_extract_n10_route_projection",
        lambda payload: payload["owner"],
    )
    monkeypatch.setattr(
        adapter,
        "_build_n10_cached_payload",
        lambda _: {"owner": "recomputed"},
    )

    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter._recompute_n10_capstone(tmp_path)

    assert exc_info.value.code == "n10_capstone_route_projection_drift"


def test_n10_recomputation_ignores_fields_outside_the_declared_route_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capstone_path = tmp_path / adapter.DEFAULT_N10_CAPSTONE
    capstone_path.parent.mkdir(parents=True)
    capstone_path.write_text(
        '{"route":"stable","outside_projection":"stored"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(adapter, "_validate_n10_payload", lambda _: None)
    monkeypatch.setattr(
        adapter,
        "_extract_n10_route_projection",
        lambda payload: payload["route"],
    )
    monkeypatch.setattr(
        adapter,
        "_build_n10_cached_payload",
        lambda _: {"route": "stable", "outside_projection": "recomputed"},
    )

    assert adapter._recompute_n10_capstone(tmp_path) == {
        "route": "stable",
        "outside_projection": "recomputed",
    }


def test_n13b_recomputation_ignores_fields_outside_declared_accounting_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _fake_n13b_contract(outside_projection="stored")
    recomputed = _fake_n13b_contract(outside_projection="recomputed")
    _stub_n13b_recomputation(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        stored=stored,
        recomputed=recomputed,
    )

    assert (
        adapter._recompute_n13b_contract(
            tmp_path,
            catalog_path=tmp_path / "catalog.duckdb",
            l5_path=tmp_path / "l5.json",
        )
        is recomputed
    )


def test_n13b_recomputation_rejects_declared_accounting_projection_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _fake_n13b_contract(authority_projection_sha256="sha256:" + "1" * 64)
    recomputed = _fake_n13b_contract(authority_projection_sha256="sha256:" + "2" * 64)
    _stub_n13b_recomputation(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        stored=stored,
        recomputed=recomputed,
    )

    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter._recompute_n13b_contract(
            tmp_path,
            catalog_path=tmp_path / "catalog.duckdb",
            l5_path=tmp_path / "l5.json",
        )

    assert exc_info.value.code == "n13b_accounting_projection_drift"


def test_n10_cached_owner_primes_provenance_before_async_capstone_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.quality.validation import (
        check_layer3_gy_depth_n_universality_contract as n10_owner,
    )

    calls: list[str] = []

    def check_provenance_stability(repo_root: Path) -> dict[str, str]:
        assert repo_root == POLICY_ENGINE_ROOT
        calls.append("provenance")
        return {"status": "stable"}

    def build_live_payload(repo_root: Path, *, lane: str) -> dict[str, str]:
        assert repo_root == POLICY_ENGINE_ROOT
        assert lane == "cached"
        calls.append("capstone")
        return {"owner": "recomputed"}

    monkeypatch.setattr(
        n10_owner,
        "check_provenance_stability",
        check_provenance_stability,
    )
    monkeypatch.setattr(n10_owner, "build_live_payload", build_live_payload)

    assert adapter._build_n10_cached_payload(POLICY_ENGINE_ROOT) == {"owner": "recomputed"}
    assert calls == ["provenance", "capstone"]


def test_nonzero_admission_state_without_enumerable_passports_fails_closed(
    tmp_path: Path,
) -> None:
    from tools.quality.validation.layer3_gy_n13b_reentry import OverlayStateProjection

    state = OverlayStateProjection(
        overlay_ref=("repo://architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"),
        exists=False,
        content_sha256=None,
        epoch_count=0,
        registration_count=0,
        admitted_observation_count=0,
    )

    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter._load_revalidated_passports(
            repo_root=tmp_path,
            catalog_path=tmp_path / "catalog.duckdb",
            l5_path=tmp_path / "l5.json",
            overlay_state=state,
            expected_response_admitted_count=1,
        )

    assert exc_info.value.code == "n13b_admission_passports_unenumerable"


def test_enumerated_passport_is_revalidated_before_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.runtime.quality import acquisition_executor as admission_owner
    from tools.quality.validation.layer3_gy_n13b_reentry import OverlayStateProjection

    overlay = tmp_path / "architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"
    overlay.parent.mkdir(parents=True)
    overlay.write_bytes(b"content-bound-overlay")
    passport_payload = {"evidence": "owner-bound"}
    passport_id = "passport:sha256:" + ("1" * 64)

    class Result:
        def __init__(self, value: object) -> None:
            self.value = value

        def fetchone(self) -> tuple[int]:
            assert isinstance(self.value, int)
            return (self.value,)

        def fetchall(self) -> list[tuple[object, ...]]:
            assert isinstance(self.value, list)
            return self.value

    class Connection:
        def execute(self, statement: str) -> Result:
            if "FROM acquisition_epochs" in statement:
                return Result(1)
            if "FROM acquisition_registrations" in statement:
                return Result(1)
            if "FROM acquisition_overlay.ds_observations" in statement:
                return Result(2)
            return Result(
                [
                    (
                        passport_id,
                        1,
                        adapter._content_sha256(passport_payload),
                        json.dumps(passport_payload),
                    )
                ]
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        catalog_read_api,
        "open_catalog_read_session",
        lambda *_args, **_kwargs: Connection(),
    )
    monkeypatch.setattr(
        catalog_read_api,
        "CanonicalAcquisitionAuthority",
        SimpleNamespace(from_provision=lambda **_kwargs: object()),
    )
    calls: list[object] = []
    parsed_passport = SimpleNamespace(
        passport_id=passport_id,
        epoch_id=1,
        variable_id="government.balance",
        source_lane="live_fetch",
        observation_class="observed",
        authority_entry_id="entry-1",
        authority_provision_id="acquisition-authority-provision:sha256:" + ("2" * 64),
        authority_registry_content_sha256="sha256:" + ("3" * 64),
        raw_evidence_ref=SimpleNamespace(event_sha256="sha256:" + ("4" * 64)),
        raw_artifact_id="sha256:" + ("5" * 64),
        source_watermark="sha256:" + ("6" * 64),
        status="admitted",
        rejection_codes=(),
    )
    monkeypatch.setattr(
        admission_owner.AdmissionPassport,
        "model_validate",
        classmethod(lambda _cls, payload: parsed_passport if payload == passport_payload else None),
    )

    def revalidate(
        passport: object,
        *,
        artifact_store: object,
        authority: object,
    ) -> SimpleNamespace:
        del artifact_store, authority
        calls.append(passport)
        return parsed_passport

    monkeypatch.setattr(admission_owner, "revalidate_admission_passport", revalidate)
    state = OverlayStateProjection(
        overlay_ref=("repo://architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"),
        exists=True,
        content_sha256=adapter._file_sha256(overlay),
        epoch_count=1,
        registration_count=1,
        admitted_observation_count=2,
    )

    rows = adapter._load_revalidated_passports(
        repo_root=tmp_path,
        catalog_path=tmp_path / "catalog.duckdb",
        l5_path=tmp_path / "l5.json",
        overlay_state=state,
        expected_response_admitted_count=1,
    )

    assert calls == [parsed_passport]
    assert len(rows) == 1
    assert rows[0].passport_id == passport_id
    assert rows[0].status == "admitted"


@pytest.mark.parametrize("value", ["1", 1.0, True, None])
def test_overlay_database_counts_reject_coercible_non_integer_values(value: object) -> None:
    with pytest.raises(adapter.OwnerProjectionError) as exc_info:
        adapter._strict_db_int(value, field="epoch_count")

    assert exc_info.value.code == "n13b_overlay_row_wire_invalid"


def test_real_capstone_and_admission_denominator_are_accounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)

    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    assert contract.accounted_run.n10_route_count == 3
    assert contract.accounted_run.owner_acquisition_route_count == 2
    assert contract.accounted_run.estimand_binding_refusal_count == 1
    assert contract.accounted_run.owner_data_gap_count == 0
    assert contract.accounted_run.n13b_attempt_count == 5
    assert contract.accounted_run.n13b_raw_response_count == 2
    assert contract.accounted_run.n13b_admission_count == 0
    assert contract.accounted_run.n13b_passport_count == 0
    assert len(contract.accounted_run.evidence_rows) == 3
    assert all(row.deterministic_proof for row in contract.accounted_run.evidence_rows)
    assert all(not row.eligible_for_promotion for row in contract.accounted_run.evidence_rows)
    assert contract.accounted_run.total_spend_numerator == 0
    assert contract.conformance_run.total_spend_numerator > 0
    assert contract.conformance_run.eligible_for_promotion is False
    assert contract.n9_promotion_projection.promotion_rows == ()
    assert checker.validate_payload(contract, expected=contract)["status"] == "pass"


def test_real_accounting_uses_ledger_hash_for_unicode_owner_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.data_plane import content_sha256

    bundle = _warm_bundle(monkeypatch)
    unicode_route = replace(
        bundle.n10.routes[0],
        candidate_ref="n10-candidate://дані",
    )
    route_values = asdict(unicode_route)
    route_values.pop("projection_sha256")
    unicode_route = replace(
        unicode_route,
        projection_sha256=content_sha256(route_values),
    )
    unicode_n10 = replace(
        bundle.n10,
        routes=(unicode_route, *bundle.n10.routes[1:]),
    )
    n10_values = asdict(unicode_n10)
    n10_values.pop("projection_sha256")
    unicode_n10 = replace(
        unicode_n10,
        projection_sha256=content_sha256(n10_values),
    )
    unicode_bundle = replace(
        bundle,
        n10=unicode_n10,
        projection_sha256=content_sha256(
                {
                    "n10": asdict(unicode_n10),
                    "n13b": asdict(bundle.n13b),
                    "consumed_inputs": bundle.consumed_inputs.model_dump(mode="json"),
                }
        ),
    )
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: unicode_bundle)

    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    row = next(
        item
        for item in contract.accounted_run.evidence_rows
        if item.certificate_ref == f"n10-route://{unicode_route.route_id}"
    )
    assert row.execution_status == "executed"
    assert row.supports_obligation is True
    assert row.owner_projection_hash is not None
    report = checker.validate_payload(contract, expected=contract)
    assert report["status"] == "pass", report["issues"]


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("owner_ref", "attacker.FakeOwner"),
        ("verifier_ref", "attacker.FakeVerifier"),
        ("obligation_class", "value"),
    ],
)
def test_real_owner_route_relabel_fails_before_accounting(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    forged_value: str,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    registry = checker.load_confidence_ledger_registry(
        POLICY_ENGINE_ROOT / checker.REGISTRY_PATH
    )
    payload = registry.source_payload()
    route = next(
        item
        for item in payload["certificate_class_routes"]
        if item["certificate_class"] == "owner_acquisition_route"
    )
    route[field] = forged_value
    forged_registry = checker.load_confidence_ledger_registry(payload)
    monkeypatch.setattr(
        checker,
        "load_confidence_ledger_registry",
        lambda *_args, **_kwargs: forged_registry,
    )
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    session_calls = 0

    def forbid_session(*_args: object, **_kwargs: object) -> None:
        nonlocal session_calls
        session_calls += 1
        raise AssertionError("ledger_session_opened_before_owner_contract_validation")

    monkeypatch.setattr(
        checker.ConfidenceLedgerSession,
        "_for_verification",
        classmethod(forbid_session),
    )

    with pytest.raises(ValueError, match="owner_certificate_route_contract_mismatch"):
        checker.build_live_contract(
            POLICY_ENGINE_ROOT,
            catalog_path=CATALOG_PATH,
            l5_path=L5_PATH,
        )

    assert session_calls == 0


def test_required_real_owner_route_cannot_be_deleted() -> None:
    registry = checker.load_confidence_ledger_registry(
        POLICY_ENGINE_ROOT / checker.REGISTRY_PATH
    )
    payload = registry.source_payload()
    payload["certificate_class_routes"] = [
        item
        for item in payload["certificate_class_routes"]
        if item["certificate_class"] != "admission_passport"
    ]
    missing = checker.load_confidence_ledger_registry(payload)

    with pytest.raises(ValueError, match="owner_certificate_route_contract_missing"):
        checker._bind_code_owned_owner_certificate_routes(missing)


def test_unowned_real_owner_kernel_route_cannot_extend_denominator() -> None:
    registry = checker.load_confidence_ledger_registry(
        POLICY_ENGINE_ROOT / checker.REGISTRY_PATH
    )
    payload = registry.source_payload()
    payload["certificate_class_routes"].append(
        {
            "certificate_class": "unowned_n10_refusal_class",
            "instrument_id": "deterministic_owner_proof",
            "obligation_class": "data",
            "certificate_role": "refusal",
            "claim_polarity": "confident_wrong_refusal",
            "owner_ref": (
                "tools.quality.validation.layer3_gy_n13a_acquisition_census."
                "extract_route_projection"
            ),
            "verifier_kernel_id": "n10_route_projection_recompute_v1",
            "verifier_ref": (
                "tools.quality.validation."
                "check_layer3_gy_depth_n_universality_contract.validate_payload"
            ),
        }
    )
    unowned = checker.load_confidence_ledger_registry(payload)

    with pytest.raises(ValueError, match="owner_certificate_route_contract_unowned"):
        checker._bind_code_owned_owner_certificate_routes(unowned)


def test_new_data_only_instrument_is_accounted_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)

    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    definition = next(
        item
        for item in contract.registry_projection.instruments
        if item.instrument_id == "deterministic_refusal_certificate"
    )
    row = next(
        item
        for item in contract.accounted_run.evidence_rows
        if item.certificate_class == "estimand_binding_refusal"
    )
    check = next(
        item
        for item in contract.real_ledger_projection.checks
        if item.check_projection_hash == row.check_projection_hash
    )

    assert definition.instrument_family == "proof_carrying_refusal_certificate"
    assert row.instrument_id == definition.instrument_id
    assert check.instrument_id == definition.instrument_id
    assert check.owner_binding is not None
    assert check.owner_binding.owner_projection_hash == row.owner_projection_hash
    assert definition.instrument_id in contract.universality.real_accounted_instrument_ids
    assert checker.validate_payload(contract, expected=contract)["status"] == "pass"


def test_unseen_instrument_probe_is_a_recorded_zero_spend_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)

    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    probe = contract.universality.unseen_instrument_probe
    assert probe.instrument_id == "__n11_unregistered_instrument_probe__"
    assert probe.refusal_code == "unknown_instrument"
    assert probe.execution_status == "refused"
    assert probe.outcome == "preflight_refusal"
    assert probe.event_count == 1
    assert probe.check_count == 1
    assert probe.execution_ordinal is None
    assert probe.schedule_query_index is None
    assert probe.execution_id is None
    assert probe.spend_numerator == 0
    assert probe.total_spend_numerator == 0
    assert probe.supports_obligation is False
    assert probe.eligible_for_promotion is False
    assert checker.validate_payload(contract, expected=contract)["status"] == "pass"


def test_projection_edges_bind_owner_declared_scopes_and_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    n10_edge, n13b_edge, accounted_edge, n9_edge, n12_edge = contract.projection_edges
    assert n10_edge.producer_scope == bundle.n10.source_projection_scope
    assert n10_edge.producer_scope == "capstone_acquisition_routes"
    assert n10_edge.producer_projection_hash == bundle.n10.source_projection_sha256
    assert n10_edge.consumer_projection_hash == contract.real_ledger_projection.projection_hash
    assert n13b_edge.producer_scope == bundle.n13b.source_accounting_projection_scope
    assert n13b_edge.producer_projection_hash == (bundle.n13b.source_accounting_projection_sha256)
    assert n13b_edge.consumer_projection_hash == contract.real_ledger_projection.projection_hash
    assert accounted_edge.producer_scope == contract.real_ledger_projection.projection_scope
    assert accounted_edge.producer_projection_hash == contract.real_ledger_projection.projection_hash
    assert accounted_edge.consumer_projection_hash == contract.accounted_run.projection_hash
    assert n9_edge.producer_scope == contract.real_ledger_projection.projection_scope
    assert n9_edge.producer_projection_hash == contract.real_ledger_projection.projection_hash
    assert n9_edge.consumer_projection_hash == contract.n9_promotion_projection.projection_hash
    assert (
        n12_edge.consumer_projection_hash == contract.n12_epoch_reference_projection.projection_hash
    )


def test_zero_mass_schedule_projection_uses_non_strict_total_bound() -> None:
    registry = checker.load_confidence_ledger_registry(POLICY_ENGINE_ROOT / checker.REGISTRY_PATH)
    payload = registry.source_payload()
    payload["schedule_profiles"].append(
        {
            "profile_id": "zero_mass_basel_square",
            "proof_kernel_id": "basel_square_v1",
            "mass": {"numerator": 0, "denominator": 1},
        }
    )
    payload["policy"]["default_schedule_profile_id"] = "zero_mass_basel_square"

    projection = checker._build_registry_projection(
        checker.load_confidence_ledger_registry(payload)
    )

    assert projection.selected_schedule_proof.declared_mass.numerator == 0
    assert (
        projection.selected_schedule_proof.total_mass_relation
        == "sum_t executable_weight_t <= declared_mass <= 1"
    )


@pytest.mark.parametrize(
    ("projection_key", "field", "value", "expected_code"),
    [
        (
            "n9_promotion_projection",
            "authority_provenance",
            "canonical_repo",
            "frozen_authority_provenance_drift",
        ),
        (
            "n12_epoch_reference_projection",
            "deployment_identity",
            "policy-engine-deployment:sha256:" + "7" * 64,
            "projection_deployment_identity_drift",
        ),
        (
            "n9_promotion_projection",
            "scope_anchor_ref",
            "sha256:" + "7" * 64,
            "real_scope_anchor_binding_drift",
        ),
        (
            "n12_epoch_reference_projection",
            "scope_anchor_ref",
            "sha256:" + "7" * 64,
            "real_scope_anchor_binding_drift",
        ),
        (
            "real_ledger_projection",
            "projection_scope",
            "n11_conformance_append_lineage",
            "semantic_projection_scope_authority_drift",
        ),
        (
            "conformance_ledger_projection",
            "projection_scope",
            "n11_real_accounting_append_lineage",
            "semantic_projection_scope_authority_drift",
        ),
    ],
)
def test_rehashed_projection_authority_fields_turn_red(
    monkeypatch: pytest.MonkeyPatch,
    projection_key: str,
    field: str,
    value: str,
    expected_code: str,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    payload = json.loads(checker.contract_bytes(contract))
    projection = payload[projection_key]
    projection[field] = value
    projection["projection_hash"] = checker._ledger_content_hash(
        {key: item for key, item in projection.items() if key != "projection_hash"}
    )
    payload["artifact_content_hash"] = checker.gy_content_hash(
        {key: item for key, item in payload.items() if key != "artifact_content_hash"}
    )

    report = checker.validate_payload(payload)

    assert report["status"] == "fail"
    assert expected_code in {issue["code"] for issue in report["issues"]}


def test_n12_root_binding_is_independent_of_n9_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    payload = json.loads(checker.contract_bytes(contract))
    n9 = payload["n9_promotion_projection"]
    n9["risk_scope"]["model_ref"] = "sha256:" + "7" * 64
    n9["projection_hash"] = checker._ledger_content_hash(
        {key: item for key, item in n9.items() if key != "projection_hash"}
    )
    payload["artifact_content_hash"] = checker.gy_content_hash(
        {key: item for key, item in payload.items() if key != "artifact_content_hash"}
    )

    report = checker.validate_payload(payload)

    assert report["status"] == "fail"
    assert "real_scope_anchor_binding_drift" in {issue["code"] for issue in report["issues"]}
    assert payload["n12_epoch_reference_projection"]["model_ref"] == (
        contract.n12_epoch_reference_projection.model_ref
    )


def test_rehashed_projection_edge_hash_turns_red(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    payload = json.loads(checker.contract_bytes(contract))
    payload["projection_edges"][0]["producer_projection_hash"] = "sha256:" + "7" * 64
    payload["artifact_content_hash"] = checker.gy_content_hash(
        {key: item for key, item in payload.items() if key != "artifact_content_hash"}
    )

    report = checker.validate_payload(payload)

    assert report["status"] == "fail"
    assert "projection_edge_binding_drift" in {issue["code"] for issue in report["issues"]}


def test_confidence_ledger_writer_is_byte_stable_and_corruptions_turn_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    first = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    second = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    assert checker.contract_bytes(first) == checker.contract_bytes(second)
    corruption_report = checker.corrupt_field_drift_check(first)
    assert corruption_report["status"] == "pass"
    assert tuple(row["case_id"] for row in corruption_report["results"]) == (
        checker.CORRUPT_FIELD_MUTATION_IDS
    )


def test_frozen_artifact_excludes_physical_ledger_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    artifact_keys = keys(json.loads(checker.contract_bytes(contract)))
    assert artifact_keys.isdisjoint(
        {
            "owner_invocation_lock_identity",
            "owner_invocation_claim_id",
            "ledger_root_id",
            "ledger_root_ref",
            "event_id",
            "event_ref",
            "check_id",
            "receipt_id",
            "precheck_history_hash",
            "claim_execution_binding_hash",
            "verifier_projection_hash",
        }
    )


def test_one_process_closeout_records_effective_config_and_stage_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _warm_bundle(monkeypatch)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    output = tmp_path / "confidence-ledger.json"
    output.write_bytes(checker.contract_bytes(contract))
    stats = iter(
        (
            {"hits": 0, "misses": 0, "maxsize": 4, "currsize": 0},
            {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
            {"hits": 1, "misses": 1, "maxsize": 4, "currsize": 1},
            {"hits": 2, "misses": 1, "maxsize": 4, "currsize": 1},
        )
    )
    monkeypatch.setattr(checker, "owner_bundle_cache_stats", lambda: next(stats))
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")

    report = checker._run_one_process_closeout(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        output=output,
        cold=False,
        _process_start_method="fork",
    )

    assert not report["issues"], report["issues"]
    assert report["status"] == "pass"
    assert report["effective_config"]["jax_platforms"] == "cpu"
    assert report["effective_config"]["catalog_sha256"].startswith("sha256:")
    assert report["effective_config"]["l5_sha256"].startswith("sha256:")
    assert report["worker_pid"] > 0
    assert report["cache_after_warmup"]["hits"] == 0
    assert report["cache_after_first"]["hits"] == 1
    assert report["cache_after_second"]["hits"] == 2
    objective_rows = [
        row for row in report["stage_heartbeats"] if row["event"] == "objective_progress"
    ]
    assert objective_rows
    ordinals = [row["objective_progress_ordinal"] for row in objective_rows]
    assert ordinals == sorted(set(ordinals))
    assert all(row["process_cpu_seconds"] is None for row in objective_rows)
    cpu_rows = [row for row in report["stage_heartbeats"] if row["event"] == "cpu_heartbeat"]
    assert cpu_rows
    assert all(row["objective_progress_ordinal"] is None for row in cpu_rows)
    assert all(row["within_two_x_historical"] for row in report["historical_stage_comparison"])


def test_cpu_burning_worker_without_objective_progress_is_profiled_and_terminated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.004)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.05,
    )

    def cpu_burning_stage(*_args: object, **_kwargs: object) -> object:
        while True:
            pass

    monkeypatch.setattr(checker, "build_live_contract", cpu_burning_stage)
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")

    report = checker._run_one_process_closeout(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        output=tmp_path / "never-written.json",
        cold=True,
        _process_start_method="fork",
    )

    assert report["status"] == "fail"
    assert report["worker_terminated"] is True
    assert report["byte_stable_passes"] == 0
    assert report["second_pass_started"] is False
    assert report["worker_profile"]["captured"] is True
    assert "cpu_burning_stage" in report["worker_profile"]["stack_trace"]
    assert {row["event"] for row in report["stage_heartbeats"]} >= {
        "objective_progress",
        "cpu_heartbeat",
        "terminated",
    }
    assert any(
        issue["code"] == "historical_stage_two_x_profiling_stop" for issue in report["issues"]
    )


def test_worker_that_never_reaches_ready_is_terminated_after_two_x(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.05,
    )

    def never_ready(*, profile_path: str, **_kwargs: object) -> None:
        with Path(profile_path).open("w", encoding="utf-8") as profile_handle:
            faulthandler.register(signal.SIGUSR1, file=profile_handle, all_threads=True)
            while True:
                pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=never_ready,
    )

    assert result["profiling_stop"] is True
    assert result["worker_terminated"] is True
    assert result["worker_profile"]["captured"] is True
    assert result["second_pass_started"] is False


def test_readiness_cpu_heartbeats_do_not_reset_objective_stall_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.05,
    )

    def readiness_only(
        connection: Connection,
        *,
        profile_path: str,
        **_kwargs: object,
    ) -> None:
        with Path(profile_path).open("w", encoding="utf-8") as profile_handle:
            faulthandler.register(signal.SIGUSR1, file=profile_handle, all_threads=True)
            connection.send({"kind": "worker_ready", "pid": os.getpid()})
            while True:
                pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=readiness_only,
    )

    assert result["profiling_stop"] is True
    assert result["worker_terminated"] is True
    assert result["second_pass_started"] is False


def test_production_spawn_worker_is_killable_before_objective_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.01)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.1,
    )

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="spawn",
        worker_target=_spawn_ready_then_stall,
    )

    assert result["profiling_stop"] is True
    assert result["worker_terminated"] is True
    assert result["second_pass_started"] is False


def test_immediate_worker_exit_is_terminal_not_a_two_x_stall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.5,
    )

    started = time.monotonic()
    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="spawn",
        worker_target=dict,
    )

    assert time.monotonic() - started < 30.0
    assert result["profiling_stop"] is False
    assert result["worker_error"]["code"] == "closeout_worker_exited_early"
    assert result["stage_wall_times"]["worker_startup"] > 0
    assert result["bootstrap_verified"] is True
    assert result["process_group_clean"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "worker_ready", "pid": "1"},
        {"kind": "worker_ready", "pid": True},
        {"kind": "worker_ready", "pid": 1, "extra": "forbidden"},
        {
            "kind": "objective_progress",
            "stage": "cold_owner_derivation",
            "ordinal": "1",
            "milestone": "stage_started",
        },
        {
            "kind": "stage_result",
            "stage": "cold_owner_derivation",
            "result_role": "first",
            "worker_pid": 1,
            "wall_time_seconds": "0.1",
            "contract_bytes": b"bytes",
            "cache_before": {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
            "cache_after_warmup": None,
            "cache_after_first": None,
            "cache_after": {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
        },
        {
            "kind": "stage_result",
            "stage": "cold_owner_derivation",
            "result_role": "first",
            "worker_pid": 1,
            "wall_time_seconds": float("nan"),
            "contract_bytes": [1, 2, 3],
            "cache_before": {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
            "cache_after_warmup": None,
            "cache_after_first": None,
            "cache_after": {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
        },
        ["not", "a", "message"],
    ],
)
def test_worker_wire_rejects_coercible_extra_and_non_mapping_values(payload: object) -> None:
    with pytest.raises(checker.ValidationError):
        checker._validated_worker_message(payload)


def test_non_mapping_worker_message_fails_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)

    def invalid_wire(connection: Connection, **_kwargs: object) -> None:
        connection.send(["not", "a", "message"])
        while True:
            pass

    started = time.monotonic()
    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=invalid_wire,
    )

    assert time.monotonic() - started < 1.0
    assert result["worker_error"]["code"] == "closeout_worker_wire_invalid"
    assert result["process_group_clean"] is True


def test_prebootstrap_stall_is_typed_as_worker_startup_without_profile_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)
    monkeypatch.setitem(checker._HISTORICAL_STAGE_SECONDS, "worker_startup", 0.03)

    def prebootstrap_stall(**_kwargs: object) -> None:
        while True:
            pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        _bootstrap_target=prebootstrap_stall,
    )

    assert result["stop_stage"] == "worker_startup"
    assert result["bootstrap_verified"] is False
    assert result["worker_profile"]["status"] == "profile_handler_not_ready"
    assert result["worker_profile"]["signal_sent"] is False
    assert result["process_group_clean"] is True


def test_bootstrap_requires_profile_readiness_and_verified_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)

    def forged_bootstrap(connection: Connection, **_kwargs: object) -> None:
        pid = os.getpid()
        connection.send(
            {
                "kind": "worker_bootstrap",
                "pid": pid,
                "pgid": pid,
                "profiling_ready": False,
            }
        )
        while True:
            pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        _bootstrap_target=forged_bootstrap,
    )

    assert result["worker_error"]["code"] == "closeout_worker_bootstrap_invalid"
    assert result["verified_pgid"] is None
    assert result["process_group_clean"] is True


@pytest.mark.parametrize("mode", ["objective_before_ready", "duplicate_ready"])
def test_worker_readiness_order_is_fail_closed(mode: str) -> None:
    def invalid_order(connection: Connection, **_kwargs: object) -> None:
        pid = os.getpid()
        if mode == "duplicate_ready":
            connection.send({"kind": "worker_ready", "pid": pid})
            connection.send({"kind": "worker_ready", "pid": pid})
        else:
            connection.send(
                {
                    "kind": "objective_progress",
                    "stage": "cold_owner_derivation",
                    "ordinal": 1,
                    "milestone": "stage_started",
                }
            )
        while True:
            pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=invalid_order,
    )

    assert result["worker_error"]["code"] in {
        "closeout_worker_readiness_order_invalid",
        "closeout_worker_readiness_protocol_error",
    }
    assert result["process_group_clean"] is True


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX process groups")
@pytest.mark.parametrize("mode", ["leader_stalls", "leader_exits"])
def test_worker_group_cleanup_leaves_no_descendants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)
    monkeypatch.setitem(checker._HISTORICAL_STAGE_SECONDS, "cold_owner_derivation", 0.03)
    descendant_path = tmp_path / f"{mode}.pid"

    def process_tree(connection: Connection, **_kwargs: object) -> None:
        descendant = os.fork()
        if descendant == 0:
            descendant_path.write_text(str(os.getpid()), encoding="utf-8")
            while True:
                signal.pause()
        deadline = time.monotonic() + 1.0
        while not descendant_path.exists() and time.monotonic() < deadline:
            time.sleep(0.001)
        connection.send({"kind": "worker_ready", "pid": os.getpid()})
        if mode == "leader_stalls":
            while True:
                pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=process_tree,
    )
    descendant_pid = int(descendant_path.read_text(encoding="utf-8"))
    try:
        deadline = time.monotonic() + 2.0
        descendant_exists = True
        while descendant_exists and time.monotonic() < deadline:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                descendant_exists = False
            else:
                time.sleep(0.01)
        assert descendant_exists is False
        assert result["verified_pgid"] == result["worker_pid"]
        assert result["process_group_clean"] is True
    finally:
        with suppress(ProcessLookupError):
            os.kill(descendant_pid, signal.SIGKILL)


def test_first_stage_result_then_eof_fails_without_starting_second_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.05,
    )

    def first_result_then_exit(
        connection: Connection,
        **_kwargs: object,
    ) -> None:
        pid = os.getpid()
        connection.send({"kind": "worker_ready", "pid": pid})
        for ordinal, milestone in enumerate(
            checker._expected_objective_milestones("cold_owner_derivation"),
            start=1,
        ):
            connection.send(
                {
                    "kind": "objective_progress",
                    "stage": "cold_owner_derivation",
                    "ordinal": ordinal,
                    "milestone": milestone,
                }
            )
        cache = {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1}
        connection.send(
            {
                "kind": "stage_result",
                "stage": "cold_owner_derivation",
                "result_role": "first",
                "worker_pid": pid,
                "wall_time_seconds": 0.01,
                "contract_bytes": b"first-only",
                "cache_before": cache,
                "cache_after_warmup": None,
                "cache_after_first": cache,
                "cache_after": cache,
            }
        )

    started = time.monotonic()
    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=first_result_then_exit,
    )

    assert time.monotonic() - started < 1.0
    assert result["profiling_stop"] is False
    assert result["second_pass_started"] is False
    assert result["worker_error"]["code"] in {
        "closeout_worker_exited_early",
        "closeout_worker_command_channel_closed",
    }


def test_final_stage_result_then_eof_is_not_worker_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)

    def final_result_then_exit(
        connection: Connection,
        **_kwargs: object,
    ) -> None:
        connection.send({"kind": "worker_ready", "pid": os.getpid()})
        next_ordinal = _send_stage_result(
            connection,
            stage="cold_owner_derivation",
            result_role="first",
            ordinal_start=1,
            contract_bytes=b"stable",
        )
        assert connection.recv() == {"command": "run_second_pass"}
        _send_stage_result(
            connection,
            stage="cache_hit_derivation",
            result_role="second",
            ordinal_start=next_ordinal,
            contract_bytes=b"stable",
        )

    started = time.monotonic()
    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=final_result_then_exit,
    )

    assert time.monotonic() - started < 1.0
    assert result["profiling_stop"] is False
    assert result["second_pass_started"] is True
    assert result["worker_error"]["code"] == "closeout_worker_exited_early"


def test_queued_worker_complete_before_eof_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.003)

    def complete_then_exit(
        connection: Connection,
        **_kwargs: object,
    ) -> None:
        connection.send({"kind": "worker_ready", "pid": os.getpid()})
        next_ordinal = _send_stage_result(
            connection,
            stage="cold_owner_derivation",
            result_role="first",
            ordinal_start=1,
            contract_bytes=b"stable",
        )
        assert connection.recv() == {"command": "run_second_pass"}
        _send_stage_result(
            connection,
            stage="cache_hit_derivation",
            result_role="second",
            ordinal_start=next_ordinal,
            contract_bytes=b"stable",
        )
        connection.send({"kind": "worker_complete", "pid": os.getpid()})

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=complete_then_exit,
    )

    assert result["profiling_stop"] is False
    assert result["worker_error"] is None
    assert result["first_bytes"] == result["second_bytes"] == b"stable"


@pytest.mark.parametrize(
    ("second_ordinal", "second_milestone"),
    [
        (1, "confidence_registry_loaded"),
        (2, "owner_pre_derivation_fence_started"),
    ],
    ids=("duplicate_ordinal", "skipped_phase"),
)
def test_invalid_objective_sequence_is_rejected(
    second_ordinal: int,
    second_milestone: str,
) -> None:
    def invalid_sequence(
        connection: Connection,
        **_kwargs: object,
    ) -> None:
        connection.send({"kind": "worker_ready", "pid": os.getpid()})
        connection.send(
            {
                "kind": "objective_progress",
                "stage": "cold_owner_derivation",
                "ordinal": 1,
                "milestone": "stage_started",
            }
        )
        connection.send(
            {
                "kind": "objective_progress",
                "stage": "cold_owner_derivation",
                "ordinal": second_ordinal,
                "milestone": second_milestone,
            }
        )
        while True:
            pass

    result = checker._run_closeout_worker(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        cold=True,
        process_start_method="fork",
        worker_target=invalid_sequence,
    )

    assert result["worker_error"]["code"] == "objective_progress_protocol_error"
    assert result["second_pass_started"] is False


def test_unknown_objective_marker_cannot_keep_worker_alive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    output = tmp_path / "confidence-ledger.json"
    output.write_bytes(checker.contract_bytes(contract))

    def marker_spam(
        *_args: object,
        objective_progress: Callable[[str], None],
        **_kwargs: object,
    ) -> object:
        for _ in range(4):
            objective_progress("unknown_keepalive_marker")
        return contract

    monkeypatch.setattr(checker, "build_live_contract", marker_spam)
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")

    report = checker._run_one_process_closeout(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        output=output,
        cold=True,
        _process_start_method="fork",
    )

    assert report["status"] == "fail"
    assert report["second_pass_started"] is False
    assert any(
        issue["code"] == "objective_progress_protocol_error" for issue in report["issues"]
    ), report["issues"]


def test_warm_closeout_stage_plan_primes_cache_inside_spawn_worker() -> None:
    assert checker._closeout_stage_plan(cold=False) == (
        "warmup_owner_derivation",
        "warm_owner_derivation",
        "cache_hit_derivation",
    )


def test_normal_byte_stability_path_uses_killable_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _warm_bundle(monkeypatch)
    monkeypatch.setattr(checker, "load_owner_bundle", lambda *_args, **_kwargs: bundle)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    payload = checker.contract_bytes(contract)
    calls: list[bool] = []
    start_methods: list[str] = []

    def monitored(
        *_args: object,
        cold: bool,
        process_start_method: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        calls.append(cold)
        start_methods.append(process_start_method)
        return {
            "first_bytes": payload,
            "second_bytes": payload,
            "profiling_stop": False,
            "worker_error": None,
        }

    monkeypatch.setattr(checker, "_run_closeout_worker", monitored)
    monkeypatch.setattr(
        checker,
        "build_live_contract",
        lambda *_args, **_kwargs: pytest.fail("unmonitored build executed"),
    )

    derived, derived_bytes = checker._derive_byte_stable_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )

    assert calls == [True]
    assert start_methods == ["spawn"]
    assert derived == contract
    assert derived_bytes == payload


def test_objectively_progressing_cold_worker_may_exceed_two_x_without_termination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _warm_bundle(monkeypatch)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    output = tmp_path / "confidence-ledger.json"
    output.write_bytes(checker.contract_bytes(contract))
    monkeypatch.setattr(checker, "_HEARTBEAT_INTERVAL_SECONDS", 0.01)
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cold_owner_derivation",
        0.5,
    )
    monkeypatch.setitem(
        checker._HISTORICAL_STAGE_SECONDS,
        "cache_hit_derivation",
        0.5,
    )
    report_owner_progress = adapter._report_owner_progress

    def slow_real_owner_progress(milestone: str) -> None:
        report_owner_progress(milestone)
        time.sleep(0.05)

    monkeypatch.setattr(adapter, "_report_owner_progress", slow_real_owner_progress)
    monkeypatch.setattr(
        adapter,
        "_owner_consumed_input_set",
        lambda *_args, **_kwargs: contract.owner_bundle_projection.consumed_inputs,
    )
    stats = iter(
        (
            {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
            {"hits": 1, "misses": 1, "maxsize": 4, "currsize": 1},
            {"hits": 2, "misses": 1, "maxsize": 4, "currsize": 1},
        )
    )
    monkeypatch.setattr(checker, "owner_bundle_cache_stats", lambda: next(stats))
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")

    report = checker._run_one_process_closeout(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        output=output,
        cold=True,
        _process_start_method="fork",
    )

    assert report["status"] == "pass", report["issues"]
    assert report["worker_terminated"] is False
    assert report["second_pass_started"] is True
    assert report["byte_stable_passes"] == 2
    assert report["first_derivation_wall_time_seconds"] > 0.4
    assert report["cold_closeout_budget_exceeded"] is True
    assert (
        report["cold_closeout_budget_disposition"]
        == "completed_with_objective_progress"
    )
    cold_comparison = next(
        row
        for row in report["historical_stage_comparison"]
        if row["stage"] == "cold_owner_derivation"
    )
    assert cold_comparison["within_two_x_historical"] is False


def test_closeout_writer_creates_missing_artifact_from_two_identical_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _warm_bundle(monkeypatch)
    contract = checker.build_live_contract(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )
    stats = iter(
        (
            {"hits": 0, "misses": 0, "maxsize": 4, "currsize": 0},
            {"hits": 0, "misses": 1, "maxsize": 4, "currsize": 1},
            {"hits": 1, "misses": 1, "maxsize": 4, "currsize": 1},
            {"hits": 2, "misses": 1, "maxsize": 4, "currsize": 1},
        )
    )
    monkeypatch.setattr(checker, "owner_bundle_cache_stats", lambda: next(stats))
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    output = tmp_path / "new-confidence-ledger.json"

    report = checker._run_one_process_closeout(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
        output=output,
        cold=False,
        write_output=True,
        _process_start_method="fork",
    )

    assert report["status"] == "pass", report["issues"]
    assert output.read_bytes() == checker.contract_bytes(contract)
    assert report["byte_stable_passes"] == 2


def _warm_bundle(monkeypatch: pytest.MonkeyPatch) -> adapter.OwnerEvidenceBundle:
    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        DEFAULT_N13B_CONTRACT,
        N13bAcquisitionExecutorContract,
    )

    capstone = json.loads(
        (POLICY_ENGINE_ROOT / adapter.DEFAULT_N10_CAPSTONE).read_text(encoding="utf-8")
    )
    n13b = N13bAcquisitionExecutorContract.model_validate_json(
        (POLICY_ENGINE_ROOT / DEFAULT_N13B_CONTRACT).read_bytes()
    )
    monkeypatch.setattr(adapter, "_recompute_n10_capstone", lambda _root: capstone)
    monkeypatch.setattr(
        adapter,
        "_recompute_n13b_contract",
        lambda _root, *, catalog_path, l5_path: n13b,
    )
    return adapter.load_owner_bundle(
        POLICY_ENGINE_ROOT,
        catalog_path=CATALOG_PATH,
        l5_path=L5_PATH,
    )


class _ProjectionValue:
    def __init__(self, **values: object) -> None:
        self._values = values
        for name, value in values.items():
            setattr(self, name, value)

    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "json"
        return dict(self._values)


def _fake_n13b_contract(
    *,
    authority_projection_sha256: str = "sha256:" + "1" * 64,
    outside_projection: str = "stable",
) -> SimpleNamespace:
    return SimpleNamespace(
        authority_owner=_ProjectionValue(
            projection_sha256=authority_projection_sha256,
            registry_entry_count=1,
        ),
        quarantine=_ProjectionValue(
            projection_sha256="sha256:" + "3" * 64,
            live_attempt_count=5,
            response_admitted_count=0,
            overlay_admitted_observation_count=0,
        ),
        world_growth=_ProjectionValue(
            projection_sha256="sha256:" + "4" * 64,
            admitted_observation_count=0,
            event_count=0,
        ),
        journal=SimpleNamespace(response_admitted_count=0),
        outside_projection=outside_projection,
    )


def _stub_n13b_recomputation(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stored: SimpleNamespace,
    recomputed: SimpleNamespace,
) -> None:
    from tools.quality.validation import layer3_gy_n13b_acquisition_contract as n13b_owner

    contract_path = tmp_path / adapter.DEFAULT_N13B_CONTRACT
    contract_path.parent.mkdir(parents=True)
    contract_path.write_bytes(b"stored-n13b-contract")
    (tmp_path / "catalog.duckdb").write_bytes(b"catalog")
    (tmp_path / "l5.json").write_bytes(b"l5")
    monkeypatch.setattr(
        n13b_owner.N13bAcquisitionExecutorContract,
        "model_validate_json",
        classmethod(lambda _cls, _payload: stored),
    )
    monkeypatch.setattr(
        n13b_owner,
        "derive_n13b_acquisition_executor_contract",
        lambda **_kwargs: recomputed,
    )
