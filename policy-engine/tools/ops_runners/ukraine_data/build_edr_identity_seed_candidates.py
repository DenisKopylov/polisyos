from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from polisyos.data_forge.domains.ukraine.builders import (
    _ensure_agent_numeric_columns,
    _extract_unresolved_identity_rows,
    _link_participants,
    _load_source_frame,
    _read_parquet_frame,
    _resolve_agent_lookup,
    _select_procurement_frame,
    _write_frame,
    _write_json,
)
from polisyos.data_forge.domains.ukraine.models import (
    BuildRootConfig,
    build_default_pipeline_config,
)


def _load_unresolved_rows_from_d0(build_root: BuildRootConfig) -> pd.DataFrame:
    stage_dir = build_root.runtime_dir / "d0_p0"
    raw_path = stage_dir / "edr_identity_bridge_unresolved_raw.parquet"
    filtered_path = stage_dir / "edr_identity_bridge_unresolved.parquet"
    if raw_path.exists():
        return _read_parquet_frame(raw_path)
    if filtered_path.exists():
        return _read_parquet_frame(filtered_path)
    return pd.DataFrame()


def build_seed_candidate_report(root: Path, *, top_n: int) -> dict[str, Path]:
    config = build_default_pipeline_config(root=root)
    build_root: BuildRootConfig = config.build_root
    out_dir = build_root.manifests_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    unresolved_rows = _load_unresolved_rows_from_d0(build_root)
    used_runtime_unresolved_artifact = not unresolved_rows.empty
    procurement_source_id = "unknown"
    if not unresolved_rows.empty:
        procurement_source_candidates = (
            unresolved_rows.get("source_id", pd.Series(dtype="string"))
            .dropna()
            .astype("string")
            .tolist()
        )
        procurement_source_id = next(
            (
                source_id
                for source_id in procurement_source_candidates
                if "prozorro" in str(source_id)
                or "spending_contracts_procurement_proxy" in str(source_id)
            ),
            procurement_source_id,
        )

    if unresolved_rows.empty:
        edr = _load_source_frame(
            config,
            "edr_current",
            columns=["agent_id", "registration_code", "tax_id", "edrpou", "region_code", "name"],
        )
        spending = _load_source_frame(
            config,
            "spending_full",
            columns=["source_agent_id", "target_agent_id", "amount", "period_id"],
        )
        procurement, procurement_source_id, _warnings = _select_procurement_frame(
            config,
            columns=["buyer_agent_id", "supplier_agent_id", "amount", "period_id", "supplier_name"],
        )

        agent_registry = _ensure_agent_numeric_columns(edr)
        lookup = _resolve_agent_lookup(agent_registry)
        agent_name_lookup = (
            agent_registry[["agent_id", "name"]]
            .dropna(subset=["agent_id"])
            .assign(agent_id=lambda frame: frame["agent_id"].astype("string"))
            .drop_duplicates(subset=["agent_id"])
            .set_index("agent_id")["name"]
            .astype("string")
            .to_dict()
        )

        spending_for_linking = spending.copy()
        spending_for_linking["_source_agent_raw_id"] = spending_for_linking[
            "source_agent_id"
        ].astype("string")
        spending_for_linking["_target_agent_raw_id"] = spending_for_linking[
            "target_agent_id"
        ].astype("string")
        spending_linked = _link_participants(
            spending_for_linking,
            lookup=lookup,
            source_col="source_agent_id",
            target_col="target_agent_id",
            source_out="source_agent_id",
            target_out="target_agent_id",
        )
        spending_linked["counterparty_name"] = (
            spending_linked.get("source_agent_id", pd.Series(dtype="string"))
            .astype("string")
            .map(agent_name_lookup)
        )

        procurement_for_linking = procurement.copy()
        procurement_for_linking["_buyer_agent_raw_id"] = procurement_for_linking[
            "buyer_agent_id"
        ].astype("string")
        procurement_for_linking["_supplier_agent_raw_id"] = procurement_for_linking[
            "supplier_agent_id"
        ].astype("string")
        procurement_linked = _link_participants(
            procurement_for_linking,
            lookup=lookup,
            source_col="buyer_agent_id",
            target_col="supplier_agent_id",
            source_out="buyer_agent_id",
            target_out="supplier_agent_id",
        )
        procurement_linked["buyer_counterparty_name"] = (
            procurement_linked.get("buyer_agent_id", pd.Series(dtype="string"))
            .astype("string")
            .map(agent_name_lookup)
        )

        unresolved_rows = pd.concat(
            [
                _extract_unresolved_identity_rows(
                    spending_linked,
                    raw_column="_target_agent_raw_id",
                    resolved_column="target_agent_id",
                    family=config.sources["spending_full"].observation_family,
                    source_id="spending_full",
                    weight_column="amount",
                    name_column="counterparty_name",
                ),
                _extract_unresolved_identity_rows(
                    procurement_linked,
                    raw_column="_supplier_agent_raw_id",
                    resolved_column="supplier_agent_id",
                    family=config.sources[procurement_source_id].observation_family,
                    source_id=procurement_source_id,
                    weight_column="amount",
                    name_column="supplier_name",
                    region_column="region_code",
                ),
                _extract_unresolved_identity_rows(
                    procurement_linked,
                    raw_column="_supplier_agent_raw_id",
                    resolved_column="supplier_agent_id",
                    family=config.sources[procurement_source_id].observation_family,
                    source_id=f"{procurement_source_id}_buyer_context",
                    weight_column="amount",
                    name_column="buyer_counterparty_name",
                    region_column="region_code",
                ),
            ],
            ignore_index=True,
        )

    if unresolved_rows.empty:
        summary = pd.DataFrame(
            columns=[
                "normalized_raw_registration_code",
                "amount_weight",
                "observation_count",
                "source_families",
                "source_ids",
                "counterparty_names",
                "first_period",
                "last_period",
            ]
        )
    else:
        summary = (
            unresolved_rows.groupby(
                "normalized_raw_registration_code", as_index=False, dropna=False
            )
            .agg(
                amount_weight=("amount_weight", "sum"),
                observation_count=("observation_count", "sum"),
                source_families=(
                    "source_family",
                    lambda values: ",".join(sorted({str(item) for item in values if str(item)})),
                ),
                source_ids=(
                    "source_id",
                    lambda values: ",".join(sorted({str(item) for item in values if str(item)})),
                ),
                counterparty_names=(
                    "counterparty_name",
                    lambda values: "|".join(
                        sorted({str(item).strip() for item in values if str(item).strip()})[:5]
                    ),
                ),
                first_period=("period_id", "min"),
                last_period=("period_id", "max"),
            )
            .sort_values(["amount_weight", "observation_count"], ascending=[False, False])
            .head(top_n)
            .reset_index(drop=True)
        )

    template = summary.copy()
    for column in [
        "seed_agent_id",
        "seed_registration_code",
        "seed_match_method",
        "seed_match_confidence",
        "seed_notes",
    ]:
        template[column] = None

    candidates_path = _write_frame(out_dir / "edr_identity_seed_candidates_top.parquet", summary)
    template_path = _write_frame(out_dir / "edr_identity_seed_template.parquet", template)
    manifest_path = _write_json(
        out_dir / "edr_identity_seed_candidates_manifest.json",
        {
            "schema_version": "1.0",
            "top_n": top_n,
            "procurement_source_id": procurement_source_id,
            "used_runtime_unresolved_artifact": used_runtime_unresolved_artifact,
            "unresolved_rows_considered": len(unresolved_rows),
            "candidate_rows": len(summary),
            "template_rows": len(template),
            "candidate_artifact": str(candidates_path),
            "template_artifact": str(template_path),
        },
    )
    return {
        "candidates": candidates_path,
        "template": template_path,
        "manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=500)
    args = parser.parse_args()
    outputs = build_seed_candidate_report(args.root, top_n=args.top_n)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))


if __name__ == "__main__":
    main()
