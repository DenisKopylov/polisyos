"""Retain primary graph measurements once and reconcile their complete finite inputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def main() -> None:
    """Archive byte-identical primary evidence or inspect only the two built graphs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("archive", "tables"))
    args = parser.parse_args()
    common = importlib.import_module(PREFIX + "capacity_common")
    profile = importlib.import_module(PREFIX + "graph_finalizer_profile")
    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
        CampaignCheckpoint,
        CampaignPlan,
    )

    declaration = profile._declaration()
    writer = common.SafeJsonWriter(common.load_credential())
    results = []
    for frame in declaration["frames"]:
        size = frame["input_count"]
        root = Path(f".tmp/corr-c1-capacity/graph-profile-{size}").resolve()
        plan = CampaignPlan(**json.loads((root / "plan.json").read_bytes())["plan"])
        if plan.input_digest != frame["input_digest"] or plan.input_count != size:
            raise ValueError("profile_frame_mismatch")
        completed = json.loads((root / "profile-completed.json").read_bytes())
        measurement = json.loads((root / "profile-result.json").read_bytes())["measurement"]
        if args.mode == "tables":
            results.append(_tables(root, completed, size))
            continue
        expected = {profile.source_work(index)["id"] for index in range(size)}
        with CampaignCheckpoint.read_only_history(root, plan) as checkpoint:
            checkpoint.validate_complete_frame()
            observed = {checkpoint.source_work(key)["id"] for key in checkpoint.iter_work_keys()}
            records = {record["id"] for record in checkpoint.iter_records()}
            sql_count = checkpoint.db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
            if (expected != observed or observed != records or len(observed) != sql_count
                    or checkpoint.summary()["outcomes"] != {"extracted": size}
                    or checkpoint.summary()["attempts"] != {}):
                raise ValueError("profile_complete_work_identity_mismatch")
        outputs = []
        primary = (
            root / "profile-telemetry" / "samples.jsonl",
            root / "profile-result.json", root / "profile-completed.json",
        )
        for source in primary:
            raw = source.read_bytes()
            if source.suffix == ".jsonl":
                values = [json.loads(line) for line in raw.splitlines()]
                if len(values) != measurement["sample_count"]:
                    raise ValueError("profile_sample_count_mismatch")
            else:
                values = [json.loads(raw)]
            for value in values:
                if value["synthetic"] is not True:
                    raise ValueError("profile_primary_synthetic_marker_missing")
                writer.check_payload(value)
            writer.check_payload(raw.decode())
            target = common.EVIDENCE / "graph-resource-profiles" / str(size) / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != raw:
                    raise ValueError("primary_archive_already_exists_with_different_bytes")
            else:
                with target.open("xb") as stream:
                    stream.write(raw)
            if target.read_bytes() != raw:
                raise ValueError("primary_archive_byte_identity_mismatch")
            outputs.append({"path": str(target), "sha256": hashlib.sha256(raw).hexdigest()})
        results.append({
            "size": size, "synthetic": True, "scope": "candidate_only",
            "complete_work_identities_equal": True,
            "work_identity_hash": common.digest(sorted(observed)),
            "sql_and_iterator_count": sql_count, "provider_attempts": 0,
            "archived_primary": outputs,
        })
    print(writer.encode({"synthetic": True, "scope": "candidate_only",  # noqa: T201
                         "mode": args.mode, "frames": results}))


def _tables(root: Path, completed: dict, size: int) -> dict:
    import duckdb

    from polisyos.data_forge.domains.academic.batch.pipeline import (
        resolve_extraction_campaign_graph,
    )
    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import CampaignPlan
    from polisyos.data_forge.kernel.pipeline.manifests import ArtifactRef

    plan = CampaignPlan(**json.loads((root / "plan.json").read_bytes())["plan"])
    manifest = resolve_extraction_campaign_graph(
        plan, root, ArtifactRef(**completed["artifact_ref"]),
    )
    if manifest["graph_metrics"] != completed["graph_metrics"]:
        raise ValueError("profile_produced_metric_binding_mismatch")
    paths = [root / item["path"] for item in manifest["artifacts"]
             if item["path"].endswith(".duckdb")]
    if len(paths) != 1:
        raise ValueError("profile_database_identity_ambiguous")
    counts = {}
    with duckdb.connect(str(paths[0]), read_only=True) as con:
        names = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        other = {row[0] for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'",
        ).fetchall()}
        if names != other:
            raise ValueError("profile_complete_table_identity_mismatch")
        for name in sorted(names):
            quoted = '"' + name.replace('"', '""') + '"'
            counted = con.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]  # noqa: S608 - actual quoted schema identifier.
            cursor = con.execute(f"SELECT * FROM {quoted}")  # noqa: S608 - actual quoted schema identifier.
            walked = 0
            while cursor.fetchone() is not None:
                walked += 1
            if walked != counted:
                raise ValueError("profile_complete_table_row_mismatch")
            counts[name] = counted
        actual_ids = {row[0] for row in con.execute("SELECT id FROM ac_works").fetchall()}
        record_ids = set()
        profile = importlib.import_module(PREFIX + "graph_finalizer_profile")
        for index in range(size):
            record_ids.add(profile.source_work(index)["id"])
        if actual_ids != record_ids or counts["ac_causal_claims_raw"] != size:
            raise ValueError("profile_graph_work_identities_mismatch")
    return {"size": size, "synthetic": True, "scope": "candidate_only",
            "complete_table_identity_sets_equal": True, "complete_table_row_counts": counts,
            "expected_work_identities_equal_actual_graph": True}


if __name__ == "__main__":
    main()
