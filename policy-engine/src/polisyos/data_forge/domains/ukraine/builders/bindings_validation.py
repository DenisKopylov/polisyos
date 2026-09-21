"""Binding-resolution diagnostics and synthetic validation payloads."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from .common import (
    _coerce_string_series,
    _ensure_agent_numeric_columns,
    _sanitize_numeric_series,
)
from .io import _read_parquet_frame

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.data_forge.domains.ukraine.models import BuildRootConfig
    from polisyos.ir.observation.contracts import ObservationFamily


def _normalize_identity_key(value: object) -> str:
    text = str(value).strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


def _resolve_agent_lookup(agent_registry: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for key in ("agent_id", "registration_code", "tax_id", "edrpou"):
        if key not in agent_registry.columns or "agent_id" not in agent_registry.columns:
            continue
        subset = agent_registry[[key, "agent_id"]].dropna()
        for raw_key, agent_id in subset.itertuples(index=False):
            normalized = _normalize_identity_key(raw_key)
            if not normalized:
                continue
            value = str(agent_id)
            lookup[normalized] = value
            if normalized.isdigit():
                if len(normalized) <= 8:
                    lookup.setdefault(normalized.zfill(8), value)
                if len(normalized) <= 10:
                    lookup.setdefault(normalized.zfill(10), value)
    return lookup


def _resolve_agent_id(value: object, lookup: dict[str, str]) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    direct = lookup.get(_normalize_identity_key(text))
    if direct:
        return direct
    normalized = _normalize_identity_key(text)
    if normalized.isdigit():
        for width in (8, 10):
            direct = lookup.get(normalized.zfill(width))
            if direct:
                return direct
    if text.startswith("agent::"):
        return text
    return None


def _normalize_name_key(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    replacements = {
        "ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ": "ТОВ",  # noqa: RUF001
        "ПРИВАТНЕ ПІДПРИЄМСТВО": "ПП",
        "ФІЗИЧНА ОСОБА ПІДПРИЄМЕЦЬ": "ФОП",
        "ФІЗИЧНА ОСОБА-ПІДПРИЄМЕЦЬ": "ФОП",
        "КОМУНАЛЬНЕ НЕКОМЕРЦІЙНЕ ПІДПРИЄМСТВО": "КНП",
        "КОМУНАЛЬНЕ ПІДПРИЄМСТВО": "КП",
        "ДЕРЖАВНЕ ПІДПРИЄМСТВО": "ДП",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[\"'`«»“”„]+", " ", text)
    text = re.sub(r"[^0-9A-ZА-ЯІЇЄҐ ]+", " ", text)  # noqa: RUF001
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _build_unique_name_lookup(
    agent_registry: pd.DataFrame,
    *,
    allowed_name_keys: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    if "name" not in agent_registry.columns or "agent_id" not in agent_registry.columns:
        return {}
    frame = agent_registry[["agent_id", "registration_code", "region_code", "name"]].copy()
    frame["name_key"] = frame["name"].map(_normalize_name_key)
    frame = frame.dropna(subset=["name_key", "agent_id"])
    if allowed_name_keys is not None:
        normalized_keys = {str(item).strip() for item in allowed_name_keys if str(item).strip()}
        if not normalized_keys:
            return {}
        frame = frame[frame["name_key"].astype("string").isin(normalized_keys)]
    if frame.empty:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for name_key, group in frame.groupby("name_key", sort=False):
        unique_agents = group["agent_id"].astype(str).dropna().unique().tolist()
        if len(unique_agents) != 1:
            continue
        row = group.iloc[0]
        lookup[str(name_key)] = {
            "agent_id": str(unique_agents[0]),
            "registration_code": str(row.get("registration_code") or "").strip(),
            "region_code": str(row.get("region_code") or "").strip(),
            "name": str(row.get("name") or "").strip(),
        }
    return lookup


def _extract_unresolved_identity_rows(
    frame: pd.DataFrame,
    *,
    raw_column: str,
    resolved_column: str,
    family: ObservationFamily,
    source_id: str,
    weight_column: str | None = None,
    name_column: str | None = None,
    region_column: str | None = None,
    period_column: str = "period_id",
) -> pd.DataFrame:
    if raw_column not in frame.columns:
        return pd.DataFrame(
            columns=[
                "raw_registration_code",
                "normalized_raw_registration_code",
                "source_family",
                "source_id",
                "counterparty_name",
                "counterparty_name_key",
                "region_code",
                "period_id",
                "amount_weight",
                "observation_count",
            ]
        )

    raw_series = _coerce_string_series(frame, raw_column)
    resolved_series = _coerce_string_series(frame, resolved_column)
    period_series = (
        _coerce_string_series(frame, period_column, fill="")
        if period_column in frame.columns
        else pd.Series([""] * len(frame))
    )
    weight_series = (
        pd.to_numeric(frame[weight_column], errors="coerce").fillna(1.0)
        if weight_column and weight_column in frame.columns
        else pd.Series([1.0] * len(frame), index=frame.index, dtype=float)
    )
    name_series = (
        _coerce_string_series(frame, name_column, fill="")
        if name_column and name_column in frame.columns
        else pd.Series([""] * len(frame), index=frame.index, dtype="string")
    )
    region_series = (
        _coerce_string_series(frame, region_column, fill="")
        if region_column and region_column in frame.columns
        else pd.Series([""] * len(frame), index=frame.index, dtype="string")
    )

    rows: list[dict[str, Any]] = []
    for raw_value, resolved_value, period_id, weight, counterparty_name, region_code in zip(
        raw_series,
        resolved_series,
        period_series,
        weight_series,
        name_series,
        region_series,
        strict=False,
    ):
        normalized = _normalize_identity_key(raw_value)
        if not normalized or str(resolved_value).strip():
            continue
        rows.append(
            {
                "raw_registration_code": str(raw_value).strip(),
                "normalized_raw_registration_code": normalized,
                "source_family": family.value,
                "source_id": source_id,
                "counterparty_name": str(counterparty_name).strip() or None,
                "counterparty_name_key": _normalize_name_key(counterparty_name),
                "region_code": str(region_code).strip() or None,
                "period_id": str(period_id).strip() or None,
                "amount_weight": float(max(float(weight), 0.0)),
                "observation_count": 1,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "raw_registration_code",
                "normalized_raw_registration_code",
                "source_family",
                "source_id",
                "counterparty_name",
                "counterparty_name_key",
                "region_code",
                "period_id",
                "amount_weight",
                "observation_count",
            ]
        )
    unresolved = pd.DataFrame.from_records(rows)
    return unresolved.groupby(
        [
            "raw_registration_code",
            "normalized_raw_registration_code",
            "source_family",
            "source_id",
            "counterparty_name",
            "counterparty_name_key",
            "region_code",
            "period_id",
        ],
        dropna=False,
        as_index=False,
    ).agg(amount_weight=("amount_weight", "sum"), observation_count=("observation_count", "sum"))


def _build_identity_bridge_seed_lookup(build_root: BuildRootConfig) -> pd.DataFrame:
    seed_path = build_root.manifests_dir / "edr_identity_bridge_seed.parquet"
    if not seed_path.exists():
        return pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "agent_id",
                "match_method",
                "match_confidence",
            ]
        )
    frame = _read_parquet_frame(seed_path)
    if frame.empty:
        return frame
    raw_column = (
        "raw_registration_code"
        if "raw_registration_code" in frame.columns
        else "normalized_raw_registration_code"
    )
    frame["normalized_raw_registration_code"] = frame[raw_column].map(_normalize_identity_key)
    frame = frame.dropna(subset=["normalized_raw_registration_code", "agent_id"]).copy()
    if "match_method" not in frame.columns:
        frame["match_method"] = "manual_seed"
    if "match_confidence" not in frame.columns:
        frame["match_confidence"] = 1.0
    return frame[
        [
            "normalized_raw_registration_code",
            "agent_id",
            "match_method",
            "match_confidence",
        ]
    ].drop_duplicates()


def _filter_identity_bridge_inputs(
    unresolved_rows: pd.DataFrame,
    seed_frame: pd.DataFrame,
) -> pd.DataFrame:
    if unresolved_rows.empty:
        return unresolved_rows.copy()
    filtered = unresolved_rows.copy()
    name_keys = (
        filtered.get("counterparty_name_key", pd.Series(dtype="string"))
        .fillna("")
        .astype("string")
        .str.strip()
    )
    has_name = name_keys.ne("")
    if seed_frame.empty:
        return filtered.loc[has_name].copy()
    seeded_codes = set(seed_frame["normalized_raw_registration_code"].astype("string"))
    normalized_codes = (
        filtered.get("normalized_raw_registration_code", pd.Series(dtype="string"))
        .fillna("")
        .astype("string")
        .str.strip()
    )
    has_seed = normalized_codes.isin(seeded_codes)
    return filtered.loc[has_name | has_seed].copy()


def _build_edr_identity_bridge(
    *,
    build_root: BuildRootConfig,
    agent_registry: pd.DataFrame,
    unresolved_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    seed_frame = _build_identity_bridge_seed_lookup(build_root)
    unresolved_frame = _filter_identity_bridge_inputs(unresolved_rows, seed_frame)
    requested_name_keys = {
        str(value).strip()
        for value in unresolved_frame.get("counterparty_name_key", pd.Series(dtype="string"))
        .fillna("")
        .astype("string")
        .tolist()
        if str(value).strip()
    }
    unique_name_lookup = _build_unique_name_lookup(
        agent_registry,
        allowed_name_keys=requested_name_keys,
    )

    candidate_rows: list[dict[str, Any]] = []
    for row in unresolved_frame.itertuples(index=False):
        normalized_code = str(getattr(row, "normalized_raw_registration_code", "") or "").strip()
        if not normalized_code:
            continue
        name_key = str(getattr(row, "counterparty_name_key", "") or "").strip()
        region_code = str(getattr(row, "region_code", "") or "").strip()
        weight = float(getattr(row, "amount_weight", 0.0) or 0.0)
        observations = int(getattr(row, "observation_count", 0) or 0)
        if name_key and name_key in unique_name_lookup:
            candidate = unique_name_lookup[name_key]
            candidate_region = str(candidate.get("region_code") or "").strip()
            region_match = (
                not region_code or not candidate_region or region_code == candidate_region
            )
            confidence = 0.93 if region_match else 0.72
            candidate_rows.append(
                {
                    "normalized_raw_registration_code": normalized_code,
                    "candidate_agent_id": candidate["agent_id"],
                    "candidate_registration_code": candidate.get("registration_code") or None,
                    "candidate_name": candidate.get("name") or None,
                    "match_method": "edr_unique_name_exact",
                    "match_confidence": confidence,
                    "amount_weight": weight,
                    "observation_count": observations,
                    "source_family": row.source_family,
                    "source_id": row.source_id,
                    "region_match": region_match,
                }
            )

    if not seed_frame.empty:
        for row in seed_frame.itertuples(index=False):
            candidate_rows.append(
                {
                    "normalized_raw_registration_code": str(row.normalized_raw_registration_code),
                    "candidate_agent_id": str(row.agent_id),
                    "candidate_registration_code": None,
                    "candidate_name": None,
                    "match_method": str(row.match_method),
                    "match_confidence": float(row.match_confidence),
                    "amount_weight": 0.0,
                    "observation_count": 0,
                    "source_family": "manual",
                    "source_id": "edr_identity_bridge_seed",
                    "region_match": True,
                }
            )

    candidate_frame = pd.DataFrame.from_records(candidate_rows)
    if candidate_frame.empty:
        candidate_frame = pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "candidate_agent_id",
                "candidate_registration_code",
                "candidate_name",
                "match_method",
                "match_confidence",
                "amount_weight",
                "observation_count",
                "source_family",
                "source_id",
                "region_match",
            ]
        )
    else:
        candidate_frame = candidate_frame.groupby(
            [
                "normalized_raw_registration_code",
                "candidate_agent_id",
                "candidate_registration_code",
                "candidate_name",
                "match_method",
                "match_confidence",
                "region_match",
            ],
            dropna=False,
            as_index=False,
        ).agg(
            amount_weight=("amount_weight", "sum"),
            observation_count=("observation_count", "sum"),
            source_family=(
                "source_family",
                lambda values: ",".join(sorted({str(item) for item in values if str(item)})),
            ),
            source_id=(
                "source_id",
                lambda values: ",".join(sorted({str(item) for item in values if str(item)})),
            ),
        )

    resolved_rows: list[dict[str, Any]] = []
    if not candidate_frame.empty:
        for normalized_code, group in candidate_frame.groupby(
            "normalized_raw_registration_code", sort=False
        ):
            unique_candidates = group["candidate_agent_id"].astype(str).dropna().unique().tolist()
            best = group.sort_values(
                ["match_confidence", "amount_weight", "observation_count"],
                ascending=[False, False, False],
            ).iloc[0]
            if len(unique_candidates) == 1 and float(best["match_confidence"]) >= 0.90:
                resolved_rows.append(
                    {
                        "normalized_raw_registration_code": normalized_code,
                        "agent_id": str(best["candidate_agent_id"]),
                        "match_method": str(best["match_method"]),
                        "match_confidence": float(best["match_confidence"]),
                        "candidate_registration_code": best.get("candidate_registration_code"),
                        "candidate_name": best.get("candidate_name"),
                        "amount_weight": float(best["amount_weight"]),
                        "observation_count": int(best["observation_count"]),
                    }
                )
    resolved_frame = pd.DataFrame.from_records(resolved_rows)
    if resolved_frame.empty:
        resolved_frame = pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "agent_id",
                "match_method",
                "match_confidence",
                "candidate_registration_code",
                "candidate_name",
                "amount_weight",
                "observation_count",
            ]
        )

    manifest = {
        "schema_version": "1.0",
        "manual_seed_applied": not seed_frame.empty,
        "unresolved_identity_rows": len(unresolved_frame),
        "unresolved_unique_numeric_ids": int(
            unresolved_frame["normalized_raw_registration_code"].astype(str).nunique()
            if not unresolved_frame.empty
            else 0
        ),
        "candidate_matches": len(candidate_frame),
        "resolved_matches": len(resolved_frame),
        "resolution_methods": (
            candidate_frame.get("match_method", pd.Series(dtype=str))
            .astype(str)
            .value_counts()
            .to_dict()
            if not candidate_frame.empty
            else {}
        ),
    }
    return unresolved_frame, candidate_frame, resolved_frame, manifest


def _augment_lookup_with_identity_bridge(
    lookup: dict[str, str],
    bridge_resolved: pd.DataFrame,
) -> dict[str, str]:
    augmented = dict(lookup)
    if bridge_resolved.empty:
        return augmented
    for row in bridge_resolved.itertuples(index=False):
        normalized = _normalize_identity_key(getattr(row, "normalized_raw_registration_code", None))
        agent_id = str(getattr(row, "agent_id", "") or "").strip()
        if normalized and agent_id:
            augmented[normalized] = agent_id
            if normalized.isdigit():
                if len(normalized) <= 8:
                    augmented.setdefault(normalized.zfill(8), agent_id)
                if len(normalized) <= 10:
                    augmented.setdefault(normalized.zfill(10), agent_id)
    return augmented


def _participant_resolution_coverage(
    frame: pd.DataFrame,
    *,
    raw_columns: Sequence[str],
    resolved_columns: Sequence[str],
) -> tuple[float | None, int, int]:
    raw_identities: set[str] = set()
    resolved_identities: set[str] = set()
    for raw_column, resolved_column in zip(raw_columns, resolved_columns, strict=True):
        raw_series = _coerce_string_series(frame, raw_column)
        resolved_series = _coerce_string_series(frame, resolved_column)
        for raw_value, resolved_value in zip(raw_series, resolved_series, strict=False):
            normalized = _normalize_identity_key(raw_value)
            if not normalized:
                continue
            raw_identities.add(normalized)
            if str(resolved_value).strip():
                resolved_identities.add(normalized)
    if not raw_identities:
        return None, 0, 0
    return (
        len(resolved_identities) / float(len(raw_identities)),
        len(resolved_identities),
        len(raw_identities),
    )


def _link_participants(
    frame: pd.DataFrame,
    *,
    lookup: dict[str, str],
    source_col: str,
    target_col: str,
    source_out: str,
    target_out: str,
) -> pd.DataFrame:
    linked = frame.copy()
    if source_col in linked.columns:
        linked[source_out] = linked[source_col].map(lambda value: _resolve_agent_id(value, lookup))
    if target_col in linked.columns:
        linked[target_out] = linked[target_col].map(lambda value: _resolve_agent_id(value, lookup))
    return linked


def _build_synthetic_multiscale_payload(
    agent_registry_runtime: pd.DataFrame,
    cell_registry: pd.DataFrame,
    cell_state: pd.DataFrame,
) -> dict[str, Any]:
    agents = _ensure_agent_numeric_columns(agent_registry_runtime)
    if agents.empty:
        agents = pd.DataFrame(
            {"agent_id": ["agent::00000000"], "revenue": [0.0], "employees": [0.0]}
        )
        agents["region_numeric"] = 0.0
        agents["assets"] = 0.0
        agents["liabilities"] = 0.0
    incomes = np.maximum(
        _sanitize_numeric_series(agents["revenue"], fill=0.0, lower=0.0, upper=1e12).to_numpy(
            dtype=float
        ),
        1.0,
    )
    employees = _sanitize_numeric_series(
        agents["employees"], fill=0.0, lower=0.0, upper=1e9
    ).to_numpy(dtype=float)
    n_agents = len(agents)
    employers = np.full(n_agents, -1, dtype=int)
    if n_agents > 0:
        employers[:-1] = 0
    wage_offer = np.nan_to_num(
        incomes / np.maximum(employees, 1.0), nan=1.0, posinf=1.0, neginf=1.0
    )
    firms = pd.DataFrame(
        {
            "labor_count": [float(max(1.0, employees.sum()))],
            "wage_offer": [float(np.nanmean(wage_offer))],
        }
    )
    cells = cell_state.copy()
    if cells.empty:
        cells = pd.DataFrame(
            {
                "cell_id": ["cell::0::0"],
                "region_numeric": [0],
                "sector_numeric": [0],
                "population": [1.0],
                "employment": [0.0],
                "output": [0.0],
                "distress_score": [0.0],
                "public_service_index": [0.0],
            }
        )
    cell_population = _sanitize_numeric_series(cells["population"], fill=1.0, lower=0.0, upper=1e9)
    cell_employment = _sanitize_numeric_series(cells["employment"], fill=0.0, lower=0.0, upper=1e9)
    cell_output = _sanitize_numeric_series(cells["output"], fill=0.0, lower=0.0)
    cell_distress = _sanitize_numeric_series(
        cells["distress_score"], fill=0.0, lower=0.0, upper=1.0
    )
    cell_public_service = _sanitize_numeric_series(
        cells["public_service_index"], fill=0.0, lower=0.0, upper=1.0
    )
    household_cells = cells.head(max(1, min(32, len(cells)))).copy()
    household_population = _sanitize_numeric_series(
        household_cells["population"], fill=1.0, lower=0.0, upper=1e9
    )
    household_output = _sanitize_numeric_series(household_cells["output"], fill=0.0, lower=0.0)
    household_distress = _sanitize_numeric_series(
        household_cells["distress_score"], fill=0.0, lower=0.0, upper=1.0
    )
    household_public_service = _sanitize_numeric_series(
        household_cells["public_service_index"], fill=0.0, lower=0.0, upper=1.0
    )
    household_cells["household_count"] = np.maximum(
        np.ceil(household_population / 3.0),
        1.0,
    )
    household_cells["disposable_income"] = np.maximum(
        household_output / np.maximum(household_cells["household_count"], 1.0),
        1.0,
    )
    household_cells["poverty_rate"] = household_distress
    household_cells["transfer_intensity"] = household_public_service
    payload = {
        "agents": {
            "age": [30.0 + (idx % 25) for idx in range(n_agents)],
            "skill_level": np.clip(
                (employees + 1.0) / np.maximum(employees.max() + 1.0, 1.0), 0.1, 2.0
            ).tolist(),
            "income": incomes.tolist(),
            "reported_income": (0.92 * incomes).tolist(),
            "risk_aversion": np.clip(np.linspace(0.2, 0.8, n_agents), 0.0, 1.0).tolist(),
            "is_employed": (employees > 0.0).tolist(),
            "employer_id": employers.tolist(),
        },
        "firms": firms.to_dict(orient="list"),
        "cells": {
            "active": [True] * len(cells),
            "region_code": pd.to_numeric(cells["region_numeric"], errors="coerce")
            .fillna(0)
            .astype(int)
            .tolist(),
            "sector_id": pd.to_numeric(cells["sector_numeric"], errors="coerce")
            .fillna(0)
            .astype(int)
            .tolist(),
            "population": cell_population.tolist(),
            "employment": cell_employment.tolist(),
            "output": cell_output.tolist(),
            "distress_score": cell_distress.tolist(),
            "public_service_index": cell_public_service.tolist(),
        },
        "household_cells": {
            "active": [True] * len(household_cells),
            "cell_id": list(range(len(household_cells))),
            "household_count": household_cells["household_count"].astype(float).tolist(),
            "disposable_income": household_cells["disposable_income"].astype(float).tolist(),
            "poverty_rate": household_cells["poverty_rate"].astype(float).tolist(),
            "transfer_intensity": household_cells["transfer_intensity"].astype(float).tolist(),
        },
    }
    return payload


def _validation_subset(
    runtime_agents: pd.DataFrame,
    cell_registry: pd.DataFrame,
    cell_state: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    agent_limit = _int_env("POLISYOS_UKRAINE_DATA_BINDINGS_AGENT_LIMIT", 1024)
    cell_limit = _int_env("POLISYOS_UKRAINE_DATA_BINDINGS_CELL_LIMIT", 256)
    warnings: list[str] = []

    validation_agents = runtime_agents.head(agent_limit).copy()
    if len(validation_agents) < len(runtime_agents):
        warnings.append(
            f"bindings_validation_agent_sampled:{len(validation_agents)}/{len(runtime_agents)}"
        )

    referenced_cell_ids = set(
        _coerce_string_series(validation_agents, "cell_id", fill="")
        .replace("", pd.NA)
        .dropna()
        .tolist()
    )
    validation_cells = cell_registry[
        cell_registry["cell_id"].astype("string").isin(referenced_cell_ids)
    ].copy()
    if validation_cells.empty:
        validation_cells = cell_registry.head(cell_limit).copy()
    elif len(validation_cells) > cell_limit:
        validation_cells = validation_cells.head(cell_limit).copy()
    if len(validation_cells) < len(cell_registry):
        warnings.append(
            f"bindings_validation_cell_sampled:{len(validation_cells)}/{len(cell_registry)}"
        )

    validation_cell_ids = set(_coerce_string_series(validation_cells, "cell_id", fill="").tolist())
    validation_cell_state = cell_state[
        cell_state["cell_id"].astype("string").isin(validation_cell_ids)
    ].copy()
    if validation_cell_state.empty:
        validation_cell_state = cell_state.head(len(validation_cells) or cell_limit).copy()

    return validation_agents, validation_cells, validation_cell_state, warnings


__all__ = ()
