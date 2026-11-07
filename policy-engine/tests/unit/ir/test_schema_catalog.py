from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import pickle
import subprocess
import sys
import textwrap
from pathlib import Path

from polisyos.ir import (
    enumerate_ir_exports,
    get_ir_schema_catalog,
    get_ir_type,
    list_ir_types,
)
from polisyos.ir.schemas import IRPublicStatus


def test_schema_catalog_exposes_root_metadata() -> None:
    catalog = get_ir_schema_catalog()
    assert len(catalog.types) >= 700

    hte = get_ir_type("HTEResult")
    assert hte.schema_version == "1.0"
    assert hte.public_status is IRPublicStatus.ROOT_FACADE
    assert hte.docs_link.endswith("#polisyos-ir-analytics-hte-hteresult")

    subgroup_field = next(field for field in hte.fields if field.name == "subgroup_effects")
    assert "polisyos.ir.analytics.hte.SubgroupEffect" in subgroup_field.references


def test_schema_catalog_lists_section_filters_and_bridge_exports() -> None:
    observation_types = list_ir_types(section="observation")
    assert any(entry.name == "ObservationRecord" for entry in observation_types)
    governance_types = list_ir_types(section="governance")
    assert any(entry.name == "TemporalPolicyConstraint" for entry in governance_types)

    analytics_exports = enumerate_ir_exports("analytics")
    world_exports = enumerate_ir_exports("world")
    assert any(entry.export_name == "DoWhyGraphBridge" for entry in analytics_exports)
    assert any(entry.export_name == "LatentConfounderContract" for entry in analytics_exports)
    assert any(entry.export_name == "ProvODocument" for entry in world_exports)


def test_schema_catalog_omits_runtime_generic_specialization_in_either_import_order() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = textwrap.dedent(
        """
        import importlib
        import sys

        order = sys.argv[1]
        catalog_module = importlib.import_module("polisyos.ir.schemas.catalog")

        if order == "catalog-first":
            initial = catalog_module.get_ir_schema_catalog()
            initial_fqns = {entry.fqn for entry in initial.types}
            assert "polisyos.ir.connectors.FetchResult" in initial_fqns
            assert "polisyos.ir.connectors.FetchResult[Any]" not in initial_fqns

        federation_module = importlib.import_module("polisyos.fabric.federated_fetch")
        connectors_module = importlib.import_module("polisyos.ir.connectors")
        specialization = vars(connectors_module)["FetchResult[Any]"]
        assert specialization.__pydantic_generic_metadata__["origin"] is connectors_module.FetchResult
        assert federation_module.FederatedFetchResult.__name__ == "FederatedFetchResult"
        assert issubclass(federation_module.FederatedFetchResult, specialization)

        if order == "catalog-first":
            catalog_module.get_ir_schema_catalog.cache_clear()

        catalog = catalog_module.get_ir_schema_catalog()
        fqns = {entry.fqn for entry in catalog.types}
        assert "polisyos.ir.connectors.FetchResult" in fqns
        assert "polisyos.ir.connectors.FetchResult[Any]" not in fqns
        assert "polisyos.ir.kernel.units.MoneyUnit" in fqns
        assert "polisyos.ir.analytics._owner_admission.OwnedJSONRepresentation" in fqns
        """
    )
    env = os.environ.copy()
    python_path = ["src", ".", env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(part for part in python_path if part)

    for order in ("catalog-first", "federation-first"):
        result = subprocess.run(
            [sys.executable, "-c", script, order],
            cwd=repo_root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr or result.stdout


def test_schema_catalog_tolerates_missing_optional_abi_registry(monkeypatch) -> None:
    from polisyos.ir.schemas import catalog as schema_catalog

    monkeypatch.setitem(sys.modules, "polisyos.schemas.abi_models", None)

    assert schema_catalog._collect_abi_entries() == {}


def test_generated_reference_catalog_is_current() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "tools/quality/diagnostics/generate_ir_reference_catalog.py", "--check"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_pre_move_abi_pickle_loads_before_the_live_catalog_consumer() -> None:
    from polisyos.foundry.methods.api import compute_source_fingerprint, compute_source_hash
    from polisyos.schemas import abi_models
    from polisyos.schemas.abi_models import (
        ABI_MODELS,
        ABIModelEntry,
        Priority,
        select_abi_entries,
    )

    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "package_path_compatibility"
        / "runtime_abi_protocol4.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    entry_payload = base64.b64decode(fixture["objects"]["ABIModelEntry"]["pickle_base64"])
    priority_payload = base64.b64decode(fixture["objects"]["Priority"]["pickle_base64"])
    entry = pickle.loads(entry_payload)  # noqa: S301 -- fixed repo-owned pre-move fixture.
    priority = pickle.loads(priority_payload)  # noqa: S301 -- fixed repo-owned pre-move fixture.

    assert type(entry) is ABIModelEntry
    assert type(priority) is Priority
    assert type(entry).__module__ == fixture["objects"]["ABIModelEntry"]["module"]
    assert type(priority).__module__ == fixture["objects"]["Priority"]["module"]
    public_types = (
        Priority,
        abi_models.CompatMode,
        abi_models.Lifecycle,
        abi_models.SchemaMode,
        ABIModelEntry,
    )
    for public_type in public_types:
        source_file = inspect.getsourcefile(public_type)
        assert source_file is not None
        assert Path(source_file).resolve() == Path(abi_models.__file__).resolve()
        assert inspect.getsource(public_type)
        source_hash = compute_source_hash(public_type)
        assert source_hash != "unavailable"
        fingerprint = compute_source_fingerprint(public_type)
        assert fingerprint.source_hash == source_hash
        assert fingerprint.normalized_source_hash is not None
        assert fingerprint.module_file is not None
        assert fingerprint.module_file.replace("\\", "/").endswith(
            "src/polisyos/schemas/abi_models/__init__.py"
        )

    assert all(
        hasattr(abi_models, name)
        for name in (
            "Iterable",
            "dataclass",
            "Enum",
            "Priority",
            "CompatMode",
            "Lifecycle",
            "SchemaMode",
            "ABIModelEntry",
            "IR_ABI_MODELS",
            "FABRIC_ABI_MODELS",
            "SCIENTIST_ABI_MODELS",
            "ABI_MODELS",
            "iter_abi_entries",
            "select_abi_entries",
        )
    )
    assert entry in ABI_MODELS
    additive_abi_keys = {
        "federation_fetch_audit",
        "ate_inference_basis",
        "hte_outcome",
        "hte_point_result",
        "hte_refusal_diagnostic",
        "retained_skg_snapshot_v1_1",
    }
    assert additive_abi_keys <= {model.abi_key for model in ABI_MODELS}
    baseline_abi_models = tuple(
        model for model in ABI_MODELS if model.abi_key not in additive_abi_keys
    )
    assert len(baseline_abi_models) == fixture["baseline"]["abi_count"]
    abi_payload = json.dumps(
        [row.__dict__ for row in baseline_abi_models],
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: value.value,
    ).encode()
    assert (
        hashlib.sha256(abi_payload).hexdigest() == fixture["baseline"]["abi_ordered_entries_sha256"]
    )
    assert (
        sum(
            row.module == "ir" and row.priority is Priority.P0
            for row in select_abi_entries(["ir", "p0"])
        )
        == 16
    )
    assert priority is entry.priority
