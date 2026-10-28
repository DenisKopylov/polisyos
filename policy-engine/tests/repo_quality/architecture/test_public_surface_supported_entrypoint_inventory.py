from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails

REPO_ROOT = Path(__file__).resolve().parents[3]


def _inventory() -> list[guardrails.PackageInventory]:
    policies = guardrails._parse_public_surface(
        REPO_ROOT / "architecture/public_surface/contract.toml"
    )
    return guardrails.build_public_surface_inventory(policies)


def test_read_api_compliance_module_is_lazily_routed_from_the_owned_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.util
    import sys

    import polisyos.data_forge.read_api as read_api

    route_path = REPO_ROOT / "src/polisyos/data_forge/read_api/surface_routes.py"
    spec = importlib.util.spec_from_file_location(
        "polisyos.data_forge.read_api._candidate_surface_routes",
        route_path,
    )
    assert spec is not None and spec.loader is not None
    routes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routes)

    target = "polisyos.data_forge.read_api.compliance"
    assert "compliance" in read_api.__all__
    assert routes.READ_API_SURFACE_MODULES["compliance"] == target
    assert "compliance" in routes.READ_API_SURFACE_SUMMARIES

    monkeypatch.setattr(
        read_api,
        "_READ_API_SURFACE_MODULES",
        dict(routes.READ_API_SURFACE_MODULES),
    )
    monkeypatch.delattr(read_api, "compliance", raising=False)
    monkeypatch.delitem(sys.modules, target, raising=False)

    assert "compliance" in dir(read_api)
    assert "compliance" not in read_api.__dict__
    assert target not in sys.modules

    compliance = read_api.compliance
    assert compliance.__name__ == target
    assert (
        Path(compliance.__file__).resolve()
        == Path(read_api.__file__).with_name("compliance.py").resolve()
    )
    unknown_name = "unknown_surface"
    with pytest.raises(AttributeError):
        getattr(read_api, unknown_name)


def test_public_surface_inventory_enumerates_every_supported_entrypoint_facade() -> None:
    manifest = tomllib.loads(
        (REPO_ROOT / "architecture/public_surface/contract.toml").read_text(encoding="utf-8")
    )
    expected = {
        entrypoint
        for package in manifest["package"]
        for entrypoint in package["supported_entrypoints"]
    }
    observed = {entrypoint.module for package in _inventory() for entrypoint in package.entrypoints}

    assert observed == expected


def test_supported_entrypoint_inventory_resolves_module_and_package_facades() -> None:
    entrypoints = {
        entrypoint.module: entrypoint
        for package in _inventory()
        for entrypoint in package.entrypoints
    }

    for module in ("polisyos.ir.api", "polisyos.fabric.api", "polisyos.foundry.api"):
        assert entrypoints[module].source_file == f"src/{module.replace('.', '/')}.py"
    for module in (
        "polisyos.foundry.compile",
        "polisyos.foundry.execute",
        "polisyos.runtime.quality",
        "polisyos.data_forge.read_api",
        "polisyos.scientist.methods.research_dag",
    ):
        assert entrypoints[module].source_file == (f"src/{module.replace('.', '/')}/__init__.py")


def test_foundry_public_surface_registers_backend_entrypoint_without_leaking_exports() -> None:
    import polisyos.foundry as facade
    from polisyos.foundry.methods import backends

    manifest = tomllib.loads(
        (REPO_ROOT / "architecture/public_surface/contract.toml").read_text(encoding="utf-8")
    )
    foundry_contract = next(
        row for row in manifest["package"] if row["module"] == "polisyos.foundry"
    )
    foundry = next(package for package in _inventory() if package.module == "polisyos.foundry")
    root_entrypoint = next(row for row in foundry.entrypoints if row.module == foundry.module)
    assert foundry.export_count == len(facade.__all__)
    assert foundry.known_export_count == len(facade.__all__)
    assert root_entrypoint.export_resolution["complete"] is True
    assert set(root_entrypoint.exports) == set(facade.__all__)
    # Real declaration consumers preserve the original embedding boundary;
    # import/name checks do not execute any optional estimator backend.
    root_exports = set(facade.__all__)
    backend_exports = set(backends.__all__)
    backend_entrypoint = "polisyos.foundry.methods.backends"
    embedding_exports = {
        "EmbedderProtocol",
        "SentenceTransformerEmbedder",
        "TFIDFEmbedder",
    }

    assert backend_entrypoint in foundry_contract["supported_entrypoints"]
    assert backend_entrypoint in foundry.supported_entrypoints
    assert backend_entrypoint in {entrypoint.module for entrypoint in foundry.entrypoints}
    assert embedding_exports <= root_exports
    assert root_exports.isdisjoint(backend_exports)


