"""Synthetic graph capacity controls, separated from evidence admission claims.

Candidate ingestion must emit no admitted claim or edge. The synthesis controls
explicitly seed synthetic mechanical inputs; they do not construct receipts.
"""

# Keep the exact unittest module interface shared with the stdlib storage gate.
# ruff: noqa: PT009, PT027

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
import shutil
import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def _contains_actual_synthetic(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("synthetic") is True or any(
            _contains_actual_synthetic(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_actual_synthetic(item) for item in value)
    return False


def synthetic_records():
    """Return marked derivative records with cross-record moderation and auxiliaries."""
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimOccurrenceVocabularyTransport,
        EstimateCandidate,
        SourceTopicRef,
        WorkRecord,
    )
    from polisyos.ir.analytics.literature import VersionedClaimVocabularyEnvelope

    for index in (0, 1, 2, 1):
        claim_id = f"synthetic-claim-{index}"
        claim = ClaimOccurrenceVocabularyTransport(
            occurrence={
                "claim_id": claim_id,
                "cause": "tax_rate",
                "effect": "employment",
                "direction": "positive" if index % 2 == 0 else "negative",
                "mechanism": "",
                "synthetic": True,
                "publish_to_graph": True,
                "source_provenance": {"synthetic": True, "scope": "capacity_fixture"},
            },
            vocabulary=VersionedClaimVocabularyEnvelope(
                cause="tax_rate",
                effect="employment",
                direction="positive" if index % 2 == 0 else "negative",
                mechanism="",
            ),
        )
        yield WorkRecord(
            id=f"synthetic-work-{index}",
            title=f"Synthetic capacity record {index}",
            year=2020 + index,
            metadata={
                "synthetic": True,
                "sample_size": 100 + index,
                "context_attributes": [
                    {
                        "synthetic": True,
                        "canonical_name": "fixture_context",
                        "country_codes": ["US", "SE"],
                        "confidence": 0.7,
                    }
                ],
                "moderation_edges": [
                    {
                        "synthetic": True,
                        "base_claim_id": claim_id,
                        "moderator": "fixture_context",
                        "confidence": 0.8,
                        "direction_of_moderation": "amplifying",
                        "evidence_count": 1,
                    }
                ],
            },
            causal_claims=[claim],
            concepts=[
                {"id": "synthetic-topic", "display_name": "Synthetic topic", "synthetic": True}
            ],
            estimates=[
                EstimateCandidate(
                    value=0.1 + index, pattern_name="synthetic_estimate", variable_hint="tax_rate"
                )
            ],
            source_topics=[
                SourceTopicRef(topic_id="synthetic-topic", topic_display_name="Synthetic")
            ],
            boundary_conditions=[{"synthetic": True, "scope_text": "synthetic fixture"}],
            context_profile={"synthetic": True, "context_id": "US"},
        )


def complete_database_snapshot(path: Path) -> dict[str, object]:
    """Walk all stored tables, columns and values; validate volatile clock cells separately."""
    import duckdb

    snapshot: dict[str, object] = {}
    with duckdb.connect(str(path), read_only=True) as con:
        tables = con.execute("SHOW TABLES").fetchall()
        for (table,) in tables:
            columns = con.execute(f'DESCRIBE "{table}"').fetchall()
            rows = []
            for source_row in con.execute(f'SELECT * FROM "{table}"').fetchall():  # noqa: S608 - names come from SHOW TABLES in the owned synthetic DB.
                row = []
                for index, value in enumerate(source_row):
                    if isinstance(value, datetime):
                        assert "current_timestamp" in str(columns[index][4]).lower() or (
                            table == "ac_runs"
                            and columns[index][0] in {"started_at", "finished_at"}
                        )
                        assert 2020 <= value.year <= 2100
                        value = {"operational_clock_column": columns[index][0]}
                    row.append(value)
                rows.append(row)
            snapshot[table] = {"columns": columns, "rows": sorted(rows, key=repr)}
    return snapshot


def seed_synthetic_synthesis_inputs(path: Path) -> None:
    """Seed marked reducer controls only; no production admission is represented."""
    import duckdb

    from polisyos.data_forge.domains.academic.knowledge.skg_store import hash_edge_id

    with duckdb.connect(str(path)) as con:
        for index, direction in enumerate(("positive", "negative", "positive")):
            edge_id = hash_edge_id("tax_revenue", "gdp_growth", direction)
            con.execute(
                "INSERT OR REPLACE INTO ac_skg_edges(edge_id,src,dst,direction,n_articles,"
                "article_refs,evidence_strength,confidence,scope_conditions,candidate_layer,"
                "quality_signals_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                [
                    edge_id,
                    "tax_revenue",
                    "gdp_growth",
                    direction,
                    1,
                    json.dumps([f"synthetic-work-{index}"]),
                    "rct",
                    0.8,
                    "[]",
                    "candidate",
                    json.dumps({"synthetic": True, "scope": "synthetic_reducer_input"}),
                ],
            )
            con.execute(
                "INSERT INTO ac_skg_edge_evidence(edge_id,claim_id,openalex_id,src,dst,direction,"
                "evidence_strength,confidence,design_family,design_quality_tier,skg_version) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                [
                    edge_id,
                    f"synthetic-claim-{index}",
                    f"synthetic-work-{index}",
                    "tax_revenue",
                    "gdp_growth",
                    direction,
                    "rct",
                    0.8,
                    "rct",
                    1,
                    1,
                ],
            )


