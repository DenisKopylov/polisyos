"""Exercise a producer-issued N5 witness in an ordinary served acquisition."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy._core import _methods as numpy_methods

from polisyos.core.artifacts import artifact_ref_identity_key
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.catalog.causal import ncm_engine
from polisyos.runtime.quality import joint_simulation_horizon as horizon_module
from polisyos.runtime.quality import n5_execution_basis as basis
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationResult,
    build_content_bound_simulation_receipt,
    verify_simulation_receipt,
)
from tests._helpers import acquisition_served_history as fixture
from tests._helpers.candidate_cycle_source_profile import (
    build_candidate_cycle_substrate_route_inputs,
)
from tests.integration.core_runtime.test_acquisition_retained_sequential_served import (
    _OwnerCallMonitor,
    _SequentialOracle,
)
from tests.integration.runtime_quality._n5_consumed_binding_falsifiers import (
    assert_real_n5_instance_entry_shadows_refused,
    assert_unconsumed_slots_do_not_change_real_n5_witness,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)
_KEY = "n5_execution_implementation_witness"


def _replace_payload(
    result: JointSimulationResult, payload: dict[str, Any], *, rebuild_receipt: bool
) -> JointSimulationResult:
    """Create an adversarial copy of a real result, never a positive fixture."""
    receipt = result.receipt
    if rebuild_receipt:
        receipt = build_content_bound_simulation_receipt(
            engine_kind=receipt.engine_kind,
            payload=payload,
            diagnostics=payload["diagnostics"],
        )
    altered = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    altered._content_payload = payload
    verify_simulation_receipt(altered.receipt, altered.content_bound_payload())
    return altered


def test_served_actual_v5_n5_witness_reconciles_owner_quantities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """The actual served B owns its witness; changed inputs, results and owners do not."""
    checked: list[str] = []

    def check_real_result(
        *,
        ctx: Any,
        oracle: Any,
        actual_b: Any,
        selected_b: Any,
        witness: Any,
        capture: Any,
        issue_equal_source: Any,
    ) -> None:
        del ctx, issue_equal_source
        with tenant_scope(None, tenant_id=fixture.TENANT, cell_id=fixture.CELL):
            result = actual_b.result
            input_ref = selected_b.n5_input_ref
            result_ref = selected_b.n5_result_ref
            candidate, problem = actual_b.source.candidate, actual_b.source.problem
            assert capture._admission is not None
            port = capture._admission.port
            assert capture._admission.controller is capture._controller is port._controller
            assert capture._admission.request is capture._request
            assert artifact_ref_identity_key(capture._admission.input_ref) == (
                artifact_ref_identity_key(input_ref)
            )
            assert capture._admission.input_content_hash == actual_b.input_record.content_hash
            assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness
            assert witness.predicate_provenance == "recomputed" and not witness.reason_codes
            assert witness.input_ref_identity == artifact_ref_identity_key(input_ref)
            assert input_ref.manifest_profile_sha256 is not None
            assert result.trajectories
            consumed_configuration = horizon_module.read_joint_simulation_configuration(
                capture._controller
            )
            prepared_configuration = horizon_module.prepare_joint_simulation_configuration()
            assert (
                type(consumed_configuration) is horizon_module.PreparedJointSimulationConfiguration
            )
            assert witness.consumed_configuration_values == basis._exact_native_content(
                consumed_configuration
            )
            assert witness.consumed_configuration_values == basis._exact_native_content(
                prepared_configuration
            )
            observed = {
                (row[0], row[1]) for row in witness.implementation["source"]["executed_code"]
            }
            controller_run = horizon_module.JointSimulationHorizonController.run
            numerical_entry = ncm_engine.NCMEngineMethod.pure_step
            assert (controller_run.__module__, controller_run.__code__.co_qualname) in observed
            assert (numerical_entry.__module__, numerical_entry.__code__.co_qualname) in observed
            # Capture-only configuration introspection is not numerical work.
            # No production callable is swapped to manufacture this context.
            for introspection in (
                horizon_module.read_joint_simulation_configuration,
                horizon_module.prepare_joint_simulation_configuration,
            ):
                assert (
                    introspection.__module__,
                    introspection.__code__.co_qualname,
                ) not in observed
            monitor_callback = oracle.monitor._on_start.__func__
            assert (
                monitor_callback.__module__,
                monitor_callback.__code__.co_qualname,
            ) not in observed
            assert any(
                row[0] == ncm_engine.__name__ and row[1] == "_parallel_worlds"
                for row in witness.implementation["source"]["executed_code"]
            ), "the selected NCM helper was not observed"

            # Reconstruct only the unbound copy of this actual result, for
            # adversarial relabeling checks; never use it as a positive witness.
            original_payload = deepcopy(result.content_bound_payload())
            del original_payload["diagnostics"][_KEY]
            original = _replace_payload(result, original_payload, rebuild_receipt=True)
            assert basis.exact_n5_content_bytes(original.content_bound_payload()) == (
                capture._result_bytes
            )

            # Both selectors name real CAS artifacts from this execution.
            assert artifact_ref_identity_key(result_ref) != artifact_ref_identity_key(input_ref)
            with pytest.raises(ValueError, match="n5_execution_witness_input_mismatch"):
                basis.reconcile_live_n5_implementation(result, input_ref=result_ref)
            with pytest.raises(ValueError, match="n5_execution_capture_input_relabelled"):
                basis.bind_n5_execution_implementation(
                    original, input_ref=result_ref, capture=capture
                )

            # This input changes the actual result's world state. GY's legacy
            # hash drops the key recursively and cannot decide this equality.
            changed_request = capture._request.model_copy(deep=True)
            assert changed_request.world_credal_state_before.get("runtime_metrics") != {
                "witness_probe": 1
            }
            changed_request.world_credal_state_before["runtime_metrics"] = {"witness_probe": 1}
            with (
                pytest.raises(ValueError, match="n5_implementation_input_request_mismatch"),
                basis.observe_candidate_n5_execution_input(
                    port=port,
                    candidate=candidate,
                    problem=problem,
                    request=changed_request,
                    input_ref=input_ref,
                ),
            ):
                pass
            # A receipt digest is not the equality predicate: force a collision.
            with monkeypatch.context() as mutation:
                mutation.setattr(
                    basis, "exact_n5_content_hash", lambda _value: "sha256:" + "0" * 64
                )
                with (
                    pytest.raises(ValueError, match="n5_implementation_input_request_mismatch"),
                    basis.observe_candidate_n5_execution_input(
                        port=port,
                        candidate=candidate,
                        problem=problem,
                        request=changed_request,
                        input_ref=input_ref,
                    ),
                ):
                    pass

            # The legacy GY receipt ignores this field. A witness must bind the
            # complete actual result even when that ordinary receipt still verifies.
            altered_payload = deepcopy(result.content_bound_payload())
            for key in ("world_credal_state_before", "world_credal_state_after"):
                altered_payload[key]["runtime_metrics"] = {"witness_probe": 1}
            altered = _replace_payload(result, altered_payload, rebuild_receipt=False)
            with pytest.raises(ValueError, match="n5_execution_witness_result_mismatch"):
                basis.reconcile_live_n5_implementation(altered, input_ref=input_ref)
            unbound_payload = deepcopy(original.content_bound_payload())
            for key in ("world_credal_state_before", "world_credal_state_after"):
                unbound_payload[key]["runtime_metrics"] = {"witness_probe": 1}
            altered_original = _replace_payload(original, unbound_payload, rebuild_receipt=False)
            with pytest.raises(ValueError, match="n5_execution_capture_result_relabelled"):
                basis.bind_n5_execution_implementation(
                    altered_original, input_ref=input_ref, capture=capture
                )

            # A rehashed caller witness is structurally valid, but was not issued
            # by the real producer's registry.
            forged_payload = deepcopy(result.content_bound_payload())
            forged_witness = forged_payload["diagnostics"][_KEY]
            forged_witness["request_content_hash"] = "sha256:" + "e" * 64
            forged_witness["content_hash"] = basis.exact_n5_content_hash(
                {name: value for name, value in forged_witness.items() if name != "content_hash"}
            )
            forged = _replace_payload(result, forged_payload, rebuild_receipt=True)
            with pytest.raises(ValueError, match="n5_execution_witness_not_producer_observed"):
                basis.reconcile_live_n5_implementation(forged, input_ref=input_ref)

            # Independent controls keep genuine selected output/source markers
            # intact while changing the actual next-call entry binding.
            assert_real_n5_instance_entry_shadows_refused(
                port=port,
                result=result,
                request=capture._request,
                input_ref=input_ref,
                monkeypatch=monkeypatch,
            )
            assert_unconsumed_slots_do_not_change_real_n5_witness(
                result=result,
                input_ref=input_ref,
                monkeypatch=monkeypatch,
            )

            real_helper = ncm_engine._parallel_worlds
            with monkeypatch.context() as mutation:
                mutation.setattr(ncm_engine, "_parallel_worlds", lambda *a, **k: [])
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert ncm_engine._parallel_worlds is real_helper

            # NCM reads np.mean for each actual outcome. This transitive Python
            # helper is called by NumPy without changing np.mean or native images.
            real_numpy_mean = numpy_methods._mean
            sample = np.asarray([0.0, 2.0])
            assert float(np.mean(sample)) == 1.0

            def shifted_numpy_mean(*args: Any, **kwargs: Any) -> Any:
                return real_numpy_mean(*args, **kwargs) + 1.0

            with monkeypatch.context() as mutation:
                mutation.setattr(numpy_methods, "_mean", shifted_numpy_mean)
                assert float(np.mean(sample)) == 2.0
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert numpy_methods._mean is real_numpy_mean

            # The already-active numerical caller resolves this imported class to
            # construct the actual NCM query. Keep the original type admissible to
            # NCM while changing the evidence supplied to its constructor.
            original_query_type = horizon_module.NCMQueryData
            ncm_spec = capture._request.engine_plan[0].ncm_spec
            evidence = dict(capture._request.baseline_state)
            assert ncm_spec is not None and evidence

            class ChangedQueryData(original_query_type):
                def __init__(self, **values: Any) -> None:
                    values["evidence"] = {
                        name: value + 1.0 for name, value in values["evidence"].items()
                    }
                    super().__init__(**values)

            original_query = original_query_type(ncm_spec=ncm_spec, evidence=evidence)
            with monkeypatch.context() as mutation:
                mutation.setattr(horizon_module, "NCMQueryData", ChangedQueryData)
                changed_query = horizon_module.NCMQueryData(ncm_spec=ncm_spec, evidence=evidence)
                assert isinstance(changed_query, original_query_type)
                assert changed_query.evidence != original_query.evidence
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert horizon_module.NCMQueryData is original_query_type

            # Replace the actual registry entry while retaining its FQN and
            # signature. The original historical NCM class remains live.
            registry = port._controller._registry
            decision = next(item for item in result.engine_decisions if item.decision == "selected")
            assert decision.method_fqn is not None
            entry = registry.get_entry(decision.method_fqn)
            assert entry is not None
            original_method = registry.get(decision.method_fqn)

            class SameFQNReplacement:
                signature = original_method.signature
                metadata = original_method.metadata

                @staticmethod
                def pure_step(*args: Any, **kwargs: Any) -> dict[str, Any]:
                    return {"counterfactual_result": {"world_summaries": []}}

            with monkeypatch.context() as mutation:
                mutation.setattr(entry, "_cached_class", SameFQNReplacement)
                assert registry.get(decision.method_fqn) is SameFQNReplacement
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert registry.get(decision.method_fqn) is original_method
            assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness
            checked.append(actual_b.input_record.content_hash)

    source = build_candidate_cycle_substrate_route_inputs(tmp_path / "candidate-source")
    with _OwnerCallMonitor() as monitor:
        oracle = _SequentialOracle(monkeypatch, monitor, after_real_b=check_real_result)
        produced = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            sequential_oracle=oracle,
        )
    assert produced is not None and produced["run_id"] and produced["candidate_id"]
    assert len(checked) == 1, "no genuine served B result reached the witness oracle"