def test_scientist_execution_facades_resolve_registered_owner_exports() -> None:
    """The scanner and live imports both resolve the two admitted facades."""
    import polisyos.scientist.adapters as adapters
    import polisyos.scientist.compute as compute
    from polisyos.scientist.adapters import fabric_bridge, registered_sql_admission
    from polisyos.scientist.nodes.builtins.decide import policy_runtime_method_metrics as metrics

    primary = tomllib.loads(
        (REPO_ROOT / "architecture/packages/scientist.toml").read_text(encoding="utf-8")
    )["public_surface"]["supported_entrypoints"]
    aggregate = tomllib.loads(
        (REPO_ROOT / "architecture/public_surface/contract.toml").read_text(encoding="utf-8")
    )
    scientist = next(row for row in aggregate["package"] if row["module"] == "polisyos.scientist")
    for module, facade in (
        ("polisyos.scientist.compute", compute),
        ("polisyos.scientist.adapters", adapters),
    ):
        assert module in primary and module in scientist["supported_entrypoints"]
        entrypoint = guardrails._entrypoint_inventory(module)
        assert entrypoint.export_resolution["complete"] is True
        assert set(entrypoint.exports) == set(facade.__all__)

    # These are the actual Scientist owners used by Runtime, not names declared
    # in TOML alone. Removing a route must fail this real import/replay witness.
    assert compute.BoundedMethodMetricSourceReader is metrics._BoundedExecutionSourceReader
    assert compute.MethodMetricSourceReadBudget is metrics._ProjectionReadBudget
    assert compute.VerifiedRestrictedExAnteCall is metrics._VerifiedRestrictedExAnteCall
    assert (
        compute.read_bounded_method_metric_artifact is metrics._read_bounded_method_metric_artifact
    )
    assert compute.selected_method_metric_ref is metrics._selected_ref
    assert compute.MAX_METHOD_METRIC_SOURCE_BYTES == metrics.MAX_METHOD_METRIC_SOURCE_BYTES
    assert adapters.RegisteredSQLCapture is registered_sql_admission.RegisteredSQLCapture
    assert adapters.RegisteredSQLViewContract is registered_sql_admission.RegisteredSQLViewContract
    assert (
        adapters.registered_sql_capture_input_refs
        is registered_sql_admission.registered_sql_capture_input_refs
    )
    assert adapters.parse_data_view_request is fabric_bridge.parse_data_view_request
    unknown_compute = "not_a_registered_execution_owner"
    unknown_adapter = "not_a_registered_capture_owner"
    with pytest.raises(AttributeError):
        getattr(compute, unknown_compute)
    with pytest.raises(AttributeError):
        getattr(adapters, unknown_adapter)


def test_supported_entrypoint_inventory_rejects_missing_or_ambiguous_facade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "src"
    monkeypatch.setattr(guardrails, "SRC_ROOT", source_root)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match=r"polisyos\.fixture.*found 0"):
        guardrails._facade_source_for("polisyos.fixture")

    module_path = source_root / "polisyos" / "fixture.py"
    package_path = source_root / "polisyos" / "fixture" / "__init__.py"
    module_path.parent.mkdir(parents=True)
    package_path.parent.mkdir(parents=True)
    module_path.write_text('__all__ = ["module_arm"]\n', encoding="utf-8")
    package_path.write_text('__all__ = ["package_arm"]\n', encoding="utf-8")

    with pytest.raises(FileNotFoundError, match=r"polisyos\.fixture.*found 2"):
        guardrails._facade_source_for("polisyos.fixture")


def test_runtime_quality_inventory_contains_human_decision_record() -> None:
    import hashlib

    import polisyos.runtime.quality as native
    from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
        HumanDecisionRecord,
    )

    inventory = _inventory()
    entrypoint = next(
        entrypoint
        for package in inventory
        for entrypoint in package.entrypoints
        if entrypoint.module == "polisyos.runtime.quality"
    )

    assert entrypoint.source_file == "src/polisyos/runtime/quality/__init__.py"
    assert entrypoint.export_count == len(native.__all__)
    assert entrypoint.known_export_count == len(native.__all__)
    assert entrypoint.export_resolution["complete"] is True
    assert set(entrypoint.exports) == set(native.__all__)
    assert "HumanDecisionRecord" in entrypoint.exports
    source_read = next(
        row
        for row in entrypoint.export_resolution["inputs"]
        if row["path"] == entrypoint.source_file and row["operation"] == "read_bytes"
    )
    assert (
        source_read["sha256"]
        == hashlib.sha256((REPO_ROOT / entrypoint.source_file).read_bytes()).hexdigest()
    )
    assert not any(
        row.subject == entrypoint.module and row.detail == "incomplete_exports"
        for row in guardrails._check_public_surface_contracts(inventory)
    )
    # Native object identity is an independent consumer observation, not proof
    # that arbitrary import-time declarations fall within the static grammar.
    assert "HumanDecisionRecord" in native.__all__
    assert native.HumanDecisionRecord is HumanDecisionRecord


