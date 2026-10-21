from __future__ import annotations

import hashlib
import inspect
import json
import struct
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
from polisyos.ir import kernel as kernel_facade
from polisyos.ir.kernel.method_metrics import (
    METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
    METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
    MethodMetricBackendAttempt,
    MethodMetricCapturedInputArray,
    MethodMetricExecutionContext,
    MethodMetricInputContext,
    MethodMetricInputRole,
    MethodMetricInputRoleContext,
    MethodMetricParameterContext,
    MethodMetricSemanticContract,
    MethodMetricSourceUnit,
    RegisteredMethodMetricLawResult,
    apply_registered_direct_output_law,
    apply_registered_ex_ante_mean_change_law,
    apply_registered_method_metric_unit_adapter,
    registered_method_metric_law_metadata,
    registered_method_metric_law_metadata_for,
    registered_method_metric_semantics_match,
    resolve_registered_method_metric_unit_adapter,
)
from polisyos.ir.kernel.units import CountUnit, GenericUnit, RateUnit


def _semantic_contract(*, input_roles=()):
    return MethodMetricSemanticContract(
        quantity_kind="economic.rate",
        quantity_role="outcome.level",
        population_id="population.target",
        axes=("time.year",),
        denominator_id="population.eligible",
        time_role="period.end",
        producer_contract_id="producer.policy_metric.v1",
        input_roles=input_roles,
    )


def _execution_context(
    *,
    dispatch_outcome: str = "succeeded",
    input_role_values: tuple[MethodMetricInputRoleContext, ...] | None = None,
    parameter_resolution_status: str = "captured",
    seed_status: str = "reconciled",
    backend_identity_status: str = "reconciled",
    backend_trace_status: str = "captured",
    rng_state_status: str = "key_captured",
) -> MethodMetricExecutionContext:
    started_at = datetime(2026, 10, 20, tzinfo=UTC)
    return MethodMetricExecutionContext(
        dispatch_outcome=dispatch_outcome,
        method_fqn="test.metric",
        method_version="1.0.0",
        method_abi_digest="a" * 64,
        method_abi_digest_algorithm="blake2b",
        output_slot_id="result",
        started_at=started_at,
        completed_at=started_at + timedelta(milliseconds=1),
        dispatch_elapsed_ms=1.0,
        runner_wall_time_ms=1.0,
        graph_input_ids=("graph.input.n",),
        signature_input_slot_ids=("n",),
        signature_output_slot_ids=("result",),
        signature_parameter_names=("rate",),
        parameter_resolution_status=parameter_resolution_status,
        parameter_values=(
            MethodMetricParameterContext(
                name="rate",
                source=(
                    "requested"
                    if parameter_resolution_status == "captured"
                    else "signature_default_unresolved"
                ),
                status=(
                    "captured" if parameter_resolution_status == "captured" else "unsupported_codec"
                ),
                value_sha256=("c" * 64 if parameter_resolution_status == "captured" else None),
            ),
        ),
        prestate_identity_status="captured",
        prestate_identity_sha256="b" * 64,
        input_slot_values=(
            MethodMetricInputContext(
                method_input_slot_id="n",
                status="captured",
                value_sha256="d" * 64,
            ),
        ),
        input_role_values=(
            input_role_values
            if input_role_values is not None
            else (
                MethodMetricInputRoleContext(
                    role_id="population.denominator",
                    method_input_slot_id="n",
                    value_sha256="d" * 64,
                ),
            )
        ),
        seed_status=seed_status,
        root_seed=11,
        step=4,
        method_seed=19,
        reproducibility_seed=19,
        method_key_words=(19, 23),
        rng_state_status=rng_state_status,
        requested_backend="jax",
        selected_backend="cpu",
        backend_selection_reason="test_profile",
        backend_trace_status=backend_trace_status,
        backend_attempts=(
            (MethodMetricBackendAttempt(backend="cpu", outcome="success"),)
            if backend_trace_status == "captured"
            else ()
        ),
        fallback_status=(
            "not_fell_back" if backend_trace_status == "captured" else "not_established"
        ),
        backend_identity_status=backend_identity_status,
        actual_backend="cpu" if backend_identity_status == "reconciled" else None,
    )


def _direct_law(value: object, semantics: MethodMetricSemanticContract, context=None):
    return apply_registered_direct_output_law(
        value,
        semantics,
        execution_context=context or _execution_context(),
        expected_method_fqn="test.metric",
        expected_method_version="1.0.0",
        expected_method_abi_digest="a" * 64,
        expected_method_abi_digest_algorithm="blake2b",
        expected_output_slot_id="result",
    )


