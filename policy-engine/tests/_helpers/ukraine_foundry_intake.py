"""Reusable actual Ukraine stage fixture for CAN intake contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    RuntimeBundleManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId


def _write_ukraine_stage(
    root: Path,
    *,
    stage_id: StageId,
    outputs: dict[str, dict[str, object]],
) -> Path:
    stage_dir = root / "stages" / stage_id.value
    stage_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for name, payload in outputs.items():
        path = stage_dir / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        records.append(ArtifactRecord.from_path(path))
    manifest = BuildRunManifest(
        run_id="ukraine-intake-test",
        stage_id=stage_id,
        status="completed",
        started_at="2026-08-26T10:00:00+00:00",
        finished_at="2026-08-26T10:01:00+00:00",
        outputs=records,
    )
    manifest_path = root / "manifests" / f"build_{stage_id.value}.json"
    write_manifest(manifest_path, manifest)
    return manifest_path


def _ukraine_intake_manifests(
    root: Path,
    *,
    data_snapshot_ref: DataSnapshotRef | None = None,
    runtime_bundle_payload: dict[str, object] | None = None,
) -> dict[str, Path]:
    if runtime_bundle_payload is None:
        snapshot_id = (
            str(data_snapshot_ref.artifact_id)
            if data_snapshot_ref is not None
            else "sha256:" + ("1" * 64)
        )
        runtime_bundle_payload = RuntimeBundleManifest(
            data_snapshot_artifact_id=snapshot_id,
            data_snapshot_ref=data_snapshot_ref,
        ).model_dump(mode="json")
    adjacency = [[0.0, 1.0], [1.0, 0.0]]
    network = {
        "adjacency": adjacency,
        "node_features": [[0.1], [0.2]],
        "node_states": [0.1, 0.2],
        "node_ids": ["a", "b"],
        "metadata": {"producer_stage": "d1"},
    }
    network_causal = {
        "outcome": [1.0, 2.0],
        "treatment": [0, 1],
        "covariates": [[0.1], [0.2]],
        "adjacency_matrix": adjacency,
        "metadata": {"producer_stage": "d1"},
    }
    proxy_bundle = {
        "contract_target": {
            "contract_id": "foundry.causal.proxy_measurement_data.v1",
            "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
        },
        "proxy_channels": [
            {
                "family": "distress_enforcement",
                "proxy_variable": "C_star",
                "latent_variable": "C",
                "treatment_variable": "x",
                "outcome_variable": "y",
                "target_contract": {
                    "contract_id": "foundry.causal.proxy_measurement_data.v1",
                    "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                },
            }
        ],
        "proxy_map": {"C": "C_star"},
    }
    d1_outputs = {
        "proxy_identification_bundle_v1.json": proxy_bundle,
        "multiplex_network_data.json": {
            "adjacency_layers": [adjacency, adjacency],
            "node_features": [[0.1], [0.2]],
            "node_ids": ["a", "b"],
            "metadata": {"producer_stage": "d1"},
        },
    }
    for layer in ("trade", "distress", "public_service"):
        d1_outputs[f"{layer}_network_data.json"] = network
        d1_outputs[f"{layer}_network_causal_data.json"] = network_causal
    return {
        "d0_p0": _write_ukraine_stage(
            root,
            stage_id=StageId.D0_P0,
            outputs={"runtime_bundle_manifest.json": runtime_bundle_payload},
        ),
        "d1": _write_ukraine_stage(root, stage_id=StageId.D1, outputs=d1_outputs),
        "d2": _write_ukraine_stage(
            root,
            stage_id=StageId.D2,
            outputs={
                "panel_observational_contract.json": {
                    "outcome": [[1.0, 2.0], [2.0, 3.0]],
                    "treatment": [0, 1],
                    "time_treatment": 1,
                    "metadata": {"producer_stage": "d2"},
                },
                "dynamic_treatment_contract.json": {
                    "outcome": list(np.linspace(1.0, 2.0, 10)),
                    "treatment_sequence": [[0, 1]] * 10,
                    "covariate_sequence": [[[0.1], [0.2]]] * 10,
                    "metadata": {"producer_stage": "d2"},
                },
                "microsim_survey_contract_preview.json": {
                    "market_income": [100.0, 200.0],
                    "weights": [1.0, 1.0],
                    "metadata": {"producer_stage": "d2"},
                },
                "survival_contract.json": {
                    "features": [[0.1], [0.2]],
                    "durations": [1.0, 2.0],
                    "events": [0, 1],
                    "metadata": {"producer_stage": "d2"},
                },
                "panel_econometric_contract.json": {
                    "dependent": list(np.linspace(1.0, 8.0, 8)),
                    "exog": [[0.0], [1.0]] * 4,
                    "entity_ids": ["a", "a", "b", "b", "c", "c", "d", "d"],
                    "time_ids": [0, 1] * 4,
                    "metadata": {"producer_stage": "d2"},
                },
            },
        ),
        "d3": _write_ukraine_stage(
            root,
            stage_id=StageId.D3,
            outputs={
                "microsim_survey_contract_v1.json": {
                    "market_income": [100.0, 200.0],
                    "weights": [1.0, 1.0],
                    "metadata": {"producer_stage": "d3"},
                }
            },
        ),
    }