def test_runtime_quality_eval_safety_facade_exports_canonical_objects() -> None:
    """The supported facade preserves each EvalSafety owner's exact object identity."""
    import polisyos.runtime.quality as facade
    from polisyos import pdc
    from polisyos.runtime.quality import (
        evaluation_modes,
        evaluation_safety,
        world_model_record,
    )

    expected = {
        "EvalSafetyAdmissionChallenge": pdc.EvalSafetyAdmissionChallenge,
        "EvalSafetyVerifierPort": pdc.EvalSafetyVerifierPort,
        "EvaluationExecutionContext": pdc.EvaluationExecutionContext,
        "WorldModelRecord": pdc.WorldModelRecord,
        "evaluation_safety_consumer_admission_is_verified": (
            pdc.evaluation_safety_consumer_admission_is_verified
        ),
        "resolve_evaluation_mode": evaluation_modes.resolve_evaluation_mode,
        "world_model_record_content_hash": pdc.world_model_record_content_hash,
    }

    assert {name: getattr(facade, name) for name in expected} == expected
    assert evaluation_safety.EvalSafetyAdmissionChallenge is pdc.EvalSafetyAdmissionChallenge
    assert evaluation_safety.EvalSafetyVerifierPort is pdc.EvalSafetyVerifierPort
    assert evaluation_safety.EvaluationExecutionContext is pdc.EvaluationExecutionContext
    assert world_model_record.WorldModelRecord is pdc.WorldModelRecord
    assert set(expected) <= set(facade.__all__)


def test_runtime_quality_facade_reexports_canonical_gy_content_hash() -> None:
    """The legal Scientist route preserves the PDC hash owner's exact identity."""
    import polisyos.runtime.quality as facade
    from polisyos.pdc import gy_content_hash as canonical_gy_content_hash

    assert facade.gy_content_hash is canonical_gy_content_hash
    assert "gy_content_hash" in facade.__all__
    assert facade.gy_content_hash({"design": "bound"}) == canonical_gy_content_hash(
        {"design": "bound"}
    )


def test_runtime_quality_facade_reexports_streaming_gy_content_hash_rows() -> None:
    """The stream helper stays owned by PDC and available through the same facade."""
    import polisyos.runtime.quality as facade
    from polisyos.pdc import gy_content_hash_rows as canonical_hash_rows

    rows = [("dataset-1", "variable", "metric", 0.75, None, True, 0.0)]
    assert facade.gy_content_hash_rows is canonical_hash_rows
    assert "gy_content_hash_rows" in facade.__all__
    assert facade.gy_content_hash_rows(
        [
            "dataset_id",
            "raw_variable",
            "canonical_var",
            "confidence",
            "evidence",
            "is_proxy",
            "proxy_penalty",
        ],
        iter(rows),
    ) == canonical_hash_rows(
        [
            "dataset_id",
            "raw_variable",
            "canonical_var",
            "confidence",
            "evidence",
            "is_proxy",
            "proxy_penalty",
        ],
        iter(rows),
    )


