#!/usr/bin/env python3
"""Heavy causal-discovery addendum for the MSME final experiment suite.

The v3 final suite intentionally kept discovery bounded. This addendum runs
package-backed discovery methods over frozen v3 inputs and derived panels:

- causal-learn PC, FCI, and GES;
- DAGMA linear DAG optimization;
- Tigramite PCMCI / PCMCI+ for temporal panels;
- optional DirectLiNGAM when the package is available.

The runner is designed for deadline-safe cloud execution: it writes every
method run as an independent artifact, appends a machine-readable run log, and
syncs progress to GCS after every batch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent import futures
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

import run_msme_final_fresg_suite as base
import run_msme_final_fresg_suite_v2 as v2


EXPERIMENT_ID = "msme_causal_discovery_addendum_20260501"
DEFAULT_SOURCE_WORKDIR = "/mnt/experiments/msme_final_fresg_evaluation_v3_20260501"
DEFAULT_WORKDIR = "/mnt/experiments/msme_causal_discovery_addendum_20260501"
DEFAULT_GCS_PREFIX = "gs://lex-1-494208-data/experiments/msme_causal_discovery_addendum_20260501"
TABULAR_PANELS = ("core_applicant_panel", "policy_world_panel")
TEMPORAL_PANELS = ("regional_temporal_panel",)
ALL_PANELS = TABULAR_PANELS + TEMPORAL_PANELS


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("")
        return 0
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_markdown(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], *, timeout: int = 3600, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=check)


def stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def standardize(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    mean = arr.mean(axis=0, keepdims=True)
    std = arr.std(axis=0, keepdims=True)
    return (arr - mean) / np.where(std < 1e-8, 1.0, std)


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30.0, 30.0)))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def latest_source_run(source_workdir: Path) -> Path:
    candidates = [p for p in source_workdir.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No source v3 run directories under {source_workdir}")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_jsonl_rows(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def policy_numeric_features(policies: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    features: dict[str, dict[str, float]] = {}
    for policy_id, policy in policies.items():
        levers = policy.get("levers", {}) if isinstance(policy.get("levers"), dict) else {}
        target = policy.get("target_population", {}) if isinstance(policy.get("target_population"), dict) else {}
        priority = target.get("priority_groups", {}) if isinstance(target.get("priority_groups"), dict) else {}
        features[policy_id] = {
            "grant_cap": safe_float(levers.get("grant_cap_uah")) / 300000.0,
            "loan_cap": safe_float(levers.get("loan_cap_uah")) / 1500000.0,
            "interest_subsidy": safe_float(levers.get("interest_subsidy_rate")),
            "tax_relief": safe_float(levers.get("tax_relief_rate")),
            "credit_guarantee": safe_float(levers.get("credit_guarantee_rate")),
            "procurement_preference": safe_float(levers.get("procurement_preference")),
            "energy_support": safe_float(levers.get("energy_support_rate")),
            "relocation_grant": safe_float(levers.get("relocation_grant_uah")) / 300000.0,
            "idp_priority": 1.0 if priority.get("idp") else 0.0,
            "women_priority": 1.0 if priority.get("women_owned") else 0.0,
            "veteran_priority": 1.0 if priority.get("veteran") else 0.0,
            "frontline_priority": 1.0 if str(target.get("region_priority", "")).lower() == "frontline" else 0.0,
        }
    return features


def build_core_applicant_panel(rows: int, seed: int) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    data = v2.generate_dgp("heterogeneous_effects", rows, seed)
    rng = np.random.default_rng(seed + 17)
    x = data.x
    conflict = x[:, 0] + 0.45 * data.stratum + rng.normal(0, 0.12, rows)
    credit_access = -x[:, 1] + 0.25 * x[:, 2] - 0.35 * conflict + rng.normal(0, 0.10, rows)
    digital = x[:, 2] + 0.15 * credit_access + rng.normal(0, 0.08, rows)
    collateral = x[:, 3] + 0.18 * credit_access + rng.normal(0, 0.10, rows)
    admin_capacity = x[:, 4] - 0.18 * conflict + rng.normal(0, 0.08, rows)
    baseline_productivity = x[:, 5] + 0.25 * digital + 0.20 * collateral + rng.normal(0, 0.12, rows)
    sector_pressure = (data.sector.astype(float) - np.mean(data.sector)) / max(1.0, float(np.std(data.sector)))
    treatment = data.treatment.astype(float)
    grant_intensity = np.clip(0.15 + 0.45 * treatment + 0.20 * data.propensity + rng.normal(0, 0.08, rows), 0, 1)
    governance_risk = sigmoid(0.35 * conflict - 0.25 * admin_capacity + 0.20 * sector_pressure + rng.normal(0, 0.20, rows))
    survival_24m = sigmoid(0.55 * data.outcome + 0.30 * grant_intensity - 0.25 * conflict + 0.15 * admin_capacity)
    employment_growth = data.outcome + 0.18 * survival_24m + rng.normal(0, 0.08, rows)
    names = [
        "conflict_exposure",
        "credit_access",
        "digital_readiness",
        "collateral_strength",
        "admin_capacity",
        "baseline_productivity",
        "sector_pressure",
        "program_treatment",
        "grant_intensity",
        "governance_risk",
        "survival_24m",
        "employment_growth",
    ]
    matrix = np.column_stack(
        [
            conflict,
            credit_access,
            digital,
            collateral,
            admin_capacity,
            baseline_productivity,
            sector_pressure,
            treatment,
            grant_intensity,
            governance_risk,
            survival_24m,
            employment_growth,
        ]
    )
    meta = {
        "rows": rows,
        "source": "v2.generate_dgp('heterogeneous_effects') plus policy-relevant derived variables",
        "credibility": "semi_synthetic_known_mechanism_panel",
    }
    return standardize(matrix), names, meta


def build_policy_world_panel(source_run: Path, max_rows: int, seed: int) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    outcome_path = source_run / "07_robust_policy_tournament" / "policy_world_outcomes.csv"
    world_path = source_run / "07_robust_policy_tournament" / "world_design_matrix.csv"
    policy_path = source_run / "03_policy_formalization" / "normalized_policy_designs.jsonl"
    outcomes = load_csv_rows(outcome_path)
    worlds = {row["world_id"]: row for row in load_csv_rows(world_path)}
    policies = {row["policy_id"]: row for row in load_jsonl_rows(policy_path)}
    policy_features = policy_numeric_features(policies)
    rng = np.random.default_rng(seed + 31)
    if len(outcomes) > max_rows:
        indices = rng.choice(len(outcomes), size=max_rows, replace=False)
        outcomes = [outcomes[int(i)] for i in indices]
    names = [
        "conflict_intensity",
        "credit_crunch",
        "energy_disruption",
        "fiscal_scarcity",
        "administrative_capacity",
        "fraud_pressure",
        "grant_cap",
        "loan_cap",
        "interest_subsidy",
        "tax_relief",
        "credit_guarantee",
        "procurement_preference",
        "frontline_priority",
        "idp_priority",
        "evidence_strength",
        "transport_score",
        "fraud_risk",
        "fairness",
        "survival",
        "employment",
        "utility",
    ]
    rows: list[list[float]] = []
    for row in outcomes:
        world = worlds.get(row.get("world_id", ""), {})
        feats = policy_features.get(row.get("policy_id", ""), {})
        rows.append(
            [
                safe_float(world.get("conflict_intensity")),
                safe_float(world.get("credit_crunch")),
                safe_float(world.get("energy_disruption")),
                safe_float(world.get("fiscal_scarcity")),
                safe_float(world.get("administrative_capacity")),
                safe_float(world.get("fraud_pressure")),
                feats.get("grant_cap", 0.0),
                feats.get("loan_cap", 0.0),
                feats.get("interest_subsidy", 0.0),
                feats.get("tax_relief", 0.0),
                feats.get("credit_guarantee", 0.0),
                feats.get("procurement_preference", 0.0),
                feats.get("frontline_priority", 0.0),
                feats.get("idp_priority", 0.0),
                safe_float(row.get("evidence_strength")),
                safe_float(row.get("transport_score")),
                safe_float(row.get("fraud_risk")),
                safe_float(row.get("fairness")),
                safe_float(row.get("survival")),
                safe_float(row.get("employment")),
                safe_float(row.get("utility")),
            ]
        )
    meta = {
        "rows": len(rows),
        "source": str(outcome_path),
        "credibility": "final_v3_policy_world_panel",
    }
    return standardize(np.asarray(rows, dtype=float)), names, meta


def build_regional_temporal_panel(periods: int, seed: int) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    rng = np.random.default_rng(seed + 53)
    regions = ["Kyiv", "Lviv", "Kharkiv", "Dnipro", "Odesa", "Zaporizhzhia", "Donetsk", "Kherson"]
    names = [
        "conflict_intensity",
        "regional_displacement",
        "energy_disruption",
        "credit_crunch",
        "program_intensity",
        "administrative_capacity",
        "survival_proxy",
        "employment_proxy",
    ]
    rows = []
    region_index = []
    for ridx, region in enumerate(regions):
        conflict = 0.18 + 0.10 * ridx / max(1, len(regions) - 1)
        displacement = 0.12 + 0.03 * ridx
        energy = 0.25 + 0.02 * ridx
        credit = 0.35
        program = 0.20
        admin = 0.60 - 0.02 * ridx
        survival = 0.50
        employment = 0.40
        for month in range(periods):
            shock = rng.normal(0, 0.035)
            seasonal = math.sin(month / 12.0 * 2 * math.pi)
            conflict = np.clip(0.70 * conflict + 0.08 * seasonal + 0.12 * (ridx >= 5) + shock, 0, 1)
            displacement = np.clip(0.65 * displacement + 0.25 * conflict + rng.normal(0, 0.025), 0, 1)
            energy = np.clip(0.62 * energy + 0.18 * conflict + rng.normal(0, 0.03), 0, 1)
            credit = np.clip(0.58 * credit + 0.16 * energy + 0.12 * conflict - 0.05 * admin + rng.normal(0, 0.025), 0, 1)
            program = np.clip(0.55 * program + 0.18 * displacement + 0.10 * credit + rng.normal(0, 0.025), 0, 1)
            admin = np.clip(0.72 * admin - 0.10 * conflict + 0.04 * program + rng.normal(0, 0.02), 0, 1)
            survival = np.clip(0.60 * survival + 0.16 * program + 0.10 * admin - 0.20 * conflict - 0.12 * credit + rng.normal(0, 0.025), 0, 1)
            employment = np.clip(0.58 * employment + 0.20 * survival + 0.10 * program - 0.12 * energy - 0.10 * credit + rng.normal(0, 0.025), 0, 1)
            rows.append([conflict, displacement, energy, credit, program, admin, survival, employment])
            region_index.append({"region": region, "region_index": ridx, "month": month})
    meta = {
        "rows": len(rows),
        "regions": regions,
        "periods_per_region": periods,
        "source": "deterministic regional-month panel calibrated to v3 scenario variables",
        "credibility": "semi_synthetic_temporal_panel",
    }
    return standardize(np.asarray(rows, dtype=float)), names, {**meta, "region_index": region_index}


def save_panel(path: Path, matrix: np.ndarray, names: list[str], meta: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    np.savez_compressed(path, matrix=np.asarray(matrix, dtype=float), names=np.asarray(names, dtype=object), meta=json.dumps(meta, ensure_ascii=False))


def load_panel(path: str | Path) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    loaded = np.load(path, allow_pickle=True)
    names = [str(x) for x in loaded["names"].tolist()]
    meta = json.loads(str(loaded["meta"].tolist()))
    return np.asarray(loaded["matrix"], dtype=float), names, meta


def _sample_rows(matrix: np.ndarray, n: int, seed: int) -> np.ndarray:
    if matrix.shape[0] <= n:
        return matrix
    rng = np.random.default_rng(seed)
    idx = rng.choice(matrix.shape[0], size=n, replace=False)
    return matrix[idx]


def _edge_from_matrix(matrix: np.ndarray, names: list[str], *, min_abs: float = 1e-12) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    p = len(names)
    for i in range(p):
        for j in range(i + 1, p):
            a = float(matrix[i, j])
            b = float(matrix[j, i])
            if abs(a) <= min_abs and abs(b) <= min_abs:
                continue
            if a == 0 and b != 0:
                src, dst = names[j], names[i]
                orientation = "single_endpoint_j_to_i"
            elif b == 0 and a != 0:
                src, dst = names[i], names[j]
                orientation = "single_endpoint_i_to_j"
            elif a == -1 and b == 1:
                src, dst = names[i], names[j]
                orientation = "directed_i_to_j"
            elif a == 1 and b == -1:
                src, dst = names[j], names[i]
                orientation = "directed_j_to_i"
            elif a == -1 and b == -1:
                src, dst = names[i], names[j]
                orientation = "undirected_or_cpdag"
            elif a == 1 and b == 1:
                src, dst = names[i], names[j]
                orientation = "bidirected_or_pag"
            else:
                src, dst = names[i], names[j]
                orientation = "partially_oriented_or_unknown"
            edges.append(
                {
                    "source": src,
                    "target": dst,
                    "node_a": names[i],
                    "node_b": names[j],
                    "matrix_ab": a,
                    "matrix_ba": b,
                    "orientation": orientation,
                    "lag": 0,
                    "weight": 1.0,
                }
            )
    return edges


def _edge_objects(graph: Any) -> list[str]:
    try:
        return [str(edge) for edge in graph.get_graph_edges()]
    except Exception:
        return []


def run_pc(data: np.ndarray, names: list[str], params: dict[str, Any]) -> dict[str, Any]:
    from causallearn.search.ConstraintBased.PC import pc

    graph = pc(
        data,
        alpha=float(params["alpha"]),
        indep_test=str(params.get("indep_test", "fisherz")),
        stable=True,
        uc_rule=int(params.get("uc_rule", 0)),
        uc_priority=int(params.get("uc_priority", 2)),
        show_progress=False,
        verbose=False,
        node_names=names,
    )
    matrix = np.asarray(graph.G.graph, dtype=float)
    return {"edges": _edge_from_matrix(matrix, names), "raw_edges": _edge_objects(graph.G), "matrix": matrix.tolist()}


def run_fci(data: np.ndarray, names: list[str], params: dict[str, Any]) -> dict[str, Any]:
    from causallearn.search.ConstraintBased.FCI import fci

    graph, raw_edges = fci(
        data,
        independence_test_method=str(params.get("indep_test", "fisherz")),
        alpha=float(params["alpha"]),
        depth=int(params.get("depth", 3)),
        max_path_length=int(params.get("max_path_length", 4)),
        show_progress=False,
        verbose=False,
        node_names=names,
    )
    matrix = np.asarray(graph.graph, dtype=float)
    return {"edges": _edge_from_matrix(matrix, names), "raw_edges": [str(edge) for edge in raw_edges], "matrix": matrix.tolist()}


def run_ges(data: np.ndarray, names: list[str], params: dict[str, Any]) -> dict[str, Any]:
    from causallearn.search.ScoreBased.GES import ges

    result = ges(
        data,
        score_func=str(params.get("score_func", "local_score_BIC")),
        maxP=int(params.get("max_parents", 4)),
        node_names=names,
    )
    graph = result["G"]
    matrix = np.asarray(graph.graph, dtype=float)
    return {
        "edges": _edge_from_matrix(matrix, names),
        "raw_edges": _edge_objects(graph),
        "matrix": matrix.tolist(),
        "score": safe_float(result.get("score")),
    }


def run_dagma(data: np.ndarray, names: list[str], params: dict[str, Any]) -> dict[str, Any]:
    from dagma.linear import DagmaLinear

    model = DagmaLinear(loss_type="l2", verbose=False)
    weights = model.fit(
        data,
        lambda1=float(params.get("lambda1", 0.04)),
        w_threshold=float(params.get("weight_threshold", 0.18)),
        T=int(params.get("T", 4)),
        warm_iter=int(params.get("warm_iter", 1200)),
        max_iter=int(params.get("max_iter", 2600)),
        lr=float(params.get("lr", 0.0003)),
    )
    weights = np.asarray(weights, dtype=float)
    threshold = float(params.get("weight_threshold", 0.18))
    edges: list[dict[str, Any]] = []
    for i, src in enumerate(names):
        for j, dst in enumerate(names):
            if i == j:
                continue
            weight = float(weights[i, j])
            if abs(weight) >= threshold:
                edges.append(
                    {
                        "source": src,
                        "target": dst,
                        "node_a": src,
                        "node_b": dst,
                        "orientation": "directed_weighted_dag",
                        "lag": 0,
                        "weight": weight,
                    }
                )
    return {"edges": edges, "raw_edges": [f"{e['source']}->{e['target']}:{e['weight']:.4f}" for e in edges], "matrix": weights.tolist()}


def run_lingam(data: np.ndarray, names: list[str], params: dict[str, Any]) -> dict[str, Any]:
    from lingam import DirectLiNGAM

    model = DirectLiNGAM(random_state=int(params.get("seed", 0)))
    model.fit(data)
    adjacency = np.asarray(model.adjacency_matrix_, dtype=float)
    threshold = float(params.get("weight_threshold", 0.08))
    edges: list[dict[str, Any]] = []
    for target_idx, target in enumerate(names):
        for source_idx, source in enumerate(names):
            if source_idx == target_idx:
                continue
            weight = float(adjacency[target_idx, source_idx])
            if abs(weight) >= threshold:
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "node_a": source,
                        "node_b": target,
                        "orientation": "directed_lingam",
                        "lag": 0,
                        "weight": weight,
                    }
                )
    return {"edges": edges, "raw_edges": [f"{e['source']}->{e['target']}:{e['weight']:.4f}" for e in edges], "matrix": adjacency.tolist()}


def run_pcmci(data: np.ndarray, names: list[str], params: dict[str, Any]) -> dict[str, Any]:
    from tigramite import data_processing as pp
    from tigramite.independence_tests.parcorr import ParCorr
    from tigramite.pcmci import PCMCI

    dataframe = pp.DataFrame(data, var_names=names)
    pcmci = PCMCI(dataframe=dataframe, cond_ind_test=ParCorr(significance="analytic"), verbosity=0)
    tau_max = int(params.get("tau_max", 3))
    alpha = float(params.get("alpha", 0.05))
    if params.get("variant") == "pcmci_plus":
        result = pcmci.run_pcmciplus(tau_min=0, tau_max=tau_max, pc_alpha=alpha)
    else:
        result = pcmci.run_pcmci(tau_min=1, tau_max=tau_max, pc_alpha=alpha, alpha_level=alpha)
    p_matrix = np.asarray(result.get("p_matrix"), dtype=float)
    val_matrix = np.asarray(result.get("val_matrix"), dtype=float)
    edges: list[dict[str, Any]] = []
    for target_idx, target in enumerate(names):
        for source_idx, source in enumerate(names):
            for lag in range(1, min(tau_max + 1, p_matrix.shape[2])):
                p_value = float(p_matrix[target_idx, source_idx, lag])
                value = float(val_matrix[target_idx, source_idx, lag])
                if np.isfinite(p_value) and p_value <= alpha and abs(value) >= float(params.get("min_abs_val", 0.02)):
                    edges.append(
                        {
                            "source": source,
                            "target": target,
                            "node_a": source,
                            "node_b": target,
                            "orientation": "lagged_directed",
                            "lag": lag,
                            "weight": value,
                            "p_value": p_value,
                        }
                    )
    return {"edges": edges, "raw_edges": [f"{e['source']}(t-{e['lag']})->{e['target']}:{e.get('p_value', 1):.4g}" for e in edges]}


def run_one_task(task: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    method = task["method"]
    panel_path = task["panel_path"]
    matrix, names, panel_meta = load_panel(panel_path)
    data = matrix
    if task.get("temporal_block") != "full":
        data = _sample_rows(data, int(task["sample_rows"]), int(task["seed"]))
        # Some policy-design levers are intentionally collinear or nearly
        # discrete. Fisher-Z based discovery needs an invertible correlation
        # matrix, so add deterministic numerical jitter without changing
        # substantive scale or edge stability.
        rng = np.random.default_rng(int(task["seed"]) + 991)
        data = data + rng.normal(0.0, 1e-5, size=data.shape)
    params = dict(task.get("params", {}))
    params["seed"] = int(task["seed"])
    try:
        if method == "pc":
            payload = run_pc(data, names, params)
        elif method == "fci":
            payload = run_fci(data, names, params)
        elif method == "ges":
            payload = run_ges(data, names, params)
        elif method == "dagma":
            payload = run_dagma(data, names, params)
        elif method == "lingam":
            payload = run_lingam(data, names, params)
        elif method == "pcmci":
            payload = run_pcmci(data, names, params)
        else:
            raise ValueError(f"unknown method {method}")
        status = "completed"
        error = None
    except Exception as exc:
        payload = {"edges": [], "raw_edges": []}
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
    runtime = float(time.perf_counter() - started)
    edges = payload.get("edges", [])
    return {
        "task_id": task["task_id"],
        "panel_id": task["panel_id"],
        "method": method,
        "bootstrap_id": task["bootstrap_id"],
        "seed": int(task["seed"]),
        "params": params,
        "sample_rows": int(data.shape[0]),
        "nodes": names,
        "panel_meta": {k: v for k, v in panel_meta.items() if k != "region_index"},
        "status": status,
        "error": error,
        "runtime_seconds": runtime,
        "edge_count": len(edges),
        "edges": edges,
        "raw_edges": payload.get("raw_edges", []),
        "matrix": payload.get("matrix"),
        "score": payload.get("score"),
        "finished_at": utc_now(),
    }


@dataclass(frozen=True)
class DiscoveryConfig:
    pc_reps_per_panel: int
    fci_reps_per_panel: int
    ges_reps_per_panel: int
    dagma_reps_per_panel: int
    pcmci_reps: int
    lingam_reps_per_panel: int


def config_for_mode(mode: str) -> DiscoveryConfig:
    if mode == "smoke":
        return DiscoveryConfig(2, 1, 1, 1, 2, 0)
    if mode == "balanced":
        return DiscoveryConfig(72, 36, 48, 24, 72, 12)
    return DiscoveryConfig(120, 72, 96, 48, 144, 24)


def make_tasks(ctx: dict[str, Any], panel_paths: dict[str, Path], cfg: DiscoveryConfig, include_lingam: bool) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seed_base = int(ctx["seed"])
    sample_rows = int(ctx["sample_rows"])
    dagma_rows = int(ctx["dagma_sample_rows"])
    pc_alpha = [0.005, 0.01, 0.025, 0.05]
    fci_alpha = [0.005, 0.01, 0.025]
    dagma_grid = [
        {"lambda1": 0.02, "weight_threshold": 0.14, "warm_iter": 1400, "max_iter": 2800},
        {"lambda1": 0.04, "weight_threshold": 0.18, "warm_iter": 1600, "max_iter": 3200},
        {"lambda1": 0.08, "weight_threshold": 0.22, "warm_iter": 1800, "max_iter": 3600},
    ]
    pcmci_grid = [
        {"variant": "pcmci", "tau_max": 1, "alpha": 0.01},
        {"variant": "pcmci", "tau_max": 3, "alpha": 0.05},
        {"variant": "pcmci_plus", "tau_max": 3, "alpha": 0.05},
        {"variant": "pcmci", "tau_max": 6, "alpha": 0.10},
    ]
    for panel_id in TABULAR_PANELS:
        for i in range(cfg.pc_reps_per_panel):
            alpha = pc_alpha[i % len(pc_alpha)]
            tasks.append(
                {
                    "task_id": f"{panel_id}_pc_{i:04d}",
                    "panel_id": panel_id,
                    "panel_path": str(panel_paths[panel_id]),
                    "method": "pc",
                    "bootstrap_id": i,
                    "seed": stable_seed(seed_base, panel_id, "pc", i),
                    "sample_rows": sample_rows,
                    "params": {"alpha": alpha, "indep_test": "fisherz"},
                }
            )
        for i in range(cfg.fci_reps_per_panel):
            alpha = fci_alpha[i % len(fci_alpha)]
            tasks.append(
                {
                    "task_id": f"{panel_id}_fci_{i:04d}",
                    "panel_id": panel_id,
                    "panel_path": str(panel_paths[panel_id]),
                    "method": "fci",
                    "bootstrap_id": i,
                    "seed": stable_seed(seed_base, panel_id, "fci", i),
                    "sample_rows": int(sample_rows * 0.75),
                    "params": {"alpha": alpha, "depth": 3, "max_path_length": 4, "indep_test": "fisherz"},
                }
            )
        for i in range(cfg.ges_reps_per_panel):
            tasks.append(
                {
                    "task_id": f"{panel_id}_ges_{i:04d}",
                    "panel_id": panel_id,
                    "panel_path": str(panel_paths[panel_id]),
                    "method": "ges",
                    "bootstrap_id": i,
                    "seed": stable_seed(seed_base, panel_id, "ges", i),
                    "sample_rows": sample_rows,
                    "params": {"score_func": "local_score_BIC", "max_parents": 4},
                }
            )
        for i in range(cfg.dagma_reps_per_panel):
            params = dagma_grid[i % len(dagma_grid)]
            tasks.append(
                {
                    "task_id": f"{panel_id}_dagma_{i:04d}",
                    "panel_id": panel_id,
                    "panel_path": str(panel_paths[panel_id]),
                    "method": "dagma",
                    "bootstrap_id": i,
                    "seed": stable_seed(seed_base, panel_id, "dagma", i),
                    "sample_rows": dagma_rows,
                    "params": params,
                }
            )
        if include_lingam:
            for i in range(cfg.lingam_reps_per_panel):
                tasks.append(
                    {
                        "task_id": f"{panel_id}_lingam_{i:04d}",
                        "panel_id": panel_id,
                        "panel_path": str(panel_paths[panel_id]),
                        "method": "lingam",
                        "bootstrap_id": i,
                        "seed": stable_seed(seed_base, panel_id, "lingam", i),
                        "sample_rows": sample_rows,
                        "params": {"weight_threshold": 0.08},
                    }
                )
    for i in range(cfg.pcmci_reps):
        params = pcmci_grid[i % len(pcmci_grid)]
        tasks.append(
            {
                "task_id": f"regional_temporal_panel_pcmci_{i:04d}",
                "panel_id": "regional_temporal_panel",
                "panel_path": str(panel_paths["regional_temporal_panel"]),
                "method": "pcmci",
                "bootstrap_id": i,
                "seed": stable_seed(seed_base, "regional_temporal_panel", "pcmci", i),
                "sample_rows": 10_000,
                "temporal_block": "full",
                "params": params,
            }
        )
    method_priority = {"pc": 0, "fci": 1, "ges": 2, "dagma": 3, "pcmci": 4, "lingam": 5}
    tasks.sort(key=lambda task: (task["bootstrap_id"], method_priority.get(task["method"], 99), task["panel_id"]))
    return tasks


def build_panels(ctx: dict[str, Any]) -> dict[str, Path]:
    panels_dir = ensure_dir(ctx["output_dir"] / "panels")
    source_run = Path(ctx["source_run"])
    core, core_names, core_meta = build_core_applicant_panel(int(ctx["core_rows"]), int(ctx["seed"]))
    policy, policy_names, policy_meta = build_policy_world_panel(source_run, int(ctx["policy_world_rows"]), int(ctx["seed"]))
    temporal, temporal_names, temporal_meta = build_regional_temporal_panel(int(ctx["temporal_periods"]), int(ctx["seed"]))
    panel_data = {
        "core_applicant_panel": (core, core_names, core_meta),
        "policy_world_panel": (policy, policy_names, policy_meta),
        "regional_temporal_panel": (temporal, temporal_names, temporal_meta),
    }
    paths: dict[str, Path] = {}
    manifest_rows: list[dict[str, Any]] = []
    for panel_id, (matrix, names, meta) in panel_data.items():
        path = panels_dir / f"{panel_id}.npz"
        save_panel(path, matrix, names, meta)
        paths[panel_id] = path
        manifest_rows.append(
            {
                "panel_id": panel_id,
                "path": str(path),
                "rows": int(matrix.shape[0]),
                "variables": int(matrix.shape[1]),
                "variable_names": names,
                **{k: v for k, v in meta.items() if k != "region_index"},
            }
        )
    write_json(ctx["output_dir"] / "panel_manifest.json", {"panels": manifest_rows, "created_at": utc_now()})
    write_csv(ctx["output_dir"] / "panel_manifest.csv", manifest_rows)
    return paths


def sync_output(ctx: dict[str, Any]) -> None:
    if not ctx.get("sync_enabled", True):
        return
    try:
        run_cmd(["gcloud", "storage", "rsync", "-r", str(ctx["output_dir"]), str(ctx["gcs_prefix"])], timeout=3600, check=False)
    except Exception:
        pass


def result_path(ctx: dict[str, Any], result: dict[str, Any]) -> Path:
    panel = result["panel_id"]
    method = result["method"]
    task_id = result["task_id"]
    return ctx["output_dir"] / "method_runs" / panel / method / f"{task_id}.json"


def persist_result(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    write_json(result_path(ctx, result), result)
    append_jsonl(
        ctx["output_dir"] / "_logs" / "algorithm_run_log.jsonl",
        {
            "task_id": result["task_id"],
            "panel_id": result["panel_id"],
            "method": result["method"],
            "bootstrap_id": result["bootstrap_id"],
            "status": result["status"],
            "runtime_seconds": result["runtime_seconds"],
            "edge_count": result["edge_count"],
            "sample_rows": result["sample_rows"],
            "error": result.get("error"),
            "finished_at": result.get("finished_at"),
            "params": result.get("params", {}),
        },
    )


def flatten_edges(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for edge in result.get("edges", []):
            rows.append(
                {
                    "task_id": result["task_id"],
                    "panel_id": result["panel_id"],
                    "method": result["method"],
                    "bootstrap_id": result["bootstrap_id"],
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "node_a": edge.get("node_a"),
                    "node_b": edge.get("node_b"),
                    "orientation": edge.get("orientation"),
                    "lag": edge.get("lag", 0),
                    "weight": edge.get("weight", 1.0),
                    "p_value": edge.get("p_value"),
                    "status": result["status"],
                }
            )
    return rows


def build_consensus(results: list[dict[str, Any]], out: Path) -> dict[str, Any]:
    completed = [r for r in results if r.get("status") == "completed"]
    by_panel_method: Counter[tuple[str, str]] = Counter((r["panel_id"], r["method"]) for r in completed)
    edge_counts: Counter[tuple[str, str, str, int, str]] = Counter()
    edge_weights: dict[tuple[str, str, str, int, str], list[float]] = defaultdict(list)
    orientation_counts: Counter[tuple[str, str, str, int, str, str]] = Counter()
    for result in completed:
        panel = result["panel_id"]
        method = result["method"]
        for edge in result.get("edges", []):
            src = str(edge.get("source"))
            dst = str(edge.get("target"))
            lag = int(edge.get("lag", 0) or 0)
            key = (panel, src, dst, lag, method)
            edge_counts[key] += 1
            edge_weights[key].append(abs(safe_float(edge.get("weight"), 1.0)))
            orientation_counts[(panel, src, dst, lag, method, str(edge.get("orientation", "unknown")))] += 1
    method_rows = []
    for (panel, src, dst, lag, method), count in sorted(edge_counts.items()):
        denom = max(1, by_panel_method.get((panel, method), 1))
        top_orientation = max(
            ((ori_key[-1], ori_count) for ori_key, ori_count in orientation_counts.items() if ori_key[:5] == (panel, src, dst, lag, method)),
            key=lambda item: item[1],
            default=("unknown", 0),
        )
        method_rows.append(
            {
                "panel_id": panel,
                "source": src,
                "target": dst,
                "lag": lag,
                "method": method,
                "support": count / denom,
                "count": count,
                "denominator": denom,
                "mean_abs_weight": float(np.mean(edge_weights[(panel, src, dst, lag, method)])),
                "dominant_orientation": top_orientation[0],
            }
        )
    write_csv(out / "edge_stability_by_method.csv", method_rows)
    consensus: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for row in method_rows:
        key = (row["panel_id"], row["source"], row["target"], int(row["lag"]))
        entry = consensus.setdefault(
            key,
            {
                "panel_id": row["panel_id"],
                "source": row["source"],
                "target": row["target"],
                "lag": int(row["lag"]),
                "methods_supporting": 0,
                "method_support_sum": 0.0,
                "max_method_support": 0.0,
                "mean_abs_weight": [],
                "methods": [],
            },
        )
        if row["support"] >= 0.20:
            entry["methods_supporting"] += 1
        entry["method_support_sum"] += float(row["support"])
        entry["max_method_support"] = max(float(entry["max_method_support"]), float(row["support"]))
        entry["mean_abs_weight"].append(float(row["mean_abs_weight"]))
        entry["methods"].append(row["method"])
    consensus_rows = []
    for entry in consensus.values():
        method_count = len(set(entry["methods"]))
        reliability = float(entry["method_support_sum"]) / max(1, method_count)
        verdict = "stable_consensus" if entry["methods_supporting"] >= 3 and reliability >= 0.35 else "method_specific_or_unstable"
        if entry["panel_id"] == "regional_temporal_panel" and entry["methods_supporting"] >= 1 and reliability >= 0.35:
            verdict = "stable_temporal_link"
        consensus_rows.append(
            {
                "panel_id": entry["panel_id"],
                "source": entry["source"],
                "target": entry["target"],
                "lag": entry["lag"],
                "methods_supporting": entry["methods_supporting"],
                "method_count": method_count,
                "mean_method_support": reliability,
                "max_method_support": entry["max_method_support"],
                "mean_abs_weight": float(np.mean(entry["mean_abs_weight"])) if entry["mean_abs_weight"] else 0.0,
                "verdict": verdict,
                "methods": ",".join(sorted(set(entry["methods"]))),
            }
        )
    consensus_rows.sort(key=lambda r: (r["panel_id"], -safe_float(r["mean_method_support"]), r["source"], r["target"]))
    write_csv(out / "consensus_edge_reliability.csv", consensus_rows)
    pag_edges = [r for r in consensus_rows if r["verdict"] in {"stable_consensus", "stable_temporal_link"}]
    write_json(
        out / "consensus_pag.json",
        {
            "created_at": utc_now(),
            "claim": "Discovery ensemble diagnostic, not a proof of a unique causal DAG.",
            "edges": pag_edges,
        },
    )
    write_json(
        out / "consensus_dag_projection.json",
        {
            "created_at": utc_now(),
            "claim": "DAG projection for downstream diagnostics only; uncertain/PAG edges are not treated as settled causal truth.",
            "edges": [
                {**edge, "projection_rule": "retain_stable_direction_or_temporal_lag"} for edge in pag_edges if edge["source"] != edge["target"]
            ],
        },
    )
    disagreement = []
    by_pair: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in method_rows:
        by_pair[(row["panel_id"], row["source"], row["target"], int(row["lag"]))].append(row)
    for key, rows in by_pair.items():
        supports = [safe_float(row["support"]) for row in rows]
        disagreement.append(
            {
                "panel_id": key[0],
                "source": key[1],
                "target": key[2],
                "lag": key[3],
                "support_range": max(supports) - min(supports) if supports else 0.0,
                "support_std": float(np.std(supports)) if supports else 0.0,
                "methods": ",".join(sorted({row["method"] for row in rows})),
            }
        )
    disagreement.sort(key=lambda r: -safe_float(r["support_range"]))
    write_csv(out / "discovery_disagreement_heatmap.csv", disagreement)
    latent = [
        {
            **row,
            "latent_confounding_reason": "FCI/PAG relation repeatedly appears but direction is not stable across methods.",
        }
        for row in consensus_rows
        if row["method_count"] >= 2 and row["methods_supporting"] >= 1 and "fci" in row["methods"] and row["verdict"] != "stable_consensus"
    ]
    write_csv(out / "latent_confounding_candidates.csv", latent[:500])
    return {
        "completed_runs": len(completed),
        "method_edge_rows": len(method_rows),
        "consensus_edges": len(consensus_rows),
        "stable_edges": len(pag_edges),
        "latent_candidates": len(latent),
    }


def write_summary(ctx: dict[str, Any], results: list[dict[str, Any]], consensus: dict[str, Any]) -> None:
    completed = [r for r in results if r.get("status") == "completed"]
    failed = [r for r in results if r.get("status") != "completed"]
    runtime = sum(float(r.get("runtime_seconds", 0.0)) for r in results)
    by_method = Counter(r["method"] for r in completed)
    by_panel = Counter(r["panel_id"] for r in completed)
    write_json(
        ctx["output_dir"] / "_manifests" / "discovery_addendum_result.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "run_id": ctx["run_id"],
            "source_run": str(ctx["source_run"]),
            "status": "completed_with_failures" if failed else "completed",
            "started_at": ctx["started_at"],
            "finished_at": utc_now(),
            "tasks_total": len(results),
            "tasks_completed": len(completed),
            "tasks_failed": len(failed),
            "sum_worker_runtime_seconds": runtime,
            "methods_completed": dict(sorted(by_method.items())),
            "panels_completed": dict(sorted(by_panel.items())),
            "consensus": consensus,
            "gcs_prefix": ctx["gcs_prefix"],
        },
    )
    rows = [
        {
            "method": method,
            "completed_runs": count,
            "failed_runs": sum(1 for r in failed if r["method"] == method),
            "mean_runtime_seconds": float(np.mean([r["runtime_seconds"] for r in results if r["method"] == method])) if any(r["method"] == method for r in results) else 0.0,
        }
        for method, count in sorted(by_method.items())
    ]
    write_csv(ctx["output_dir"] / "method_runtime_summary.csv", rows)
    write_markdown(
        ctx["output_dir"] / "discovery_addendum_summary.md",
        f"""