def test_ratio_percent_adapter_uses_only_registered_exact_rational_pair() -> None:
    semantics = MethodMetricSemanticContract(
        quantity_kind="ratio",
        quantity_role="rate",
        population_id="population.target",
        axes=("time.year",),
        denominator_id="population.eligible",
        time_role="period.end",
        producer_contract_id=METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
    )
    law_id, law_version, law_digest = registered_method_metric_law_metadata()
    direct = RegisteredMethodMetricLawResult(
        law_id=law_id,
        law_version=law_version,
        code_digest=law_digest,
        status="available",
        value=0.25,
        exact_value_numerator=1,
        exact_value_denominator=4,
    )
    ratio = MethodMetricSourceUnit(dimension="ratio", symbol="ratio", scale=1.0)
    percent = MethodMetricSourceUnit(dimension="ratio", symbol="percent", scale=0.01)

    to_percent = resolve_registered_method_metric_unit_adapter(
        ratio, RateUnit(base="percent"), law_id=law_id, semantics=semantics
    )
    to_ratio = resolve_registered_method_metric_unit_adapter(
        percent, RateUnit(base="ratio"), law_id=law_id, semantics=semantics
    )
    converted = apply_registered_method_metric_unit_adapter(direct, to_percent)

    assert (
        to_percent.operation,
        to_percent.factor_numerator,
        to_percent.factor_denominator,
    ) == (
        "ratio_to_percent",
        100,
        1,
    )
    assert (
        to_ratio.operation,
        to_ratio.factor_numerator,
        to_ratio.factor_denominator,
    ) == (
        "percent_to_ratio",
        1,
        100,
    )
    assert converted.status == "available"
    assert converted.value == 25.0
    assert to_percent.adapter_id == to_ratio.adapter_id
    assert to_percent.code_digest.startswith("sha256:")


def test_equal_dimensions_do_not_authorize_unregistered_unit_conversion() -> None:
    source = MethodMetricSourceUnit(dimension="ratio", symbol="ratio", scale=1.0)

    conversion = resolve_registered_method_metric_unit_adapter(source, CountUnit(label="person"))

    assert conversion.operation == "unsupported"
    assert conversion.limitation == "unit_relation_not_registered"


@pytest.mark.parametrize(
    ("identity_status", "actual_backend", "accepted"),
    [
        ("reconciled", "cpu", True),
        ("reconciled", None, False),
        ("reconciled", "gpu", False),
        ("mismatch", None, True),
        ("mismatch", "cpu", False),
        ("not_established", None, True),
        ("not_established", "gpu", False),
    ],
)
def test_backend_identity_status_and_observed_identity_matrix(
    identity_status: str, actual_backend: str | None, accepted: bool
) -> None:
    payload = _execution_context().model_dump(mode="python")
    payload["backend_identity_status"] = identity_status
    payload["actual_backend"] = actual_backend

    if accepted:
        context = MethodMetricExecutionContext.model_validate(payload)
        assert context.backend_identity_status == identity_status
        assert context.actual_backend == actual_backend
    else:
        refusal = (
            "reconciled_method_metric_backend_requires_identity"
            if identity_status == "reconciled"
            else "unreconciled_method_metric_backend_cannot_have_identity"
        )
        with pytest.raises(ValueError, match=refusal):
            MethodMetricExecutionContext.model_validate(payload)


@pytest.mark.parametrize(
    ("provider_updates", "expected_refusal"),
    [
        pytest.param(
            {"requested_backend": None},
            "captured_method_metric_backend_trace_is_incomplete",
            id="requested-backend-absent",
        ),
        pytest.param(
            {"requested_backend": " "},
            "reconciled_method_metric_backend_requires_identity",
            id="requested-backend-blank",
        ),
        pytest.param(
            {"selected_backend": None},
            "captured_method_metric_backend_trace_is_incomplete",
            id="selected-backend-absent",
        ),
        pytest.param(
            {
                "selected_backend": "gpu",
                "backend_attempts": ({"backend": "gpu", "outcome": "success"},),
            },
            "reconciled_method_metric_backend_requires_identity",
            id="selected-backend-differs-from-actual-with-valid-trace",
        ),
        pytest.param(
            {
                "backend_trace_status": "not_established",
                "backend_attempts": (),
                "fallback_status": "not_established",
            },
            "reconciled_method_metric_backend_requires_identity",
            id="backend-trace-not-established-with-matching-identity",
        ),
        pytest.param(
            {"backend_attempts": ()},
            "captured_method_metric_backend_trace_is_incomplete",
            id="captured-trace-terminal-attempt-absent",
        ),
        pytest.param(
            {"backend_attempts": ({"backend": "gpu", "outcome": "success"},)},
            "captured_method_metric_backend_trace_is_incomplete",
            id="captured-trace-terminal-backend-disagrees-with-selected",
        ),
        pytest.param(
            {"backend_attempts": ({"backend": "cpu", "outcome": "failed"},)},
            "captured_method_metric_backend_trace_is_incomplete",
            id="captured-trace-terminal-attempt-not-successful",
        ),
        pytest.param(
            {"actual_backend": None},
            "reconciled_method_metric_backend_requires_identity",
            id="actual-backend-absent",
        ),
        pytest.param(
            {
                "actual_backend": " ",
                "selected_backend": " ",
                "backend_attempts": ({"backend": " ", "outcome": "success"},),
            },
            "reconciled_method_metric_backend_requires_identity",
            id="actual-backend-blank-with-other-identity-fields-matching",
        ),
    ],
)
def test_reconciled_backend_identity_rejects_each_provider_premise_independently(
    provider_updates: dict[str, object], expected_refusal: str
) -> None:
    payload = _execution_context().model_dump(mode="python")
    payload.update(provider_updates)

    with pytest.raises(ValueError, match=expected_refusal):
        MethodMetricExecutionContext.model_validate(payload)