class GraphCapacityTests(unittest.TestCase):
    """Prove default owner use, complete reconciliation and operational refusal."""

    def setUp(self) -> None:
        from polisyos.data_forge.domains.academic.batch._graph_staging import GraphCapacityLimits

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.limits = GraphCapacityLimits()

    def test_complete_candidate_database_parity_across_batch_bounds(self) -> None:
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        for size in (1, 100):
            stats = load_graph(
                records=synthetic_records(),
                db_path=self.root / f"{size}.duckdb",
                insert_batch_size=size,
                capacity_limits=self.limits,
            )
            self.assertEqual((stats.raw_claims, stats.claims, stats.skg_edges), (4, 0, 0))
        self.assertEqual(
            complete_database_snapshot(self.root / "1.duckdb"),
            complete_database_snapshot(self.root / "100.duckdb"),
        )
        snapshot = complete_database_snapshot(self.root / "1.duckdb")
        moderation = snapshot["ac_skg_moderation_edges"]["rows"]
        self.assertEqual(len(moderation), 1)
        self.assertEqual(moderation[0][8], 4)
        self.assertEqual(
            json.loads(moderation[0][12]),
            ["synthetic-work-0", "synthetic-work-1", "synthetic-work-2"],
        )

    def test_default_owner_path_uses_disk_staging(self) -> None:
        from polisyos.data_forge.domains.academic.batch._graph_staging import read_staging_usage
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        stage = self.root / "staging"
        load_graph(
            records=synthetic_records(), db_path=self.root / "graph.duckdb", staging_dir=stage
        )
        usage = read_staging_usage(stage / "graph-load.sqlite")
        self.assertGreater(usage["row_appends"], 0)
        self.assertGreater(usage["aggregate_edits"], 0)
        self.assertEqual(usage["applied_limits"], asdict(self.limits))
        settings = usage["storage_configuration"]
        self.assertEqual(settings["duckdb_threads"], 1)
        self.assertTrue(settings["duckdb_memory_limit"])
        self.assertEqual(settings["duckdb_temp_directory"], str(stage / "duckdb-temp"))
        self.assertGreater(usage["namespace_operations"]["work_batch"]["writes"], 0)

    def test_input_record_capacity_refuses_without_finalized_version(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch._graph_staging import GraphCapacityError
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        path = self.root / "refused.duckdb"
        with self.assertRaisesRegex(GraphCapacityError, "max_record_bytes"):
            load_graph(
                records=synthetic_records(),
                db_path=path,
                capacity_limits=replace(self.limits, max_record_bytes=10),
            )
        with duckdb.connect(str(path), read_only=True) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM ac_skg_edges").fetchone()[0], 0)

    def test_resolver_vocabulary_accepts_measured_bounds_and_refuses_each_smaller_budget(
        self,
    ) -> None:
        from polisyos.data_forge.domains.academic.batch._graph_staging import (
            GraphCapacityError,
            read_staging_usage,
        )
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        stage = self.root / "vocabulary-staging"
        load_graph(
            records=iter(()),
            db_path=self.root / "vocabulary.duckdb",
            staging_dir=stage,
            source_provenance={"synthetic": True},
        )
        usage = read_staging_usage(stage / "graph-load.sqlite")
        measured = {
            "max_resolver_vocabulary_entries": usage["resolver_vocabulary_entries"],
            "max_resolver_vocabulary_bytes": usage["resolver_vocabulary_bytes"],
        }
        load_graph(
            records=iter(()),
            db_path=self.root / "at-limit.duckdb",
            capacity_limits=replace(self.limits, **measured),
            source_provenance={"synthetic": True},
        )
        for name, maximum in measured.items():
            with self.subTest(limit=name), self.assertRaisesRegex(GraphCapacityError, name):
                load_graph(
                    records=iter(()),
                    db_path=self.root / f"{name}.duckdb",
                    capacity_limits=replace(self.limits, **{name: maximum - 1}),
                    source_provenance={"synthetic": True},
                )

    def test_synthetic_synthesis_reconciles_opposing_directions_globally(self) -> None:
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
        from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        snapshots = []
        queues = []
        for size in (1, 100):
            config = AcademicBatchConfig(snapshot_root=self.root / str(size))
            config.db_path.parent.mkdir(parents=True, exist_ok=True)
            load_graph(
                records=synthetic_records(),
                db_path=config.db_path,
                insert_batch_size=size,
                capacity_limits=replace(self.limits, max_batch_rows=size),
            )
            seed_synthetic_synthesis_inputs(config.db_path)
            stats = run_edge_synthesize(
                config,
                capacity_limits=replace(self.limits, max_batch_rows=size),
                source_provenance={"synthetic": True},
            )
            self.assertEqual((stats["family_edges"], stats["contested_edges"]), (2, 1))
            snapshots.append(complete_database_snapshot(config.db_path))
            queues.append(config.canonical_review_queue_path.read_text())
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(queues[0], queues[1])
        for table in ("ac_skg_family_edges", "ac_skg_contested_edges"):
            columns = [column[0] for column in snapshots[0][table]["columns"]]
            quality_index = columns.index("quality_signals_json")
            for row in snapshots[0][table]["rows"]:
                self.assertTrue(json.loads(row[quality_index])["synthetic"])
        baseline_path = (
            Path(__file__).resolve().parents[6]
            / "docs/superpowers/journals/corr-evidence/c1-capacity"
            / "graph-owner-baseline-final.json"
        )
        baseline = json.loads(json.loads(baseline_path.read_text())["stdout"])
        actual = {
            table: hashlib.sha256(
                json.dumps(
                    value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode()
            ).hexdigest()
            for table, value in snapshots[0].items()
        }
        self.assertEqual(actual, baseline["table_digests"])

    def test_whole_pair_capacity_refuses_even_when_each_direction_fits(self) -> None:
        from polisyos.data_forge.domains.academic.batch._graph_staging import GraphCapacityError
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
        from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        config = AcademicBatchConfig(snapshot_root=self.root / "pair")
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        load_graph(records=synthetic_records(), db_path=config.db_path)
        seed_synthetic_synthesis_inputs(config.db_path)
        with self.assertRaisesRegex(GraphCapacityError, "max_pair_contributions"):
            run_edge_synthesize(
                config,
                capacity_limits=replace(
                    self.limits, max_group_contributions=2, max_pair_contributions=2
                ),
                source_provenance={"synthetic": True},
            )
        self.assertFalse(config.edge_synthesis_report_path.exists())

    def test_novel_data_and_forged_publish_flag_remain_unadmitted_candidates(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        record = next(synthetic_records())
        claim = record.causal_claims[0]
        occurrence = {
            **claim.occurrence,
            "cause": "novel_policy_ζ99",
            "effect": "novel_outcome_λ99",
            "publish_to_graph": True,
            "publishable_edge": True,
            "source_provenance": {"synthetic": True, "scope": "novel_candidate_fixture"},
        }
        claim = claim.model_copy(
            update={
                "occurrence": occurrence,
                "vocabulary": claim.vocabulary.model_copy(
                    update={"cause": occurrence["cause"], "effect": occurrence["effect"]}
                ),
            }
        )
        record = record.model_copy(update={"causal_claims": [claim]})
        path = self.root / "novel.duckdb"
        stats = load_graph(records=iter([record]), db_path=path)
        self.assertEqual(
            (stats.raw_claims, stats.claim_adjudications, stats.claims, stats.skg_edges),
            (1, 0, 0, 0),
        )
        with duckdb.connect(str(path), read_only=True) as con:
            self.assertEqual(
                con.execute("SELECT cause,effect FROM ac_causal_claims_raw").fetchone(),
                ("novel_policy_ζ99", "novel_outcome_λ99"),
            )

    def test_legacy_file_intake_refuses_oversize_before_workrecord_construction(self) -> None:
        from polisyos.data_forge.domains.academic.batch import graph_builder
        from polisyos.data_forge.domains.academic.batch._graph_staging import GraphCapacityError
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

        config = AcademicBatchConfig(snapshot_root=self.root / "legacy-input")
        config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
        config.merged_records_path.write_text(
            json.dumps(
                {
                    "id": "synthetic-oversized",
                    "title": "x" * 300,
                    "metadata": {"synthetic": True},
                }
            )
            + "\n"
        )
        with (
            patch.object(
                graph_builder,
                "GraphCapacityLimits",
                return_value=replace(self.limits, max_record_bytes=128),
            ),
            patch.object(
                graph_builder,
                "adapt_jsonl_work_record_claims",
                side_effect=AssertionError("oversized line reached record construction"),
            ),
            self.assertRaisesRegex(GraphCapacityError, "max_record_bytes"),
        ):
            graph_builder.run_graph_load(config)

    def test_synthesis_emissions_infer_actual_synthetic_input_without_caller_marker(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
        from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        config = AcademicBatchConfig(snapshot_root=self.root / "inferred-provenance")
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        load_graph(records=synthetic_records(), db_path=config.db_path)
        seed_synthetic_synthesis_inputs(config.db_path)
        with duckdb.connect(str(config.db_path)) as con:
            con.execute(
                "INSERT INTO ac_skg_canonization_cache(raw_name,canonical_name,approved) "
                "VALUES(?,?,FALSE)",
                ["synthetic unknown", "synthetic_unknown"],
            )
        run_edge_synthesize(config)
        report = json.loads(config.edge_synthesis_report_path.read_text())
        self.assertIs(report["synthetic"], True)
        manifest = json.loads((config.manifests_dir / "edge_synthesize.json").read_text())
        self.assertIs(manifest["metrics"]["synthetic"], True)
        queue = [
            json.loads(line) for line in config.canonical_review_queue_path.read_text().splitlines()
        ]
        self.assertTrue(queue)
        for row in queue:
            self.assertIs(row["synthetic"], True)
            self.assertEqual(row["source_provenance"]["authority"], "candidate_only")

    def test_raw_only_source_ancestry_overrides_missing_and_false_caller_markers(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch._graph_staging import read_staging_usage
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
        from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
        from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph

        for label, caller in (("missing", None), ("false", {"synthetic": False})):
            with self.subTest(caller=label):
                config = AcademicBatchConfig(snapshot_root=self.root / label)
                config.db_path.parent.mkdir(parents=True, exist_ok=True)
                load_graph(records=synthetic_records(), db_path=config.db_path)
                with duckdb.connect(str(config.db_path)) as con:
                    con.execute(
                        "INSERT INTO ac_skg_canonization_cache(raw_name,canonical_name,approved) "
                        "VALUES(?,?,FALSE)",
                        ["synthetic unknown", "synthetic_unknown"],
                    )
                stats = run_edge_synthesize(config, source_provenance=caller)
                self.assertEqual(stats["family_edges"], 0)
                self.assertIs(
                    json.loads(config.edge_synthesis_report_path.read_text())["synthetic"], True
                )
                self.assertIs(
                    json.loads((config.manifests_dir / "edge_synthesize.json").read_text())[
                        "metrics"
                    ]["synthetic"],
                    True,
                )
                queue = [
                    json.loads(line)
                    for line in config.canonical_review_queue_path.read_text().splitlines()
                ]
                self.assertTrue(queue)
                self.assertTrue(all(row["synthetic"] is True for row in queue))
                staging_path = (
                    config.db_path.with_suffix(config.db_path.suffix + ".staging")
                    / "edge-synthesize.sqlite"
                )
                self.assertIs(read_staging_usage(staging_path)["synthetic"], True)

    def test_complete_reader_families_and_each_writer_owned_source_carrier(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch import edge_synthesize, graph_builder
        from polisyos.data_forge.domains.academic.batch._graph_staging import read_staging_usage
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
        from polisyos.data_forge.domains.academic.knowledge import canonical_resolver, skg_store

        readers = (edge_synthesize, canonical_resolver)
        source_families = set()
        for reader in readers:
            tree = ast.parse(inspect.getsource(reader))
            for function in (
                node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            ):
                for node in ast.walk(function):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if re.search(r"\bSELECT\b", node.value, re.I):
                            source_families.update(
                                re.findall(r"\b(?:FROM|JOIN)\s+(ac_[a-z_]+)", node.value, re.I)
                            )
                        if re.fullmatch(r"ac_[a-z_]+", node.value):
                            source_families.add(
                                node.value
                            )  # Actual dynamic source-basis table choices.
        contract = edge_synthesize._SOURCE_PROVENANCE_CODECS
        self.assertEqual(source_families, set(contract))
        print(
            json.dumps(
                {  # noqa: T201 - complete deciding source-family reconciliation receipt.
                    "synthetic": True,
                    "scope": "synthetic_codec_reconciliation",
                    "reader_families": sorted(source_families),
                    "carrier_contract": contract,
                    "owner_sources": {
                        inspect.getsourcefile(owner): hashlib.sha256(
                            Path(inspect.getsourcefile(owner)).read_bytes()
                        ).hexdigest()
                        for owner in (*readers, graph_builder, skg_store)
                    },
                },
                sort_keys=True,
            )
        )
        base = self.root / "synthetic-writer.duckdb"
        graph_builder.load_graph(records=synthetic_records(), db_path=base)
        seed_synthetic_synthesis_inputs(base)
        with duckdb.connect(str(base)) as con:
            con.execute(
                "INSERT INTO ac_skg_canonization_cache(raw_name,canonical_name,approved) "
                "VALUES(?,?,FALSE)",
                ["synthetic unknown", "synthetic_unknown"],
            )
            carriers = []
            for table, codecs in contract.items():
                columns = {row[0]: row[1] for row in con.execute(f'DESCRIBE "{table}"').fetchall()}
                for column, codec in codecs.items():
                    self.assertIn(column, columns)
                    rows = con.execute(f'SELECT "{column}" FROM "{table}"').fetchall()  # noqa: S608 - finite owner contract checked against actual schema above.
                    self.assertTrue(rows)
                    self.assertTrue(
                        any(
                            value is True
                            if codec == "boolean"
                            else _contains_actual_synthetic(json.loads(value or "null"))
                            for (value,) in rows
                        )
                    )
                    carriers.append((table, column, codec))
            for table, column, codec in carriers:
                con.execute(
                    f'UPDATE "{table}" SET "{column}"=?',  # noqa: S608 - schema-checked owner codec identifiers.
                    [None if codec == "boolean" else "{}"],
                )
        for index, (table, column, codec) in enumerate(carriers):
            with self.subTest(source=f"{table}.{column}"):
                config = AcademicBatchConfig(snapshot_root=self.root / f"carrier-{index}")
                config.db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(base, config.db_path)
                with duckdb.connect(str(config.db_path)) as con:
                    con.execute(
                        f'UPDATE "{table}" SET "{column}"=?',  # noqa: S608 - schema-checked owner codec identifiers.
                        [
                            True
                            if codec == "boolean"
                            else json.dumps({"nested": {"synthetic": True}})
                        ],
                    )
                stats = edge_synthesize.run_edge_synthesize(
                    config, source_provenance={"synthetic": False}
                )
                self.assertEqual((stats["family_edges"], stats["contested_edges"]), (2, 1))
                self.assertIs(
                    json.loads(config.edge_synthesis_report_path.read_text())["synthetic"], True
                )
                self.assertIs(
                    json.loads((config.manifests_dir / "edge_synthesize.json").read_text())[
                        "metrics"
                    ]["synthetic"],
                    True,
                )
                for line in config.canonical_review_queue_path.read_text().splitlines():
                    self.assertIs(json.loads(line)["synthetic"], True)
                stage = (
                    config.db_path.with_suffix(config.db_path.suffix + ".staging")
                    / "edge-synthesize.sqlite"
                )
                usage = read_staging_usage(stage)
                self.assertIs(usage["synthetic"], True)
                self.assertEqual(usage["provenance_source_families"], len(contract))
                with duckdb.connect(str(config.db_path), read_only=True) as con:
                    for output in ("ac_skg_family_edges", "ac_skg_contested_edges"):
                        for (quality,) in con.execute(
                            f'SELECT quality_signals_json FROM "{output}"'  # noqa: S608 - two literal synthesized outputs.
                        ).fetchall():
                            self.assertIs(json.loads(quality)["synthetic"], True)

    def test_source_intake_preserves_unknown_and_refuses_present_malformed_ancestry(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch import edge_synthesize, graph_builder
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

        for index, value in enumerate((None, "null", "{broken", '{"synthetic":"false"}')):
            with self.subTest(value=value):
                config = AcademicBatchConfig(snapshot_root=self.root / f"unknown-{index}")
                config.db_path.parent.mkdir(parents=True, exist_ok=True)
                graph_builder.load_graph(records=synthetic_records(), db_path=config.db_path)
                with duckdb.connect(str(config.db_path)) as con:
                    con.execute(
                        "UPDATE ac_causal_claims_raw SET synthetic=NULL,source_provenance_json=?",
                        [value],
                    )
                    con.execute("UPDATE ac_skg_articles SET extraction_json='{}',context_json=NULL")
                if index < 2:
                    edge_synthesize.run_edge_synthesize(config)
                    self.assertIsNone(
                        json.loads(config.edge_synthesis_report_path.read_text())["synthetic"]
                    )
                else:
                    with self.assertRaisesRegex(ValueError, "graph_source_provenance_malformed"):
                        edge_synthesize.run_edge_synthesize(config)
                    self.assertFalse(config.edge_synthesis_report_path.exists())
                    self.assertFalse(config.canonical_review_queue_path.exists())
                    self.assertFalse((config.manifests_dir / "edge_synthesize.json").exists())

    def test_direct_synthesis_counts_queue_bytes_in_shared_output_budget(self) -> None:
        import duckdb

        from polisyos.data_forge.domains.academic.batch import edge_synthesize, graph_builder
        from polisyos.data_forge.domains.academic.batch._graph_staging import GraphCapacityError
        from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

        original = edge_synthesize._canonical_review_queue

        def after_queue(*args, **kwargs):
            queue = original(*args, **kwargs)
            store = kwargs["staging"]
            paths = (store.path.parent, *store._database_paths)
            measured = sum(
                path.stat().st_size
                for root in paths
                for path in (root.rglob("*") if root.is_dir() else [root])
                if path.is_file()
            )
            store.limits = replace(store.limits, max_disk_bytes=measured + 64 * 1024)
            return queue

        for length in (16, 96 * 1024):
            with self.subTest(queue_name_length=length):
                config = AcademicBatchConfig(snapshot_root=self.root / f"queue-{length}")
                config.db_path.parent.mkdir(parents=True, exist_ok=True)
                graph_builder.load_graph(records=synthetic_records(), db_path=config.db_path)
                with duckdb.connect(str(config.db_path)) as con:
                    con.execute(
                        "INSERT INTO ac_skg_canonization_cache(raw_name,canonical_name,approved) "
                        "VALUES(?,?,FALSE)",
                        ["synthetic" + "x" * length, "synthetic_unknown"],
                    )
                with patch.object(
                    edge_synthesize, "_canonical_review_queue", side_effect=after_queue
                ):
                    if length > 64 * 1024:
                        with self.assertRaisesRegex(GraphCapacityError, "max_disk_bytes"):
                            edge_synthesize.run_edge_synthesize(
                                config, source_provenance={"synthetic": True}
                            )
                        self.assertFalse((config.manifests_dir / "edge_synthesize.json").exists())
                    else:
                        edge_synthesize.run_edge_synthesize(
                            config, source_provenance={"synthetic": True}
                        )
                        self.assertTrue((config.manifests_dir / "edge_synthesize.json").exists())


if __name__ == "__main__":
    unittest.main()
