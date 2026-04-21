from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.kernel_causal import (
    KernelEstimatorSpec,
    KernelEstimatorTemplate,
    KernelLoweringDisposition,
    KernelNuisanceSpec,
    KernelRegularization,
    KernelSpec,
    KernelTargetRepresentation,
    OperatorConvergenceGuarantee,
    OperatorEffectBundle,
    OperatorEstimatorFamily,
    OperatorProbeExport,
    load_kernel_estimator_spec,
    load_operator_effect_bundle,
    persist_kernel_estimator_spec,
    persist_operator_effect_bundle,
)


def _ready_spec() -> KernelEstimatorSpec:
    return KernelEstimatorSpec(
        estimand_hash="abc12345deadbeef",
        template=KernelEstimatorTemplate.BACKDOOR_CME,
        target_representation=KernelTargetRepresentation.MEAN_EMBEDDING,
        lowering_disposition=KernelLoweringDisposition.READY,
        output_kernel=KernelSpec(
            name="rbf",
            params={"bandwidth": "median_heuristic"},
            characteristic=True,
            weak_metrizing=True,
        ),
        regularization=KernelRegularization(),
        variable_roles={"treatment": ("T",), "outcome": ("Y",), "covariates": ("Z",)},
        required_side_conditions=("positivity", "consistency"),
        nuisance_plan=(
            KernelNuisanceSpec(
                role="cme_y_given_xz",
                method_hint="causal.kernel.nuisance.fit_cme_y_given_xz",
            ),
        ),
        diagnostics_plan=("kernel_semantics", "regularization_stability"),
    )


def test_kernel_estimator_spec_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    spec = _ready_spec()

    ref = persist_kernel_estimator_spec(store, spec)
    loaded = load_kernel_estimator_spec(store, ref)

    assert loaded == spec
    assert ref.kind == "ir.kernel_estimator_spec"


def test_kernel_estimator_spec_rejects_ready_with_blocking_reasons() -> None:
    with pytest.raises(ValueError, match="ready kernel lowering"):
        KernelEstimatorSpec.model_validate(
            _ready_spec().model_copy(
                update={"blocking_reasons": ("operator_certificate_missing",)}
            ).model_dump(mode="json")
        )


def test_kernel_estimator_spec_requires_reason_for_blocked_disposition() -> None:
    with pytest.raises(ValueError, match="must explain blocking_reasons"):
        KernelEstimatorSpec.model_validate(
            _ready_spec().model_copy(
                update={"lowering_disposition": KernelLoweringDisposition.PROOF_ONLY}
            ).model_dump(mode="json")
        )


def test_distributional_spec_requires_characteristic_or_downgrade() -> None:
    with pytest.raises(ValueError, match="requires characteristic output_kernel"):
        KernelEstimatorSpec.model_validate(
            _ready_spec().model_copy(
                update={
                    "output_kernel": KernelSpec(
                        name="linear",
                        params={},
                        characteristic=False,
                        weak_metrizing=False,
                    )
                }
            ).model_dump(mode="json")
        )


def test_operator_effect_bundle_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = OperatorEffectBundle(
        operator_ref="operator:cme_krr:deadbeefcafefeed",
        estimand_hash="deadbeefcafefeed",
        probe_space_ref="hy",
        codomain_space_ref="hv",
        estimator_family=OperatorEstimatorFamily.CME_KRR,
        regularization=KernelRegularization(lambda_value=0.1),
        probe_basis=("coord_0", "coord_1"),
        codomain_axis=("v_0", "v_1"),
        operator_matrix=((0.1, 0.2), (0.05, -0.1)),
        operator_norm_error_bound=0.25,
        convergence_guarantee=OperatorConvergenceGuarantee(
            guarantee_type="induced_operator",
            norm_kind="hy_to_l2_pv",
            rate_symbol="r_n",
        ),
        applied_probe_exports=(
            OperatorProbeExport(
                probe_ref="coord_0",
                codomain_axis=("v_0", "v_1"),
                values=(0.1, 0.05),
            ),
            OperatorProbeExport(
                probe_ref="coord_1",
                codomain_axis=("v_0", "v_1"),
                values=(0.2, -0.1),
            ),
        ),
    )

    ref = persist_operator_effect_bundle(store, bundle)
    loaded = load_operator_effect_bundle(store, ref)

    assert loaded == bundle
    assert ref.kind == "ir.operator_effect_bundle"


def test_operator_effect_bundle_rejects_matrix_without_axes() -> None:
    with pytest.raises(ValueError, match="requires codomain_axis"):
        OperatorEffectBundle.model_validate(
            {
                "operator_ref": "operator:test",
                "estimand_hash": "deadbeef",
                "probe_space_ref": "hy",
                "codomain_space_ref": "hv",
                "estimator_family": "cme_krr",
                "probe_basis": ["coord_0"],
                "operator_matrix": [[0.1]],
            }
        )


def test_operator_effect_bundle_requires_unique_probe_exports() -> None:
    with pytest.raises(ValueError, match="unique probe_ref"):
        OperatorEffectBundle.model_validate(
            {
                "operator_ref": "operator:test",
                "estimand_hash": "deadbeef",
                "probe_space_ref": "hy",
                "codomain_space_ref": "hv",
                "estimator_family": "cme_krr",
                "probe_basis": ["coord_0"],
                "codomain_axis": ["v_0"],
                "operator_matrix": [[0.1]],
                "applied_probe_exports": [
                    {"probe_ref": "coord_0", "codomain_axis": ["v_0"], "values": [0.1]},
                    {"probe_ref": "coord_0", "codomain_axis": ["v_0"], "values": [0.1]},
                ],
            }
        )
