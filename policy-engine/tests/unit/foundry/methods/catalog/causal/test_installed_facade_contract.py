"""Actual ABI consumers usable from an installed wheel or rebuilt sdist.

The same tests also run against the source tree. Package isolation is checked
by the external runner, rather than inferred from a successful import here.
"""

from __future__ import annotations

import importlib
import json
import os
import pickle
import pydoc
import subprocess
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal import causal_engine, interference
from polisyos.foundry.methods.catalog.causal.causal_engine import identification
from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery, SourceDomain
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle

PREFIX = "polisyos.foundry.methods.catalog.causal"
COMPATIBILITY = {
    causal_engine.__name__: (
        "_make_dummy_identification_result",
        "mz_id_algorithm",
        "id_with_oracle_fallback",
        "id_star_algorithm",
        "idc_star_algorithm",
    ),
    interference.__name__: (
        "_ReductionErrorBoundPlan",
        "_SimplicialSupportGate",
        "_TopologyCertificatePlan",
    ),
}


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["X", "Y", "Z"],
        edges=[CausalEdge(src=src, dst=dst) for src, dst in [("Z", "X"), ("Z", "Y"), ("X", "Y")]],
    )


@pytest.mark.parametrize("module", [causal_engine, interference])
def test_public_and_retained_private_identity_pickle_and_documentation(module) -> None:
    """Every declared binding remains the canonical object at its serialized FQN."""
    public = tuple(module.__all__)
    compatibility = COMPATIBILITY[module.__name__]
    assert set(public).isdisjoint(compatibility)
    namespace = {}
    exec(f"from {module.__name__} import *", namespace)
    assert set(namespace) - {"__builtins__"} == set(public)
    document = pydoc.plain(pydoc.render_doc(module))
    for name in (*public, *compatibility):
        value = getattr(module, name)
        owner = importlib.import_module(value.__module__)
        canonical = owner
        for component in value.__qualname__.split("."):
            canonical = getattr(canonical, component)
        assert value is canonical
        assert pickle.loads(pickle.dumps(value)) is canonical  # noqa: S301
        imported = {}
        exec(f"from {module.__name__} import {name}", imported)
        assert imported[name] is canonical
        if name in public:
            assert namespace[name] is canonical
            assert name in document


def _identify(binding: str):
    options = {}
    if binding == "mz_id_algorithm":
        options["source_domains"] = [SourceDomain(domain_id="one"), SourceDomain(domain_id="two")]
    elif binding in {"id_star_algorithm", "idc_star_algorithm"}:
        options["counterfactual_query"] = CtfQuery(
            outcome="Y",
            intervention=(("X", 1.0),),
            evidence=(("X", 1.0),) if binding == "idc_star_algorithm" else (),
            kind="ett" if binding == "idc_star_algorithm" else "single_world",
        )
    return causal_engine.CausalEngine().identify("X", "Y", _graph(), **options)


@pytest.mark.parametrize(
    "binding",
    ["mz_id_algorithm", "id_with_oracle_fallback", "id_star_algorithm", "idc_star_algorithm"],
)
def test_each_supported_patch_executes_native_algorithm_and_restores(binding, monkeypatch) -> None:
    """Observe real algorithms through all four historical patch addresses."""
    original = getattr(causal_engine, binding)
    baseline = _identify(binding)
    calls = []

    def observed(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, binding, observed)
        actual = _identify(binding)
        assert len(calls) == 1
        assert actual == baseline
    restored = _identify(binding)
    assert len(calls) == 1
    assert restored == baseline
    assert getattr(identification, binding) is original


@pytest.mark.parametrize("module", [causal_engine, interference])
def test_unknown_and_incidental_names_remain_absent_on_real_reload(module, monkeypatch) -> None:
    """An added leaf import or stale package name cannot widen direct or star ABI."""
    leaf = importlib.import_module(
        module.__name__ + (".artifacts" if module is causal_engine else ".api")
    )
    manifest = tuple(module.__all__)
    name = "INCIDENTAL_INSTALLED_API_IMPORT"
    try:
        with monkeypatch.context() as patch:
            patch.setattr(leaf, name, object(), raising=False)
            module.__dict__[name] = object()
            importlib.reload(module)
            assert tuple(module.__all__) == manifest
            assert not hasattr(module, name)
            with pytest.raises(ImportError):
                exec(f"from {module.__name__} import {name}", {})
    finally:
        module.__dict__.pop(name, None)
        importlib.reload(module)


def test_same_name_wrapper_clone_and_removed_patch_bridge_fail_original_identity_oracle(
    monkeypatch,
) -> None:
    """Names, signatures and __all__ can stay fixed while the actual ABI is lost."""
    owner = importlib.import_module(causal_engine.__name__ + ".api")
    original_class = owner.CausalEngine
    clone = type("CausalEngine", (original_class,), {"__module__": original_class.__module__})
    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, "CausalEngine", clone)
        assert causal_engine.__all__ == ["CausalEngine", "DataReadinessBlockedError"]
        with pytest.raises(AssertionError):
            assert causal_engine.CausalEngine is owner.CausalEngine
    original = causal_engine.id_with_oracle_fallback
    calls = []

    def observed(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, "id_with_oracle_fallback", observed)
        patch.setattr(identification, "_sync_public_algorithm_overrides", lambda: None)
        _identify("id_with_oracle_fallback")
        with pytest.raises(AssertionError):
            assert len(calls) == 1


