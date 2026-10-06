import asyncio
import importlib.util
import json
import tempfile
from argparse import Namespace
from pathlib import Path

from polisyos.data_forge.domains.catalog.batch import pipeline as pipeline_module
from polisyos.data_forge.domains.catalog.batch.cli import _build_config, _run_single_stage
from polisyos.data_forge.domains.catalog.batch.config import DEFAULT_RUN_STAGES

TEST_MODULE_PATH = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-c-catalog-20261006/polisyos/"
    "policy-engine/tests/unit/data_forge/domains/catalog/batch/test_publish.py"
)
spec = importlib.util.spec_from_file_location("catalog_test_publish_review", TEST_MODULE_PATH)
assert spec is not None and spec.loader is not None
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)

with tempfile.TemporaryDirectory(prefix="catalog-after-validation-") as scratch:
    root = Path(scratch)
    registry_path = root / "registry.yaml"
    fixtures._write_test_registry(registry_path)
    args = Namespace(
        snapshot_root=str(root / "snap"),
        registry_path=str(registry_path),
        fail_fast=False,
    )
    config = _build_config(args, stages=DEFAULT_RUN_STAGES)
    fixtures._build_publish_fixture(config)
    asyncio.run(_run_single_stage(args, "benchmark"))
    asyncio.run(_run_single_stage(args, "qc"))

    original_receipt = pipeline_module.current_content_stage_receipt
    state = {"mutated_after_validated_qc": False}

    def replace_reports_after_validation(stage_config, stage):
        receipt = original_receipt(stage_config, stage)
        if stage == "qc" and not state["mutated_after_validated_qc"]:
            fixtures._write_qc_and_benchmark(stage_config)
            state["mutated_after_validated_qc"] = True
        return receipt

    pipeline_module.current_content_stage_receipt = replace_reports_after_validation
    error = None
    try:
        asyncio.run(_run_single_stage(args, "publish"))
    except RuntimeError as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        pipeline_module.current_content_stage_receipt = original_receipt

    readiness_exists = config.consumer_readiness_path.exists()
    manifest_exists = config.publish_manifest_path.exists()
    stage_manifest_exists = (config.manifests_dir / "publish.json").exists()
    print(json.dumps({
        "head": "180bb931ab96cd5f40c1f91c092d24375456d50f",
        "tree": "dc073387ab5b08b77c007286079ff695a886d403",
        "actual_benchmark_and_qc_producers_ran": True,
        "reports_replaced_after_qc_receipt_returned": state["mutated_after_validated_qc"],
        "error": error,
        "consumer_readiness_written": readiness_exists,
        "publish_manifest_written": manifest_exists,
        "publish_stage_manifest_written": stage_manifest_exists,
    }, sort_keys=True))