def test_direct_output_law_never_infers_meaning_from_complete_caller_context() -> None:
    semantics = _semantic_contract(
        input_roles=(
            MethodMetricInputRole(
                role_id="population.denominator",
                method_input_slot_id="n",
            ),
        )
    )

    result = _direct_law(0.25, semantics)

    assert result.status == "unavailable"
    assert result.value is None
    assert result.limitation == "registered_method_metric_law_missing"


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "0.25", [0.25]])
def test_direct_output_law_never_treats_shape_or_numeric_type_as_semantic_meaning(
    value: object,
) -> None:
    result = _direct_law(value, _semantic_contract())

    assert result.status == "unavailable"
    assert result.value is None
    assert result.limitation == "registered_method_metric_law_missing"


def _exact_registered_law_result(
    value: int | float, numerator: int, denominator: int
) -> RegisteredMethodMetricLawResult:
    law_id, law_version, code_digest = registered_method_metric_law_metadata_for(
        "policy.evaluation.ex_ante_simulation@1.0.0", "1.0.0"
    ) or (None, None, None)
    assert law_id is not None and law_version is not None and code_digest is not None
    return RegisteredMethodMetricLawResult(
        law_id=law_id,
        law_version=law_version,
        code_digest=code_digest,
        status="available",
        value=value,
        exact_value_numerator=numerator,
        exact_value_denominator=denominator,
    )


def test_large_integer_is_preserved_exactly_and_withheld_from_float_projection() -> None:
    semantics = _semantic_contract(
        input_roles=(
            MethodMetricInputRole(
                role_id="population.denominator",
                method_input_slot_id="n",
            ),
        )
    )
    direct = _exact_registered_law_result(2**53 + 1, 2**53 + 1, 1)
    identity = resolve_registered_method_metric_unit_adapter(
        MethodMetricSourceUnit(dimension="value", symbol="amount", scale=1),
        GenericUnit(label="value"),
        law_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        semantics=_ex_ante_semantics(),
    )
    projected = apply_registered_method_metric_unit_adapter(direct, identity)

    assert direct.value == 2**53 + 1
    assert direct.exact_value_numerator == 2**53 + 1
    assert direct.exact_value_denominator == 1
    assert projected.status == "unavailable"
    assert projected.value is None
    assert projected.exact_value_numerator == 2**53 + 1
    assert projected.limitation == "numeric_precision_not_established"


def test_exact_binary64_integer_remains_projectable() -> None:
    semantics = _semantic_contract(
        input_roles=(
            MethodMetricInputRole(
                role_id="population.denominator",
                method_input_slot_id="n",
            ),
        )
    )
    direct = _exact_registered_law_result(2**53, 2**53, 1)
    projected = apply_registered_method_metric_unit_adapter(
        direct,
        resolve_registered_method_metric_unit_adapter(
            MethodMetricSourceUnit(dimension="value", symbol="amount", scale=1),
            GenericUnit(label="value"),
            law_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
            semantics=_ex_ante_semantics(),
        ),
    )

    assert projected.status == "available"
    assert projected.value == float(2**53)


def _ex_ante_semantics() -> MethodMetricSemanticContract:
    return MethodMetricSemanticContract(
        quantity_kind="value",
        quantity_role="scenario_delta",
        population_id="captured_model_input_rows",
        axes=("n_agents",),
        denominator_id="n_agents",
        time_role="pre_dispatch_state",
        producer_contract_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        input_roles=(
            MethodMetricInputRole(role_id="baseline", method_input_slot_id="baseline"),
            MethodMetricInputRole(role_id="scenario", method_input_slot_id="scenario"),
        ),
        output_value_path=("mean_change",),
    )


