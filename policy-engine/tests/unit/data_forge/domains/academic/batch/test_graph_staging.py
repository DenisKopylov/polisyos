"""Synthetic storage controls; no extraction or adjudication authority is created."""

# This gate deliberately uses only the stdlib unittest harness during live-profile holds.
# ruff: noqa: PT009, PT027

from __future__ import annotations

import importlib
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path


class GraphStagingTests(unittest.TestCase):
    """Exercise persisted nested edits and operational refusal through real SQLite."""

    def setUp(self) -> None:
        self.module = importlib.import_module(
            "polisyos.data_forge.domains.academic.batch._graph_staging"
        )
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "synthetic.sqlite"
        self.limits = self.module.GraphCapacityLimits()

    def test_nested_edit_survives_reopen_and_exception_rolls_back(self) -> None:
        with self.module.StagingStore(self.path, self.limits) as store:
            groups = store.groups("synthetic_groups")
            for ref in ("first", "second"):
                with groups.edit(
                    ("policy", "outcome"),
                    lambda: {"synthetic": True, "refs": set(), "nested": {"counts": Counter()}},
                    contribution={"synthetic": True, "ref": ref},
                ) as payload:
                    payload["refs"].add(ref)
                    payload["nested"]["counts"]["positive"] += 1
                    if ref == "first":
                        continue  # The moderation owner's first-seen branch exits this way.
            with (
                self.assertRaisesRegex(RuntimeError, "interrupted"),
                groups.edit(
                    ("policy", "outcome"),
                    dict,
                    contribution={"synthetic": True, "ref": "uncommitted"},
                ) as payload,
            ):
                payload["refs"].add("uncommitted")
                payload["nested"]["counts"]["negative"] += 1
                raise RuntimeError("interrupted")
        with self.module.StagingStore(self.path, self.limits) as store:
            rows = list(store.groups("synthetic_groups").iter_items())
        self.assertEqual(
            rows,
            [
                (
                    ("policy", "outcome"),
                    {
                        "synthetic": True,
                        "refs": {"first", "second"},
                        "nested": {"counts": Counter(positive=2)},
                    },
                )
            ],
        )

    def test_contribution_refusal_precedes_decode_and_mutation(self) -> None:
        limits = replace(self.limits, max_group_contributions=1)
        with self.module.StagingStore(self.path, limits) as store:
            groups = store.groups("synthetic_groups")
            with groups.edit(
                "edge", lambda: {"synthetic": True, "refs": []}, contribution="first"
            ) as payload:
                payload["refs"].append("first")
            with (
                self.assertRaisesRegex(self.module.GraphCapacityError, "max_group_contributions"),
                groups.edit("edge", dict, contribution="second"),
            ):
                self.fail("oversized aggregate entered its mutation scope")
            self.assertEqual(groups.get("edge")["refs"], ["first"])

    def test_byte_refusal_precedes_aggregate_mutation(self) -> None:
        limits = replace(self.limits, max_group_bytes=600)
        with self.module.StagingStore(self.path, limits) as store:
            groups = store.groups("synthetic_groups")
            with groups.edit(
                "edge", lambda: {"synthetic": True, "refs": []}, contribution="first"
            ) as payload:
                payload["refs"].append("first")
            with (
                self.assertRaisesRegex(self.module.GraphCapacityError, "max_group_bytes"),
                groups.edit("edge", dict, contribution="x" * 601),
            ):
                self.fail("oversized serialized contribution entered mutation scope")

    def test_pair_admission_counts_all_directions_before_merge(self) -> None:
        limits = replace(self.limits, max_group_contributions=3, max_pair_contributions=3)
        with self.module.StagingStore(self.path, limits) as store:
            pairs = store.groups("synthetic_pairs", pair=True)
            with pairs.edit(
                ("p", "o"),
                lambda: {"synthetic": True, "refs": []},
                contribution_delta=2,
                contribution=["positive", "positive"],
            ) as value:
                value["refs"].extend(["positive", "positive"])
            with (
                self.assertRaisesRegex(self.module.GraphCapacityError, "max_pair_contributions"),
                pairs.edit(
                    ("p", "o"), dict, contribution_delta=2, contribution=["negative", "negative"]
                ),
            ):
                self.fail("whole-pair fan-in was not checked before merge")

    def test_pair_bytes_accept_exact_reservation_then_refuse_next_before_decode(self) -> None:
        with self.module.StagingStore(
            self.path, self.limits, source_provenance={"synthetic": True}
        ) as store:
            first = {"synthetic": True, "refs": ["positive"]}
            second = {"synthetic": True, "refs": ["negative"]}
            budget = store.encoded_size(first) + store.encoded_size(second)
            store.limits = replace(self.limits, max_pair_bytes=budget)
            pairs = store.groups("synthetic_pairs", pair=True)
            with pairs.edit(
                "pair", lambda: {"synthetic": True, "refs": []}, contribution=first
            ) as row:
                row["refs"].extend(first["refs"])
            with pairs.edit("pair", dict, contribution=second) as row:
                row["refs"].extend(second["refs"])
            with (
                self.assertRaisesRegex(self.module.GraphCapacityError, "max_pair_bytes"),
                pairs.edit("pair", dict, contribution={"synthetic": True, "refs": ["third"]}),
            ):
                self.fail("over-budget pair bytes entered the editor")
            self.assertEqual(pairs.get("pair")["refs"], ["positive", "negative"])

    def test_rows_keep_order_nulls_and_both_batch_bounds(self) -> None:
        limits = replace(self.limits, max_batch_rows=2, max_batch_bytes=400)
        with self.module.StagingStore(self.path, limits) as store:
            rows = store.rows("synthetic_rows")
            expected = [
                (index, {"synthetic": True, "absent": None, "value": "é" * 25})
                for index in range(5)
            ]
            for value in expected:
                rows.append(value)
            batches = list(rows.iter_batches())
            self.assertEqual([row for batch in batches for row in batch], expected)
            for batch in batches:
                self.assertLessEqual(len(batch), 2)
                self.assertLessEqual(sum(store.encoded_size(row) for row in batch), 400)
            self.assertEqual(rows.count(), 5)
            rows.clear()
            self.assertEqual(rows.count(), 0)

    def test_usage_survives_row_flush_and_measures_committed_edits_only(self) -> None:
        with self.module.StagingStore(self.path, self.limits) as store:
            rows = store.rows("synthetic_rows")
            rows.append({"synthetic": True})
            rows.clear()
            with store.groups("synthetic_groups").edit("key", dict, contribution="first") as row:
                row["synthetic"] = True
        usage = self.module.read_staging_usage(self.path)
        self.assertEqual(usage["row_appends"], 1)
        self.assertEqual(usage["aggregate_edits"], 1)
        self.assertEqual(usage["resident_row_count"], 0)
        self.assertEqual(usage["aggregate_groups"], 1)
        self.assertGreater(usage["max_row_bytes"], 0)

    def test_usage_reconciles_all_registered_namespaces_and_applied_configuration(self) -> None:
        with self.module.StagingStore(
            self.path, self.limits, source_provenance={"synthetic": True}
        ) as store:
            rows = store.rows("synthetic_rows")
            rows.append({"synthetic": True})
            self.assertEqual(len(list(rows.iter_batches())), 1)
            rows.clear()
            store.values("synthetic_values")["key"] = "value"
            store.counts("synthetic_counts").increment("key", 2)
            with store.groups("synthetic_groups").edit("key", dict, contribution="first"):
                pass
            store.groups("synthetic_pairs", pair=True)
            with (
                self.assertRaisesRegex(RuntimeError, "interrupted"),
                store.groups("synthetic_groups").edit("key", dict, contribution="second"),
            ):
                raise RuntimeError("interrupted")
        usage = self.module.read_staging_usage(self.path)
        self.assertEqual(usage["applied_limits"], asdict(self.limits))
        self.assertEqual(
            usage["namespace_operations"],
            {
                "synthetic_rows": {"kind": "rows", "writes": 1, "batches": 1},
                "synthetic_values": {"kind": "values", "writes": 1, "batches": 0},
                "synthetic_counts": {"kind": "counts", "writes": 1, "batches": 0},
                "synthetic_groups": {"kind": "groups", "writes": 1, "batches": 0},
                "synthetic_pairs": {"kind": "pairs", "writes": 0, "batches": 0},
            },
        )
        self.assertEqual(
            usage["storage_configuration"]["sqlite_cache_kib"],
            self.limits.sqlite_cache_bytes // 1024,
        )
        self.assertGreater(usage["storage_configuration"]["sqlite_max_page_count"], 0)

    def test_killed_edit_leaves_only_prior_committed_nested_state(self) -> None:
        source = """
import sys
from pathlib import Path
from polisyos.data_forge.domains.academic.batch._graph_staging import GraphCapacityLimits, StagingStore
with StagingStore(Path(sys.argv[1]), GraphCapacityLimits()) as store:
    groups = store.groups('synthetic_groups')
    with groups.edit('key', lambda: {'synthetic': True, 'refs': []}, contribution='committed') as row:
        row['refs'].append('committed')
    with groups.edit('key', dict, contribution='interrupted') as row:
        row['refs'].append('interrupted')
        print('synthetic-uncommitted-edit-ready', flush=True)
        sys.stdin.read()
"""
        with subprocess.Popen(
            [sys.executable, "-c", source, str(self.path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        ) as child:
            self.assertEqual(child.stdout.readline().strip(), "synthetic-uncommitted-edit-ready")
            os.kill(child.pid, signal.SIGKILL)
            child.communicate(timeout=10)
            self.assertEqual(child.returncode, -signal.SIGKILL)
        with self.module.StagingStore(self.path, self.limits) as store:
            self.assertEqual(
                store.groups("synthetic_groups").get("key"),
                {"synthetic": True, "refs": ["committed"]},
            )

    def test_disposable_rebuild_reset_removes_prior_rows_and_groups(self) -> None:
        with self.module.StagingStore(self.path, self.limits) as store:
            store.rows("synthetic_rows").append({"synthetic": True})
            store.values("synthetic_values")["key"] = "old"
            store.reset()
            self.assertEqual(store.rows("synthetic_rows").count(), 0)
            self.assertEqual(len(store.values("synthetic_values")), 0)

    def test_store_owns_synthetic_candidate_provenance_before_derived_rows(self) -> None:
        with self.module.StagingStore(
            self.path, self.limits, source_provenance={"synthetic": True}
        ) as store:
            metadata = store.con.execute(
                "SELECT synthetic,authority FROM spool_metadata"
            ).fetchone()
            self.assertEqual(metadata, (1, "candidate_only"))
            store.rows("derivative").append(("synthetic-derived-identity", None))
        self.assertIs(self.module.read_staging_usage(self.path)["synthetic"], True)

    def test_missing_provenance_stays_unknown_and_actual_ancestry_is_monotone(self) -> None:
        with self.module.StagingStore(self.path, self.limits) as store:
            self.assertIsNone(
                store.con.execute("SELECT synthetic FROM spool_metadata").fetchone()[0]
            )
            store.rows("derivative").append({"nested": {"synthetic": True}})
            self.assertEqual(
                store.con.execute("SELECT synthetic FROM spool_metadata").fetchone()[0], 1
            )
            store.rows("derivative").append({"synthetic": False})
            self.assertEqual(
                store.con.execute("SELECT synthetic FROM spool_metadata").fetchone()[0], 1
            )

    def test_disk_refusal_occurs_on_the_write_that_crosses_the_budget(self) -> None:
        with self.module.StagingStore(
            self.path, self.limits, source_provenance={"synthetic": True}
        ) as store:
            store.limits = replace(self.limits, max_disk_bytes=self.path.stat().st_size + 1000)
            with self.assertRaisesRegex(self.module.GraphCapacityError, "max_disk_bytes"):
                store.rows("synthetic_rows").append({"synthetic": True, "value": "x" * 10_000})

    def test_record_auxiliary_and_single_row_limits_accept_boundary_refuse_next(self) -> None:
        value = {"synthetic": True, "items": [1, 2]}
        with self.module.StagingStore(self.path, self.limits) as store:
            size = store.encoded_size(value)
            store.limits = replace(self.limits, max_record_bytes=size)
            store.check_record(value, "synthetic-record")
            with self.assertRaisesRegex(self.module.GraphCapacityError, "max_record_bytes"):
                store.check_record({**value, "extra": "x"}, "synthetic-record")
            store.limits = replace(self.limits, max_auxiliary_rows_per_work=2)
            store.check_record(value, "synthetic-record")
            with self.assertRaisesRegex(
                self.module.GraphCapacityError, "max_auxiliary_rows_per_work"
            ):
                store.check_record({"synthetic": True, "items": [1, 2, 3]}, "synthetic-record")
            store.limits = replace(self.limits, max_batch_bytes=size)
            store.rows("synthetic-rows").append(value)
            with self.assertRaisesRegex(self.module.GraphCapacityError, "max_batch_bytes"):
                store.rows("synthetic-rows").append({**value, "extra": "x"})

    def test_impossibly_small_disk_budget_is_a_typed_refusal(self) -> None:
        with self.assertRaisesRegex(self.module.GraphCapacityError, "max_disk_bytes"):
            self.module.StagingStore(
                self.path,
                replace(self.limits, max_disk_bytes=1),
                source_provenance={"synthetic": True},
            )

    def test_owned_output_budget_deduplicates_roots_and_bounds_stream_before_growth(self) -> None:
        output = self.path.parent / "outputs" / "synthetic.jsonl"
        with self.module.StagingStore(
            self.path, self.limits, source_provenance={"synthetic": True}
        ) as store:
            store.track_outputs(output)
            before = self.module.measure_owned_output_bytes((self.path.parent, self.path))
            self.assertEqual(
                before, self.module.measure_owned_output_bytes((self.path, self.path.parent))
            )
            text = '{"synthetic":true}\n'
            store.limits = replace(self.limits, max_disk_bytes=before + len(text.encode()))
            with store.text_output(output) as stream:
                stream.write(text)
                with self.assertRaisesRegex(self.module.GraphCapacityError, "max_disk_bytes"):
                    stream.write("é")
            self.assertEqual(output.read_text(), text)

    def test_oversized_owned_manifest_never_reaches_completed_path(self) -> None:
        output = self.path.parent / "completed-synthetic.json"
        with self.module.StagingStore(
            self.path, self.limits, source_provenance={"synthetic": True}
        ) as store:
            before = self.module.measure_owned_output_bytes((self.path.parent,))
            store.limits = replace(self.limits, max_disk_bytes=before + 32)

            def producer(path: Path) -> None:
                path.write_text('{"synthetic":true,"payload":"' + "x" * 100 + '"}')

            with self.assertRaisesRegex(self.module.GraphCapacityError, "max_disk_bytes"):
                store.publish_output(output, producer)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