def test_public_surface_inventory_corrupt_supported_entrypoint_fails_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "src"
    package_root = source_root / "polisyos" / "fixture"
    package_root.mkdir(parents=True)
    facade = package_root / "__init__.py"
    facade.write_text(
        '"""Fixture facade."""\n__all__ = ["HumanDecisionRecord"]\n',
        encoding="utf-8",
    )
    (package_root / "README.md").write_text(
        "Last updated: 2026-08-24\n\n## Where to Start\n",
        encoding="utf-8",
    )
    reference_doc = tmp_path / "docs" / "reference.md"
    reference_doc.parent.mkdir(parents=True)
    reference_doc.write_text("fixture\n", encoding="utf-8")
    manifest = tmp_path / "public.toml"
    manifest.write_text(
        "\n".join(
            (
                "[[package]]",
                'module = "polisyos.fixture"',
                'classification = "public_experimental"',
                'facade_mode = "eager_exports"',
                'owner = "test-owner"',
                'readme = "src/polisyos/fixture/README.md"',
                'reference_doc = "docs/reference.md"',
                'supported_entrypoints = ["polisyos.fixture"]',
                "major_subsystem = false",
                'notes = "fixture"',
                "",
            )
        ),
        encoding="utf-8",
    )
    generated_manifest = tmp_path / "generated.toml"
    generated_manifest.write_text("", encoding="utf-8")
    generated_md = tmp_path / "generated.md"
    generated_md.write_text(guardrails.render_generated_artifacts_markdown([]), encoding="utf-8")
    exceptions = tmp_path / "exceptions.toml"
    exceptions.write_text("", encoding="utf-8")
    exception_registry = tmp_path / "exceptions.md"
    exception_registry.write_text("| id | state |\n| --- | --- |\n", encoding="utf-8")

    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(guardrails, "SRC_ROOT", source_root)
    monkeypatch.setattr(guardrails, "DEFAULT_MODULE_SIZE_BUDGET", tmp_path / "none.toml")
    monkeypatch.setattr(guardrails, "_check_workflow_toolchain_guardrails", lambda: [])
    policies = guardrails._parse_public_surface(manifest)
    initial = guardrails.build_public_surface_inventory(policies)
    public_json = tmp_path / "inventory.json"
    public_json.write_text(guardrails.render_public_surface_json(initial), encoding="utf-8")
    public_md = tmp_path / "public.md"
    public_md.write_text(guardrails.render_public_surface_markdown(initial), encoding="utf-8")
    deep_baseline = tmp_path / "deep.json"
    deep_baseline.write_text(
        guardrails.render_deep_import_baseline_json(guardrails.collect_deep_import_edges(policies)),
        encoding="utf-8",
    )

    facade.write_text('"""Fixture facade."""\n__all__ = []\n', encoding="utf-8")
    args = argparse.Namespace(
        public_manifest=manifest,
        public_json=public_json,
        public_md=public_md,
        generated_manifest=generated_manifest,
        generated_md=generated_md,
        deep_import_baseline=deep_baseline,
        exceptions=exceptions,
        exceptions_registry=exception_registry,
        max_expiry_days=90,
        skip_generated_checks=True,
        all_generated_checks=False,
        generated_expected_root=tmp_path,
    )

    assert guardrails.run_check(args) == 1
    output = capsys.readouterr().out
    assert "Public surface inventory JSON drift detected" in output
    assert '"HumanDecisionRecord"' in output

    facade.write_text(
        '"""Fixture facade."""\n__all__ = ["HumanDecisionRecord"]\n',
        encoding="utf-8",
    )
    public_inventory = guardrails.build_public_surface_inventory(policies)
    public_generated_families = guardrails._parse_public_generated_artifact_families(manifest)
    public_json.write_text(
        guardrails.render_public_surface_json(
            public_inventory,
            generated_artifact_families=public_generated_families,
        ),
        encoding="utf-8",
    )
    public_md.write_text(
        guardrails.render_public_surface_markdown(public_inventory), encoding="utf-8"
    )
    generated_md.write_text("corrupted generated-artifacts reference\n", encoding="utf-8")

    assert guardrails.run_check(args) == 1
    output = capsys.readouterr().out
    assert "Generated-artifacts reference doc drift detected." in output
    assert "Public surface inventory JSON drift detected." not in output
    assert "Public surface reference doc drift detected." not in output
    assert "Deep-import baseline drift detected." not in output


def test_generated_inventory_serializes_each_resolved_facade() -> None:
    payload = json.loads(guardrails.render_public_surface_json(_inventory()))
    runtime_quality = next(
        row for row in payload["packages"] if row["module"] == "polisyos.runtime.quality"
    )

    assert runtime_quality["classification"] == "public_experimental"
    assert [row["module"] for row in runtime_quality["entrypoints"]] == ["polisyos.runtime.quality"]


def test_ddm_facade_policy_matches_observed_lazy_boundary() -> None:
    import hashlib

    import polisyos.ddm as native
    from polisyos.ddm.integration.monitor import DDMWindowResult

    inventory = _inventory()
    ddm = next(package for package in inventory if package.module == "polisyos.ddm")

    assert ddm.facade_mode_expected == "lazy_facade"
    assert ddm.facade_mode_observed == "lazy_facade"
    assert ddm.export_count == len(native.__all__)
    assert ddm.known_export_count == len(native.__all__)
    entrypoint = ddm.entrypoints[0]
    assert entrypoint.export_resolution["complete"] is True
    assert set(entrypoint.exports) == set(native.__all__)
    source_read = next(
        row
        for row in entrypoint.export_resolution["inputs"]
        if row["path"] == entrypoint.source_file and row["operation"] == "read_bytes"
    )
    assert (
        source_read["sha256"]
        == hashlib.sha256((REPO_ROOT / entrypoint.source_file).read_bytes()).hexdigest()
    )
    assert not any(
        row.subject == ddm.module and row.detail == "incomplete_exports"
        for row in guardrails._check_public_surface_contracts(inventory)
    )
    assert callable(native.__getattr__)
    assert native.__getattr__("DDMWindowResult") is DDMWindowResult
    with pytest.raises(AttributeError):
        native.__getattr__("unknown_public_candidate")
