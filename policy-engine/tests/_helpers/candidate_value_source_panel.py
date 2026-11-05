"""Controlled native source panel for candidate value-method route tests."""

from __future__ import annotations

import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore


def build_candidate_value_source_panel(
    tmp_path: Path,
    *,
    store: ArtifactStore,
    target_variable: str = "cells.distress_score",
) -> SimpleNamespace:
    """Build actual active source projections and a candidate AIPW request.

    The synthetic panel has 200 rows, four balanced treatment/covariate cells,
    ``usd`` outcome values within support ``[0, 16]``, and an exact fixture ATE
    of ``2``. The unit label is the canonical slot unit id. Active-source
    timestamps remain unestablished; the fixture grants no treatment-assignment,
    source-time, or production authority.

    Args:
        tmp_path: Test-owned parent for the source and companion artifacts.
        store: Runtime artifact store shared with the served route.
        target_variable: Candidate binary treatment variable identifier.

    Returns:
        A namespace containing the native source, selected and resolved Catalog
        source, canonical source projection request, and independent fixture
        oracle values.
    """
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator
    from polisyos.foundry.methods.causal import HTEObservationalData
    from polisyos.runtime.quality import (
        ValueOwnerSourceProjectionRequestV1,
        ValueOwnerSourceVariableProjectionV1,
    )
    from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        resolve_catalog_serving_source,
    )
    from tests._helpers.candidate_cycle_source_profile import _build_source_files
    from tests._helpers.generic_n4_served_replay import _declared_generic_component_knobs
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    if not isinstance(target_variable, str) or not target_variable.strip():
        raise ValueError("candidate_value_source_panel_treatment_variable_missing")

    source_root = tmp_path / "native-source"
    native_repo_root = source_root / "authority" / "repo"
    _build_source_files(
        native_repo_root,
        include_owner_slot_manifest=True,
        owner_knob_dictionary=_declared_generic_component_knobs("controlled_overlay"),
    )
    contract_target = {
        "contract_id": HTEObservationalData.contract_id,
        "contract_fqn": (f"{HTEObservationalData.__module__}.{HTEObservationalData.__qualname__}"),
    }
    observation_manifest = {
        "schema_version": "1.0",
        "artifact_name": "observation_to_contract_manifest.json",
        "routes": [
            {
                "family": "agents.income",
                "target_contract": contract_target,
                "notes": [
                    "Synthetic candidate method compatibility route only; no source or "
                    "assignment authority is established."
                ],
            }
        ],
        "artifacts": [
            {
                "artifact_name": "synthetic_candidate_hte_contract.json",
                "compiler_id": "test.synthetic_candidate_source_profile",
                "status": "compiled",
                "target_contract": contract_target,
                "notes": [
                    "Compiled candidate contract configuration only; no source or "
                    "assignment authority is established."
                ],
            }
        ],
    }
    manifest_path = default_l6_bundle_paths(native_repo_root)["observation_to_contract_manifest"]
    resolved_native_root = native_repo_root.resolve(strict=True)
    if not manifest_path.resolve(strict=False).is_relative_to(resolved_native_root):
        raise AssertionError("candidate_value_source_panel_manifest_escaped_native_root")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(observation_manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    source_rows: list[dict[str, object]] = []
    for covariate in (0, 1):
        for treatment in (0, 1):
            for _ in range(50):
                index = len(source_rows)
                outcome = 10 + 3 * covariate + treatment * (1 + 2 * covariate)
                source_rows.append(
                    {
                        "country_code": "UA",
                        "year": 1800 + index,
                        "income": float(outcome),
                        "treatment": float(treatment),
                        "baseline_covariate": float(covariate),
                        "condition_json": (
                            '{"fixture":"candidate_value_source_panel",'
                            '"time_role":"synthetic_index"}'
                        ),
                    }
                )

    cell_counts = Counter(
        (int(row["treatment"]), int(row["baseline_covariate"])) for row in source_rows
    )
    expected_cells = {(treatment, covariate): 50 for treatment in (0, 1) for covariate in (0, 1)}
    if len(source_rows) != 200 or cell_counts != expected_cells:
        raise AssertionError("candidate_value_source_panel_denominator_mismatch")

    variable_specs = (
        {
            "target_variable": "agents.income",
            "raw_field": "income",
            "raw_unit": "usd",
            "canonical_unit": "usd",
            "unit_transform": "identity",
            "unit_transform_ref": "fabric://units/usd-identity/v1",
            "valid_min": 0.0,
            "valid_max": 16.0,
        },
        {
            "target_variable": target_variable,
            "raw_field": "treatment",
            "raw_unit": "binary",
            "canonical_unit": "binary",
            "unit_transform": "identity",
            "unit_transform_ref": "fabric://units/binary-identity/v1",
            "valid_min": 0.0,
            "valid_max": 1.0,
        },
        {
            "target_variable": "baseline_covariate",
            "raw_field": "baseline_covariate",
            "raw_unit": "binary",
            "canonical_unit": "binary",
            "unit_transform": "identity",
            "unit_transform_ref": "fabric://units/binary-identity/v1",
            "valid_min": 0.0,
            "valid_max": 1.0,
        },
    )
    native_source = make_native_multivariable_active_projections(
        source_root,
        source_rows=source_rows,
        variable_specs=variable_specs,
        condition_units_by_raw_field={
            "income": "usd",
            "treatment": "binary",
            "baseline_covariate": "binary",
        },
        artifact_store=cast("FileSystemCAS", store),
    )
    if native_source.repo_root != native_repo_root:
        raise AssertionError("candidate_value_source_panel_companion_root_mismatch")
    projections = native_source.projections
    variable_ids = ("agents.income", target_variable, "baseline_covariate")
    for variable_id in variable_ids:
        projection = projections[variable_id]
        if (
            len(projection.observations) != 200
            or projection.source_time_status != "not_established"
        ):
            raise AssertionError("candidate_value_source_panel_projection_mismatch")

    selection = CatalogServingSourceSelection(
        snapshot_root=native_source.repo_root,
        database_relative_path=Path("catalog/catalog.duckdb"),
        catalog_run_profile="preflight_core",
    )
    catalog_source = resolve_catalog_serving_source(
        native_source.repo_root,
        selection=selection,
        requested_profile=selection.catalog_run_profile,
    )
    if catalog_source.database_path != native_source.baseline_path:
        raise AssertionError("candidate_value_source_panel_catalog_selection_mismatch")

    estimand_spec_json = json.dumps(
        {
            "query_id": "controlled-candidate-value-source-panel-ate-v1",
            "estimand_id": "ATE",
            "outcome": "agents.income",
            "treatment_or_exposure": target_variable,
            "covariates_or_conditioning": ["baseline_covariate"],
            "adjustment_set": ["baseline_covariate"],
            "population": "unspecified",
            "sample_filter": None,
            "time_horizon": None,
            "prediction_origin": None,
            "unit": "usd",
            "scale": "identity",
            "transform": None,
            "target_role": "estimate",
            "loss_or_utility_id": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    role_bindings = (
        ("outcome", "agents.income"),
        ("treatment", target_variable),
        ("covariate", "baseline_covariate"),
    )
    request = ValueOwnerSourceProjectionRequestV1(
        selected_method_fqn=AIPWEstimator.signature.fqn,
        estimand_spec_json=estimand_spec_json,
        variable_projections=tuple(
            ValueOwnerSourceVariableProjectionV1(
                role=role,
                variable_id=variable_id,
                projection_payload=projections[variable_id].model_dump(mode="json"),
            )
            for role, variable_id in role_bindings
        ),
        outcome_lower=0.0,
        outcome_upper=16.0,
        outcome_bounds_unit="usd",
        method_parameters_json=json.dumps(
            {
                "estimation_backend": "custom",
                "direct_model_type": "linear",
                "confidence_level": 0.95,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        seed=7,
    )

    cell_means = {
        (treatment, covariate): Fraction(
            sum(
                int(row["income"])
                for row in source_rows
                if row["treatment"] == treatment and row["baseline_covariate"] == covariate
            ),
            cell_counts[(treatment, covariate)],
        )
        for treatment in (0, 1)
        for covariate in (0, 1)
    }
    exact_ate = (
        sum(
            (cell_means[(1, covariate)] - cell_means[(0, covariate)] for covariate in (0, 1)),
            Fraction(),
        )
        / 2
    )
    treated_mean = sum((cell_means[(1, covariate)] for covariate in (0, 1)), Fraction()) / 2
    control_mean = sum((cell_means[(0, covariate)] for covariate in (0, 1)), Fraction()) / 2
    treatment_share = Fraction(1, 2)
    control_share = Fraction(1, 2)
    support_lower = Fraction(0)
    support_upper = Fraction(16)
    manski_lower = (
        treatment_share * treated_mean
        + control_share * support_lower
        - control_share * control_mean
        - treatment_share * support_upper
    )
    manski_upper = (
        treatment_share * treated_mean
        + control_share * support_upper
        - control_share * control_mean
        - treatment_share * support_lower
    )
    if (exact_ate, manski_lower, manski_upper) != (Fraction(2), Fraction(-7), Fraction(9)):
        raise AssertionError("candidate_value_source_panel_oracle_mismatch")

    return SimpleNamespace(
        source=native_source,
        selection=selection,
        catalog_source=catalog_source,
        request=request,
        source_rows=tuple(source_rows),
        cell_counts=dict(cell_counts),
        expected_ate=2.0,
        expected_bounds=(-7.0, 9.0),
        outcome_support=(0.0, 16.0),
    )