def test_installed_id_package_executes_identification_and_reopens_persisted_result(
    tmp_path: Path,
) -> None:
    """An actual nonempty package supplies algorithms after empty-shim retirement."""
    package = importlib.import_module(PREFIX + ".id_engine")
    assert Path(package.__file__).name == "__init__.py"
    assert package.__path__
    result = causal_engine.CausalEngine().identify("X", "Y", _graph())
    assert result.status is package.IdentificationStatus.IDENTIFIED
    _, bundle, certificate = causal_engine.CausalEngine().run(
        "X", "Y", _graph(), run_id="installed-package-api"
    )
    assert certificate is None
    assert bundle.identification_status == "identified"
    store = FileSystemCAS(tmp_path / "cas")
    reference = store.put_json(
        bundle,
        PutOptions(kind="research.api.identification", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    reopened = FileSystemCAS(tmp_path / "cas")
    restored = EvidenceBundle.model_validate(from_canonical_bytes(reopened.get_bytes(reference)))
    assert restored == bundle


@pytest.mark.parametrize(
    "address", ["polisyos.foundry.methods.layout", "polisyos.foundry.methods.compiler.layout"]
)
def test_installed_layout_identity_and_real_slot_paths_survive_cas(address, tmp_path: Path) -> None:
    """Both compatibility addresses execute IR builders and preserve fresh readback."""
    module = importlib.import_module(address)
    owner = importlib.import_module("polisyos.ir.kernel.slots")
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY

    for name in (
        "SlotLayout",
        "SlotFamily",
        "SlotFamilyManifest",
        "build_slot_layout",
        "build_slot_family_manifest",
    ):
        assert getattr(module, name) is getattr(owner, name)
    layout = module.build_slot_layout(DEFAULT_SLOT_REGISTRY)
    manifest = module.build_slot_family_manifest(DEFAULT_SLOT_REGISTRY)
    assert layout.layout["agents.income"] == "agents.income"
    assert layout.layout["government.balance"] == "government_balance"
    assert "cells.population" in manifest.families["cells"].slots
    store = FileSystemCAS(tmp_path / "cas")
    reference = store.put_json(
        layout, PutOptions(kind="foundry.slot_layout", media_type="application/json")
    )
    restored = module.SlotLayout.model_validate(
        json.loads(FileSystemCAS(tmp_path / "cas").get_bytes(reference))
    )
    assert type(restored) is owner.SlotLayout
    assert restored == layout


def test_census_walks_immutable_inputs_and_names_computed_import_boundary(tmp_path: Path) -> None:
    """Ignored/outside, changed, binary, unresolved and absent inputs stay distinct."""
    relative = "docs/research/e02-cloud-test-plan/verification/F/api-20261006/census.py"
    supplied = os.environ.get("E02_CENSUS_SCRIPT")
    if supplied:
        path = Path(supplied)
    else:
        path = next(
            parent / relative
            for parent in Path(__file__).resolve().parents
            if (parent / relative).is_file()
        )
    spec = importlib.util.spec_from_file_location("e02_api_census", path)
    assert spec is not None and spec.loader is not None
    instrument = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instrument)
    root = tmp_path / "fixture"
    root.mkdir()

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root).decode().strip()

    git("init", "--quiet")
    git("config", "user.name", "E02 synthetic input fixture")
    git("config", "user.email", "synthetic@example.invalid")
    (root / "caller.py").write_text(
        f"from {PREFIX}.causal_engine import CausalEngine\n"
        "import importlib\n"
        "importlib.import_module('.'.join(['computed', 'address']))\n"
    )
    (root / "docs.md").write_text(f"{PREFIX}.interference.NetworkAIPWEstimator\n")
    (root / "binary.dat").write_bytes(b"\xff\0causal_engine")
    git("add", "caller.py", "docs.md", "binary.dat")
    git("commit", "--quiet", "-m", "freeze complete synthetic inputs")
    first_sha = git("rev-parse", "HEAD")
    (root / "untracked.py").write_text(f"from {PREFIX}.interference import *\n")
    first = instrument.census(root, first_sha)
    assert first["denominator"]["tracked_entries"] == 3
    assert first["denominator"]["python_parsed"] == 1
    assert len(first["literal_imports"]) == 1
    assert first["denominator"]["non_utf8"] == 1
    assert any(
        row["resolution"] == "computed_unresolved" for row in first["dynamic_import_candidates"]
    )
    assert all(row["path"] != "untracked.py" for row in first["lexical_mentions"])
    (root / "caller.py").write_text("pass\n")
    assert instrument.census(root, first_sha)["literal_imports"] == first["literal_imports"]
    git("add", "caller.py")
    git("commit", "--quiet", "-m", "change tracked input")
    second = instrument.census(root, "HEAD")
    assert not second["literal_imports"]
    assert second["tracked_manifest_sha256"] != first["tracked_manifest_sha256"]
    with pytest.raises(subprocess.CalledProcessError):
        instrument.census(root, "refs/e02/absent-input")