def _input_digest(values: tuple[int | float, ...], *, dtype: str = "<f8") -> str:
    digest = hashlib.sha256()
    digest.update(dtype.encode("ascii"))
    digest.update(json.dumps([len(values)], separators=(",", ":")).encode("ascii"))
    if dtype == "<f8":
        digest.update(struct.pack(f"<{len(values)}d", *(float(value) for value in values)))
    elif dtype == "<i8":
        digest.update(struct.pack(f"<{len(values)}q", *(int(value) for value in values)))
    else:
        raise AssertionError("test only needs binary64 and signed 64-bit input encoding")
    return digest.hexdigest()


def _ex_ante_method_identity() -> dict[str, str]:
    signature = ExAnteSimulationEstimator.signature
    source = inspect.getsource(ExAnteSimulationEstimator).encode("utf-8")
    return {
        "method_fqn": signature.fqn,
        "method_version": signature.version,
        "method_abi_digest": signature.abi_digest(),
        "method_abi_digest_algorithm": "blake2b",
        "method_build_digest": "sha256:" + hashlib.sha256(source).hexdigest(),
        "method_build_digest_scope": "class_source_only",
    }


def _ex_ante_execution_context(
    *,
    baseline: tuple[int | float, ...] = (1.0, 2.0, 5.0),
    scenario: tuple[int | float, ...] = (2.0, 1.0, 8.0),
    prestate_sha256: str = "b" * 64,
    dtype: str = "<f8",
) -> tuple[MethodMetricExecutionContext, tuple[MethodMetricCapturedInputArray, ...]]:
    started_at = datetime(2026, 10, 20, tzinfo=UTC)
    baseline_digest = _input_digest(baseline, dtype=dtype)
    scenario_digest = _input_digest(scenario, dtype=dtype)
    signature = ExAnteSimulationEstimator.signature
    template = _execution_context().model_dump(mode="python")
    template.update(_ex_ante_method_identity())
    template.update(
        {
            "output_slot_id": "result",
            "output_value_path": ("mean_change",),
            "signature_input_slot_ids": tuple(sorted(slot.name for slot in signature.input_slots)),
            "signature_output_slot_ids": tuple(
                sorted(slot.name for slot in signature.output_slots)
            ),
            "signature_parameter_names": tuple(sorted(item.name for item in signature.parameters)),
            "dispatch_outcome": "succeeded",
            "started_at": started_at,
            "completed_at": started_at + timedelta(milliseconds=1),
            "graph_input_ids": ("baseline", "scenario"),
            "parameter_resolution_status": "captured",
            "parameter_values": tuple(
                MethodMetricParameterContext(
                    name=parameter.name,
                    source="signature_default",
                    status="captured",
                    value_sha256=hashlib.sha256(
                        json.dumps(
                            parameter.default,
                            ensure_ascii=False,
                            allow_nan=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                )
                for parameter in signature.parameters
            ),
            "prestate_identity_status": "captured",
            "prestate_identity_sha256": prestate_sha256,
            "input_slot_values": (
                MethodMetricInputContext(
                    method_input_slot_id="baseline",
                    status="captured",
                    value_sha256=baseline_digest,
                ),
                MethodMetricInputContext(
                    method_input_slot_id="scenario",
                    status="captured",
                    value_sha256=scenario_digest,
                ),
            ),
            "input_role_values": (
                MethodMetricInputRoleContext(
                    role_id="baseline",
                    method_input_slot_id="baseline",
                    value_sha256=baseline_digest,
                ),
                MethodMetricInputRoleContext(
                    role_id="scenario",
                    method_input_slot_id="scenario",
                    value_sha256=scenario_digest,
                ),
            ),
            "requested_backend": "numpy",
            "selected_backend": "numpy",
            "backend_selection_reason": "registered_numpy_method",
            "actual_backend": "numpy",
            "backend_trace_status": "captured",
            "backend_attempts": (MethodMetricBackendAttempt(backend="numpy", outcome="success"),),
            "fallback_status": "not_fell_back",
            "backend_identity_status": "reconciled",
            "seed_status": "reconciled",
            "rng_state_status": "runner_rng_state_not_retained",
        }
    )
    context = MethodMetricExecutionContext.model_validate(template)
    source_unit = MethodMetricSourceUnit(dimension="value", symbol="amount", scale=1)
    inputs = (
        MethodMetricCapturedInputArray(
            slot_id="baseline",
            dtype=dtype,
            shape=(len(baseline),),
            values=baseline,
            value_sha256=baseline_digest,
            unit=source_unit,
        ),
        MethodMetricCapturedInputArray(
            slot_id="scenario",
            dtype=dtype,
            shape=(len(scenario),),
            values=scenario,
            value_sha256=scenario_digest,
            unit=source_unit,
        ),
    )
    return context, inputs


def _ex_ante_law(
    value: float,
    *,
    context: MethodMetricExecutionContext | None = None,
    inputs: tuple[MethodMetricCapturedInputArray, ...] | None = None,
    prestate_sha256: str = "b" * 64,
    semantics: MethodMetricSemanticContract | None = None,
    output_path: tuple[str, ...] = ("mean_change",),
):
    default_context, default_inputs = _ex_ante_execution_context()
    identity = _ex_ante_method_identity()
    return apply_registered_ex_ante_mean_change_law(
        value,
        semantics or _ex_ante_semantics(),
        execution_context=context or default_context,
        input_values=inputs or default_inputs,
        input_capture_prestate_identity_sha256=prestate_sha256,
        expected_method_fqn=identity["method_fqn"],
        expected_method_version=identity["method_version"],
        expected_method_abi_digest=identity["method_abi_digest"],
        expected_method_abi_digest_algorithm=identity["method_abi_digest_algorithm"],
        expected_method_build_digest=identity["method_build_digest"],
        expected_output_slot_id="result",
        expected_output_value_path=output_path,
        target_unit=GenericUnit(label="value"),
    )


def test_registered_ex_ante_semantics_are_exact_and_method_scoped() -> None:
    semantics = _ex_ante_semantics()
    metadata = registered_method_metric_law_metadata_for(
        "policy.evaluation.ex_ante_simulation@1.0.0",
        "1.0.0",
    )
    wrong_method = registered_method_metric_law_metadata_for("other.method", "1.0.0")
    wrong_denominator = semantics.model_copy(update={"denominator_id": "population_size"})

    assert metadata is not None
    assert metadata[0] == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
    assert registered_method_metric_semantics_match(metadata[0], semantics)
    assert not registered_method_metric_semantics_match(metadata[0], wrong_denominator)
    assert wrong_method is None
    assert kernel_facade.MethodMetricExecutionContext is MethodMetricExecutionContext
    assert (
        kernel_facade.apply_registered_ex_ante_mean_change_law
        is apply_registered_ex_ante_mean_change_law
    )


@pytest.mark.parametrize(
    ("updates", "limitation"),
    [
        pytest.param(
            {"dispatch_outcome": "failed"},
            "ex_ante_execution_context_not_established",
            id="failed-dispatch",
        ),
        pytest.param(
            {"parameter_resolution_status": "not_established"},
            "ex_ante_execution_context_not_established",
            id="parameter-resolution-not-established",
        ),
        pytest.param(
            {"graph_input_ids": ("baseline",)},
            "ex_ante_execution_context_not_established",
            id="graph-input-inventory-incomplete",
        ),
        pytest.param(
            {"signature_parameter_names": (), "parameter_values": ()},
            "ex_ante_execution_context_not_established",
            id="signature-parameter-inventory-does-not-match-law",
        ),
        pytest.param(
            {
                "signature_input_slot_ids": ("baseline",),
                "input_slot_values": (
                    MethodMetricInputContext(
                        method_input_slot_id="baseline", status="captured", value_sha256="d" * 64
                    ),
                ),
                "input_role_values": (
                    MethodMetricInputRoleContext(
                        role_id="baseline", method_input_slot_id="baseline", value_sha256="d" * 64
                    ),
                ),
            },
            "ex_ante_execution_context_not_established",
            id="signature-input-inventory-incomplete",
        ),
        pytest.param(
            {"requested_backend": "accelerator"},
            "ex_ante_execution_context_not_established",
            id="requested-backend-disagrees-with-registered-method",
        ),
        pytest.param(
            {
                "selected_backend": "cpu",
                "actual_backend": "cpu",
                "backend_attempts": (MethodMetricBackendAttempt(backend="cpu", outcome="success"),),
            },
            "ex_ante_execution_context_not_established",
            id="selected-and-observed-backend-disagree-with-registered-method",
        ),
        pytest.param(
            {
                "backend_trace_status": "not_established",
                "backend_attempts": (),
                "fallback_status": "not_established",
                "backend_identity_status": "not_established",
                "actual_backend": None,
            },
            "ex_ante_execution_context_not_established",
            id="backend-trace-not-established",
        ),
        pytest.param(
            {
                "backend_attempts": (
                    MethodMetricBackendAttempt(backend="cpu", outcome="failure"),
                    MethodMetricBackendAttempt(backend="numpy", outcome="success"),
                ),
                "fallback_status": "fell_back",
            },
            "ex_ante_execution_context_not_established",
            id="backend-fell-back",
        ),
        pytest.param(
            {"backend_identity_status": "mismatch", "actual_backend": None},
            "ex_ante_execution_context_not_established",
            id="backend-identity-mismatch",
        ),
        pytest.param(
            {"backend_identity_status": "not_established", "actual_backend": None},
            "ex_ante_execution_context_not_established",
            id="backend-identity-not-established",
        ),
        pytest.param(
            {"seed_status": "mismatch"},
            "ex_ante_execution_context_not_established",
            id="seed-not-reconciled",
        ),
        pytest.param(
            {"rng_state_status": "key_captured"},
            "ex_ante_execution_context_not_established",
            id="runner-rng-retention-not-established",
        ),
    ],
)
def test_ex_ante_law_refuses_each_incomplete_execution_premise_independently(
    updates: dict[str, object], limitation: str
) -> None:
    context, inputs = _ex_ante_execution_context()
    payload = context.model_dump(mode="python")
    payload.update(updates)
    changed_context = MethodMetricExecutionContext.model_validate(payload)

    result = _ex_ante_law(1.0, context=changed_context, inputs=inputs)

    assert result.status == "unavailable"
    assert result.value is None
    assert result.limitation == limitation


def test_ex_ante_execution_context_rejects_unregistered_abi_digest_algorithm() -> None:
    context, _inputs = _ex_ante_execution_context()
    payload = context.model_dump(mode="python")
    payload["method_abi_digest_algorithm"] = "sha256"

    with pytest.raises(ValueError, match="method_abi_digest_algorithm"):
        MethodMetricExecutionContext.model_validate(payload)


@pytest.mark.parametrize(
    "updates",
    [
        pytest.param({"method_fqn": "other.method@1.0.0"}, id="method-fqn"),
        pytest.param({"method_version": "2.0.0"}, id="method-version"),
        pytest.param({"method_abi_digest": "0" * 64}, id="method-abi-digest"),
        pytest.param(
            {"method_build_digest": "sha256:" + "0" * 64},
            id="method-build-digest",
        ),
        pytest.param(
            {"method_build_digest": None, "method_build_digest_scope": "unavailable"},
            id="method-build-digest-scope",
        ),
        pytest.param({"output_slot_id": "other"}, id="output-slot"),
        pytest.param({"output_value_path": ("median_change",)}, id="output-value-path"),
        pytest.param({"signature_output_slot_ids": ()}, id="declared-output-inventory"),
    ],
)
def test_ex_ante_law_refuses_each_method_binding_identity_mismatch_independently(
    updates: dict[str, object],
) -> None:
    context, inputs = _ex_ante_execution_context()
    payload = context.model_dump(mode="python")
    payload.update(updates)
    changed_context = MethodMetricExecutionContext.model_validate(payload)

    result = _ex_ante_law(1.0, context=changed_context, inputs=inputs)

    assert result.status == "unavailable"
    assert result.value is None
    assert result.limitation == "method_execution_binding_identity_mismatch"


def test_ex_ante_mean_change_recomputes_actual_paired_input_rows() -> None:
    result = _ex_ante_law(1.0)

    assert result.status == "available"
    assert result.exact_value_numerator == 1
    assert result.exact_value_denominator == 1
    assert result.value == 1.0
    predicate_classes = {row.predicate_id: row.classification for row in result.predicate_evidence}
    assert predicate_classes["method_metric.paired_model_input_rows"] == "recomputed"
    assert predicate_classes["method_metric.n_agents_denominator"] == "recomputed"
    assert predicate_classes["method_metric.model_input_rowset_scope"] == "recomputed"
    assert predicate_classes["method_metric.external_row_representativeness"] == "not_established"
    assert predicate_classes["method_metric.external_causal_validity"] == "not_established"
    assert predicate_classes["method_metric.external_empirical_calibration"] == "not_established"
    assert predicate_classes["method_metric.external_legal_permission"] == "not_established"


def test_ex_ante_mean_change_requires_graph_input_slot_alignment() -> None:
    context, inputs = _ex_ante_execution_context()
    unbound_graph_input = context.model_copy(update={"graph_input_ids": ("baseline",)})

    result = _ex_ante_law(1.0, context=unbound_graph_input, inputs=inputs)

    assert result.status == "unavailable"
    assert result.limitation == "ex_ante_execution_context_not_established"


@pytest.mark.parametrize(
    "context_updates",
    [
        pytest.param({"dispatch_outcome": "failed"}, id="failed-dispatch"),
        pytest.param(
            {"parameter_resolution_status": "not_established"},
            id="parameter-resolution-unestablished",
        ),
        pytest.param({"graph_input_ids": ("baseline",)}, id="graph-input-omitted"),
        pytest.param({"parameter_values": ()}, id="parameter-inventory-omitted"),
        pytest.param(
            {"signature_parameter_names": ("other",)},
            id="parameter-signature-changed",
        ),
        pytest.param(
            {"signature_input_slot_ids": ("baseline",)},
            id="input-signature-incomplete",
        ),
        pytest.param(
            {"signature_output_slot_ids": ("result", "other")},
            id="output-signature-expanded",
        ),
        pytest.param({"requested_backend": None}, id="requested-backend-absent"),
        pytest.param({"selected_backend": "jax"}, id="selected-backend-differs"),
        pytest.param({"actual_backend": None}, id="actual-backend-absent"),
        pytest.param(
            {"backend_trace_status": "not_established"},
            id="backend-trace-unestablished",
        ),
        pytest.param(
            {"backend_identity_status": "not_established"},
            id="backend-identity-unreconciled",
        ),
        pytest.param({"fallback_status": "fell_back"}, id="backend-fell-back"),
        pytest.param({"seed_status": "mismatch"}, id="seed-mismatch"),
        pytest.param(
            {"rng_state_status": "key_captured"},
            id="runner-rng-retention-missing",
        ),
    ],
)
def test_ex_ante_law_rejects_each_unestablished_dispatch_context_predicate(
    context_updates: dict[str, object],
) -> None:
    context, inputs = _ex_ante_execution_context()

    result = _ex_ante_law(1.0, context=context.model_copy(update=context_updates), inputs=inputs)

    assert result.status == "unavailable"
    assert result.limitation == "ex_ante_execution_context_not_established"


@pytest.mark.parametrize(
    ("updates", "dto_accepts"),
    [
        pytest.param({"requested_backend": "accelerator"}, True, id="wrong-requested"),
        pytest.param(
            {
                "selected_backend": "cpu",
                "actual_backend": "cpu",
                "backend_attempts": (
                    MethodMetricBackendAttempt(backend="numpy", outcome="failure"),
                    MethodMetricBackendAttempt(backend="cpu", outcome="success"),
                ),
                "fallback_status": "fell_back",
            },
            True,
            id="reconciled-but-wrong-selected-and-actual",
        ),
        pytest.param(
            {
                "backend_attempts": (
                    MethodMetricBackendAttempt(backend="cpu", outcome="failure"),
                    MethodMetricBackendAttempt(backend="numpy", outcome="success"),
                ),
                "fallback_status": "fell_back",
            },
            True,
            id="reconciled-with-fallback",
        ),
        pytest.param(
            {"backend_identity_status": "mismatch", "actual_backend": None},
            True,
            id="mismatch-without-identity",
        ),
        pytest.param(
            {"backend_identity_status": "not_established", "actual_backend": None},
            True,
            id="not-established-without-identity",
        ),
        pytest.param(
            {
                "backend_trace_status": "not_established",
                "backend_attempts": (),
                "fallback_status": "not_established",
                "backend_identity_status": "not_established",
                "actual_backend": None,
            },
            True,
            id="trace-not-established",
        ),
        pytest.param(
            {"backend_identity_status": "reconciled", "actual_backend": None},
            False,
            id="reconciled-without-actual",
        ),
        pytest.param(
            {"backend_identity_status": "mismatch", "actual_backend": "cpu"},
            False,
            id="unexpected-actual-under-mismatch",
        ),
        pytest.param(
            {"backend_identity_status": "not_established", "actual_backend": "numpy"},
            False,
            id="actual-present-under-unestablished-status",
        ),
        pytest.param({"requested_backend": None}, False, id="requested-absent"),
        pytest.param({"selected_backend": None}, False, id="selected-absent"),
    ],
)
def test_ex_ante_backend_provider_truth_matrix(
    updates: dict[str, object], dto_accepts: bool
) -> None:
    context, inputs = _ex_ante_execution_context()
    payload = context.model_dump(mode="python")
    payload.update(updates)

    if not dto_accepts:
        with pytest.raises(ValidationError):
            MethodMetricExecutionContext.model_validate(payload)
        return

    changed_context = MethodMetricExecutionContext.model_validate(payload)
    result = _ex_ante_law(1.0, context=changed_context, inputs=inputs)

    assert changed_context.actual_backend is None or (
        changed_context.backend_identity_status == "reconciled"
        and changed_context.actual_backend == changed_context.selected_backend
    )
    assert result.status == "unavailable"
    assert result.value is None
    assert result.limitation == "ex_ante_execution_context_not_established"


@pytest.mark.parametrize(
    "context_updates",
    [
        pytest.param({"method_fqn": "policy.evaluation.other@1.0.0"}, id="fqn"),
        pytest.param({"method_version": "2.0.0"}, id="version"),
        pytest.param({"method_abi_digest": "b" * 64}, id="abi-digest"),
        pytest.param({"method_build_digest": "sha256:" + "0" * 64}, id="build-digest"),
        pytest.param({"method_build_digest_scope": "unavailable"}, id="build-scope"),
        pytest.param({"output_slot_id": "other"}, id="output-slot"),
        pytest.param({"output_value_path": ("median_change",)}, id="output-path"),
        pytest.param({"signature_output_slot_ids": ("other",)}, id="signature-output"),
    ],
)
def test_ex_ante_law_rejects_each_method_identity_rebinding(
    context_updates: dict[str, object],
) -> None:
    context, inputs = _ex_ante_execution_context()

    result = _ex_ante_law(1.0, context=context.model_copy(update=context_updates), inputs=inputs)

    assert result.status == "unavailable"
    assert result.limitation == "method_execution_binding_identity_mismatch"


def test_ex_ante_mean_change_rejects_integer_loss_before_float_conversion() -> None:
    context, inputs = _ex_ante_execution_context(
        baseline=(2**53 + 1,),
        scenario=(2**53 + 2,),
        dtype="<i8",
    )
    inexact = _ex_ante_law(2.0, context=context, inputs=inputs)

    exact_context, exact_inputs = _ex_ante_execution_context(
        baseline=(2**53,),
        scenario=(2**53 + 2,),
        dtype="<i8",
    )
    exactly_representable = _ex_ante_law(
        2.0,
        context=exact_context,
        inputs=exact_inputs,
    )

    assert inexact.status == "unavailable"
    assert inexact.limitation == "ex_ante_input_numeric_precision_not_established"
    assert exactly_representable.status == "available"
    assert exactly_representable.value == 2.0


@pytest.mark.parametrize(
    ("baseline", "scenario", "expected_limitation"),
    [
        ((), (), "ex_ante_paired_input_rows_not_established"),
        ((1.0, 2.0), (1.0,), "ex_ante_paired_input_rows_not_established"),
    ],
)
def test_ex_ante_mean_change_rejects_empty_or_unequal_input_shapes(
    baseline: tuple[float, ...],
    scenario: tuple[float, ...],
    expected_limitation: str,
) -> None:
    context, inputs = _ex_ante_execution_context(baseline=baseline, scenario=scenario)
    result = _ex_ante_law(0.0, context=context, inputs=inputs)

    assert result.status == "unavailable"
    assert result.limitation == expected_limitation


def test_ex_ante_mean_change_rejects_prestate_swap_and_input_content_swap() -> None:
    context, inputs = _ex_ante_execution_context()
    prestate_swap = _ex_ante_law(
        1.0,
        context=context,
        inputs=inputs,
        prestate_sha256="c" * 64,
    )
    changed_values = (
        inputs[0].model_copy(update={"values": (10.0, 20.0, 50.0)}),
        inputs[1],
    )
    changed_input = _ex_ante_law(1.0, context=context, inputs=changed_values)
    path_swap = _ex_ante_law(1.0, context=context, inputs=inputs, output_path=("median_change",))

    assert prestate_swap.status == "unavailable"
    assert prestate_swap.limitation == "ex_ante_input_capture_prestate_mismatch"
    assert changed_input.status == "unavailable"
    assert changed_input.limitation == "ex_ante_captured_input_content_digest_mismatch"
    assert path_swap.status == "unavailable"
    assert path_swap.limitation == "method_execution_binding_identity_mismatch"


def test_ex_ante_mean_change_refuses_inexact_integer_input_and_rehashed_capture() -> None:
    context, inputs = _ex_ante_execution_context(
        baseline=(0,),
        scenario=(2**53 + 1,),
        dtype="<i8",
    )
    tampered_values = inputs[0].model_copy(
        update={"values": (10.0, 20.0, 50.0), "value_sha256": inputs[0].value_sha256}
    )
    precision_result = _ex_ante_law(
        float(2**53),
        context=context,
        inputs=inputs,
    )
    digest_result = _ex_ante_law(1.0, context=context, inputs=(tampered_values, inputs[1]))

    assert precision_result.status == "unavailable"
    assert precision_result.limitation == "ex_ante_input_numeric_precision_not_established"
    assert digest_result.status == "unavailable"
    assert digest_result.limitation == "ex_ante_captured_input_content_digest_mismatch"