# MSME Causal Discovery Addendum

Run ID: `{ctx['run_id']}`.
Source v3 run: `{ctx['source_run']}`.

This addendum strengthens the final experiment with package-backed causal
discovery. It is a diagnostic and triangulation layer, not a claim that the
observational data uniquely identify a single true DAG.

Completed tasks: `{len(completed)}`.
Failed tasks: `{len(failed)}`.
Stable consensus edges: `{consensus.get('stable_edges')}`.
Latent-confounding candidates: `{consensus.get('latent_candidates')}`.

Methods used:

- PC, FCI, and GES from `causal-learn`;
- DAGMA from `dagma`;
- PCMCI / PCMCI+ from `tigramite`;
- DirectLiNGAM if available in the environment.

Primary artifacts:

- `consensus_pag.json`
- `consensus_dag_projection.json`
- `consensus_edge_reliability.csv`
- `edge_stability_by_method.csv`
- `discovery_disagreement_heatmap.csv`
- `latent_confounding_candidates.csv`
- `_logs/algorithm_run_log.jsonl`
""",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-workdir", default=DEFAULT_SOURCE_WORKDIR)
    parser.add_argument("--source-run-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--workdir", default=DEFAULT_WORKDIR)
    parser.add_argument("--gcs-prefix", default=DEFAULT_GCS_PREFIX)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--mode", choices=("smoke", "balanced", "max"), default="max")
    parser.add_argument("--hard-cap-hours", type=float, default=8.0)
    parser.add_argument("--core-rows", type=int, default=90_000)
    parser.add_argument("--policy-world-rows", type=int, default=40_000)
    parser.add_argument("--temporal-periods", type=int, default=96)
    parser.add_argument("--sample-rows", type=int, default=4_000)
    parser.add_argument("--dagma-sample-rows", type=int, default=2_500)
    parser.add_argument("--batch-size", type=int, default=48)
    parser.add_argument("--seed", type=int, default=20260501)
    parser.add_argument("--include-lingam", action="store_true")
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    source_workdir = Path(args.source_workdir)
    source_run = source_workdir / args.source_run_id if args.source_run_id else latest_source_run(source_workdir)
    run_id = args.run_id or f"{EXPERIMENT_ID}_{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    output_dir = ensure_dir(Path(args.workdir) / run_id)
    return {
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "source_workdir": str(source_workdir),
        "source_run": str(source_run),
        "output_dir": output_dir,
        "gcs_prefix": f"{args.gcs_prefix.rstrip('/')}/{run_id}",
        "threads": int(args.threads),
        "mode": args.mode,
        "hard_cap_hours": float(args.hard_cap_hours),
        "core_rows": int(args.core_rows),
        "policy_world_rows": int(args.policy_world_rows),
        "temporal_periods": int(args.temporal_periods),
        "sample_rows": int(args.sample_rows),
        "dagma_sample_rows": int(args.dagma_sample_rows),
        "batch_size": int(args.batch_size),
        "seed": int(args.seed),
        "include_lingam_requested": bool(args.include_lingam),
        "sync_enabled": not args.no_sync,
        "started_at": utc_now(),
    }


def package_inventory(include_lingam_requested: bool) -> dict[str, bool]:
    import importlib.util

    packages = {
        "causal_learn": importlib.util.find_spec("causallearn") is not None,
        "tigramite": importlib.util.find_spec("tigramite") is not None,
        "dagma": importlib.util.find_spec("dagma") is not None,
        "lingam": importlib.util.find_spec("lingam") is not None,
    }
    packages["include_lingam"] = include_lingam_requested and packages["lingam"]
    return packages


def main() -> int:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    args = parse_args()
    ctx = build_context(args)
    ensure_dir(ctx["output_dir"] / "_logs")
    ensure_dir(ctx["output_dir"] / "_manifests")
    packages = package_inventory(bool(ctx["include_lingam_requested"]))
    write_json(ctx["output_dir"] / "_manifests" / "effective_config.json", {k: str(v) if isinstance(v, Path) else v for k, v in ctx.items()})
    write_json(ctx["output_dir"] / "_manifests" / "package_inventory.json", packages)
    if not (packages["causal_learn"] and packages["tigramite"] and packages["dagma"]):
        write_json(ctx["output_dir"] / "failure.json", {"status": "failed_missing_required_packages", "packages": packages})
        print(json.dumps({"status": "failed_missing_required_packages", "packages": packages}, ensure_ascii=False))
        return 2

    panel_paths = build_panels(ctx)
    cfg = config_for_mode(str(ctx["mode"]))
    tasks = make_tasks(ctx, panel_paths, cfg, include_lingam=bool(packages["include_lingam"]))
    write_json(ctx["output_dir"] / "_manifests" / "task_manifest.json", {"tasks_total": len(tasks), "mode": ctx["mode"], "tasks": tasks})
    sync_output(ctx)

    started = time.perf_counter()
    completed_results: list[dict[str, Any]] = []
    max_workers = max(1, int(ctx["threads"]))
    batch_size = max(1, int(ctx["batch_size"]))
    stop_reason = "all_tasks_completed"
    for offset in range(0, len(tasks), batch_size):
        elapsed_hours = (time.perf_counter() - started) / 3600.0
        if elapsed_hours >= float(ctx["hard_cap_hours"]) * 0.94:
            stop_reason = "stopped_before_next_batch_due_to_hard_cap"
            break
        batch = tasks[offset : offset + batch_size]
        with futures.ProcessPoolExecutor(max_workers=min(max_workers, len(batch))) as pool:
            for result in pool.map(run_one_task, batch, chunksize=1):
                completed_results.append(result)
                persist_result(ctx, result)
        write_json(
            ctx["output_dir"] / "_manifests" / "progress.json",
            {
                "completed": len(completed_results),
                "tasks_total": len(tasks),
                "elapsed_hours": (time.perf_counter() - started) / 3600.0,
                "last_completed_at": utc_now(),
                "stop_reason": None,
            },
        )
        sync_output(ctx)

    edge_rows = flatten_edges(completed_results)
    write_csv(ctx["output_dir"] / "all_discovered_edges.csv", edge_rows)
    consensus = build_consensus(completed_results, ctx["output_dir"])
    write_json(
        ctx["output_dir"] / "_manifests" / "progress.json",
        {
            "completed": len(completed_results),
            "tasks_total": len(tasks),
            "elapsed_hours": (time.perf_counter() - started) / 3600.0,
            "last_completed_at": utc_now(),
            "stop_reason": stop_reason,
        },
    )
    write_summary(ctx, completed_results, consensus)
    sync_output(ctx)
    print(
        json.dumps(
            {
                "status": "completed",
                "run_id": ctx["run_id"],
                "tasks_completed": len(completed_results),
                "tasks_total": len(tasks),
                "stop_reason": stop_reason,
                "gcs_prefix": ctx["gcs_prefix"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
