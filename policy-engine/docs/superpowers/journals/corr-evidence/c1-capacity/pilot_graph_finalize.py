"""Finalize only the two already completed six-input pilots; never call a provider."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.batch.pipeline import (
    campaign_graph_owner_projection,
    finalize_extraction_campaign_graph,
    resolve_extraction_campaign_graph,
)
from polisyos.data_forge.domains.academic.batch.reextraction_campaign import CampaignPlan

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def main() -> None:
    """Reconcile every old source byte and every new graph table through real owners."""
    common = importlib.import_module(PREFIX + "capacity_common")
    history = importlib.import_module(PREFIX + "campaign_history_probe")
    admission = importlib.import_module(PREFIX + "throughput_runner")
    writer = common.SafeJsonWriter(common.load_credential())
    sources = campaign_graph_owner_projection()
    outputs = []
    for slug, model in (
        ("deepseek", "deepseek-ai/DeepSeek-V4-Flash-0731"),
        ("minimax", "MiniMaxAI/MiniMax-M2.7"),
    ):
        root = Path(".tmp/corr-c1-capacity/pilots") / slug
        root = root.resolve()
        before = history._projection(root)
        with (root / "plan.json").open("rb") as stream:
            raw_plan = stream.read(1_048_577)
        if len(raw_plan) > 1_048_576:
            raise ValueError("pilot_plan_exceeds_bound")
        original_plan = json.loads(raw_plan)["plan"]
        binding = admission._committed(
            common.EVIDENCE / f"2026-09-09-{slug}-pilot-execution-binding.json",
        )
        if original_plan != binding["campaign_plan"]:
            raise ValueError("pilot_original_committed_execution_binding_mismatch")
        plan = CampaignPlan(**original_plan)
        if plan.input_count != 6 or plan.synthetic or plan.extraction_model != model:
            raise ValueError("only_original_completed_six_input_pilots_admitted")
        ref = finalize_extraction_campaign_graph(plan, root, safe_write_json=writer)
        packet = resolve_extraction_campaign_graph(plan, root, ref)
        if packet["synthetic"] is not False:
            raise ValueError("pilot_resolved_synthetic_ancestry_requires_separate_diagnostic")
        after = history._projection(root)
        if set(before) - set(after) or any(after[name] != value for name, value in before.items()):
            raise ValueError("pilot_original_source_bytes_changed")
        novel = set(after) - set(before)
        if any(Path(name).parts[0] not in {"graphs", "graph-builds"} for name in novel):
            raise ValueError("pilot_finalization_escaped_owned_output_roots")
        databases = [root / item["path"] for item in packet["artifacts"]
                     if item["path"].endswith(".duckdb")]
        if len(databases) != 1:
            raise ValueError("pilot_graph_database_identity_ambiguous")
        counts = {}
        with duckdb.connect(str(databases[0]), read_only=True) as connection:
            names = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
            other = {row[0] for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'",
            ).fetchall()}
            if names != other:
                raise ValueError("pilot_graph_table_identity_reconciliation_failed")
            for name in sorted(names):
                quoted = '"' + name.replace('"', '""') + '"'
                sql_count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]  # noqa: S608 - quoted actual table identifier.
                cursor = connection.execute(f"SELECT * FROM {quoted}")  # noqa: S608 - quoted actual table identifier.
                walked = 0
                while cursor.fetchone() is not None:
                    walked += 1
                if walked != sql_count:
                    raise ValueError("pilot_graph_row_denominator_reconciliation_failed")
                counts[name] = walked
        if campaign_graph_owner_projection() != sources:
            raise ValueError("pilot_graph_owner_changed_during_replay")
        outputs.append({
            "model_id": model, "synthetic": packet["synthetic"],
            "authority_status": "candidate_only",
            "original_root": str(root),
            "original_plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
            "graph_ref": {"path": str(root / ref.path), "sha256": ref.sha256},
            "original_source_file_count": len(before),
            "original_source_projection_hash": common.digest(before),
            "original_source_unchanged": True, "new_owned_file_count": len(novel),
            "completed_input_count": packet["completed_input_count"],
            "work_outcomes": packet["work_outcomes"], "graph_metrics": packet["graph_metrics"],
            "complete_table_counts": counts, "table_and_row_reconciliation": "equal",
            "default_flipped": packet["strangle_receipt"]["default_flipped"],
            "scope": "real raw candidate artifacts; no newly admitted authority or N9 input",
        })
    result = {
        "schema_version": "corr.original_pilot_graph_finalization.v1",
        "synthetic": any(output["synthetic"] for output in outputs),
        "authority_status": "candidate_only", "provider_calls": 0,
        "full_pass_executed": False, "graph_owner_projection": sources, "pilots": outputs,
    }
    target = common.EVIDENCE / "original-pilot-graph-finalization.json"
    writer(target, result)
    print(writer.encode({"report": str(target), "provider_calls": 0}))  # noqa: T201


if __name__ == "__main__":
    main()
