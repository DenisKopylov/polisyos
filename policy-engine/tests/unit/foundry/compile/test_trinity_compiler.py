from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry.builder import build_registry_bundle
from polisyos.core.registry.loader import load_registry_bundle_content
from polisyos.foundry.compile.trinity_compiler import _merge_notes
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SlotRegistry,
)


def _artifact_ref(kind: str = "test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "a" * 64),
        kind=kind,
        media_type="application/json",
    )


def _alternate_manifest_profile(
    store: FileSystemCAS,
    ref: ArtifactRef,
    *,
    version: str,
    source_store: FileSystemCAS | None = None,
) -> ArtifactRef:
    source_store = source_store or store
    manifest = source_store.get_manifest(ref)
    return store.put_bytes(
        source_store.get_bytes(ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component="test.foundry.compiler", version=version),
            env=manifest.env,
            inputs=manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
    )


def test_registry_loader_refuses_foreign_selected_member_profile(tmp_path: Path) -> None:
    root = tmp_path / "registry-cas"
    owner_store = FileSystemCAS(root).for_tenant("tenant-owner")
    foreign_store = FileSystemCAS(root).for_tenant("tenant-foreign")
    bundle = build_registry_bundle(
        owner_store,
        slot_registry=SlotRegistry(),
        merge_registry=MergeRuleRegistry(),
        mechanism_registry=MechanismTypeRegistry(),
        constraint_registry=ConstraintRegistry(),
    )

    foreign_slot_ref = _alternate_manifest_profile(
        foreign_store,
        bundle.slot_registry,
        version="2.0.0",
        source_store=owner_store,
    )
    assert foreign_slot_ref.artifact_id == bundle.slot_registry.artifact_id
    assert foreign_slot_ref.manifest_profile_sha256 is not None
    assert owner_store.get_bytes(bundle.slot_registry) == foreign_store.get_bytes(foreign_slot_ref)

    selected_payload = RegistryBundlePayload(
        slot_registry=foreign_slot_ref,
        merge_registry=bundle.merge_registry,
        constraint_registry=bundle.constraint_registry,
        mechanism_registry=bundle.mechanism_registry,
    )
    selected_bundle_ref = owner_store.put_json(
        selected_payload,
        PutOptions(
            kind="core.registry_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.RegistryBundlePayload", version="1"),
        ),
    )

    owner_payload = RegistryBundlePayload(
        slot_registry=bundle.slot_registry,
        merge_registry=bundle.merge_registry,
        constraint_registry=bundle.constraint_registry,
        mechanism_registry=bundle.mechanism_registry,
    )
    owner_bundle_ref = owner_store.put_json(
        owner_payload,
        PutOptions(
            kind="core.registry_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.RegistryBundlePayload", version="1"),
        ),
    )
    owner_content = load_registry_bundle_content(owner_store, owner_bundle_ref)
    assert isinstance(owner_content.slot_registry, SlotRegistry)

    with pytest.raises(ArtifactOwnershipError):
        load_registry_bundle_content(owner_store, selected_bundle_ref)


def _make_compile_request(
    *,
    registry_bundle_ref=None,
    strict_link=False,
    strict_schema=False,
    strict_conflict_check=False,
    cost_budget_max_total_ms=None,
):
    request = MagicMock()
    request.policy_ref = _artifact_ref("ir")
    request.registry_bundle_ref = registry_bundle_ref
    flags = MagicMock()
    flags.strict_link = strict_link
    flags.strict_schema = strict_schema
    flags.strict_conflict_check = strict_conflict_check
    flags.allow_extra_params = False
    request.validation_flags = flags
    config = MagicMock()
    config.determinism_tier = "strict_cpu"
    config.random_seed = 42
    config.nan_guard_enabled = True
    config.mode = "dev"
    config.jit = True
    config.max_steps = 100
    config.estimate_n_agents = 100
    config.estimate_time_steps = 10
    config.cost_budget_max_total_ms = cost_budget_max_total_ms
    config.cost_budget_max_memory_mb = None
    config.cost_budget_max_compile_ms = None
    config.cost_budget_max_per_mechanism_ms = None
    request.compile_config = config
    return request


class TestCompileTrinityMissing:
    @patch("polisyos.foundry.compile.trinity_compiler.from_canonical_bytes")
    @patch("polisyos.foundry.compile.trinity_compiler.put_compile_report")
    def test_compile_trinity_missing_registry_bundle(
        self,
        mock_put_report,
        mock_canon,
    ) -> None:
        from polisyos.foundry.compile.trinity_compiler import compile_trinity

        mock_canon.return_value = {
            "problem_frame": {"schema_version": "0.1"},
            "policy_spec": {"schema_version": "0.1"},
            "model_spec": {"schema_version": "0.1", "registry_bundle_ref": None},
        }
        mock_put_report.return_value = _artifact_ref("report")

        store = MagicMock()
        store.get_bytes.return_value = b"{}"
        request = _make_compile_request(registry_bundle_ref=None)

        with patch(
            "polisyos.foundry.compile.trinity_compiler.TrinityBundle.model_validate",
        ) as mock_validate:
            mock_bundle = MagicMock()
            mock_bundle.model_spec.registry_bundle_ref = None
            mock_validate.return_value = mock_bundle
            result = compile_trinity(store, request)

        assert result.ok is False
        assert "missing_registry_bundle" in result.notes


class TestCompileTrinityLowering:
    @patch("polisyos.foundry.compile.trinity_compiler.RegistryBundle")
    @patch("polisyos.foundry.compile.trinity_compiler.from_canonical_bytes")
    @patch("polisyos.foundry.compile.trinity_compiler.TrinityBundle.model_validate")
    @patch("polisyos.foundry.compile.trinity_compiler.load_registry_bundle_content")
    @patch("polisyos.foundry.compile.trinity_compiler.link_trinity")
    @patch("polisyos.foundry.compile.trinity_compiler.put_link_report")
    @patch("polisyos.foundry.compile.trinity_compiler.lower_trinity")
    @patch("polisyos.foundry.compile.trinity_compiler.put_compile_report")
    def test_compile_trinity_lowering_exception(
        self,
        mock_put_report,
        mock_lower,
        mock_put_link,
        mock_link,
        mock_load_registry,
        mock_validate,
        mock_canon,
        mock_reg_bundle,
    ) -> None:
        from polisyos.foundry.compile.trinity_compiler import compile_trinity

        mock_canon.return_value = {}
        mock_bundle = MagicMock()
        mock_bundle.model_spec.registry_bundle_ref = "sha256:" + "c" * 64
        mock_validate.return_value = mock_bundle
        mock_load_registry.return_value = MagicMock()

        link_report = MagicMock()
        link_report.ok = True
        link_report.issues = []
        mock_link.return_value = (mock_bundle, link_report)
        mock_put_link.return_value = _artifact_ref("link_report")

        mock_lower.side_effect = ValueError("missing_runtime_mechanism_support:unknown_mech")
        mock_put_report.return_value = _artifact_ref("report")

        store = MagicMock()
        store.get_bytes.return_value = b"{}"
        request = _make_compile_request(registry_bundle_ref=_artifact_ref("registry"))

        result = compile_trinity(store, request)

        assert result.ok is False
        assert any("semantic_lowering_failed" in n for n in result.notes)

    @patch("polisyos.foundry.compile.trinity_compiler.RegistryBundle")
    @patch("polisyos.foundry.compile.trinity_compiler.from_canonical_bytes")
    @patch("polisyos.foundry.compile.trinity_compiler.TrinityBundle.model_validate")
    @patch("polisyos.foundry.compile.trinity_compiler.load_registry_bundle_content")
    @patch("polisyos.foundry.compile.trinity_compiler.link_trinity")
    @patch("polisyos.foundry.compile.trinity_compiler.put_link_report")
    @patch("polisyos.foundry.compile.trinity_compiler.put_compile_report")
    def test_compile_trinity_strict_link_failure(
        self,
        mock_put_report,
        mock_put_link,
        mock_link,
        mock_load_registry,
        mock_validate,
        mock_canon,
        mock_reg_bundle,
    ) -> None:
        from polisyos.foundry.compile.trinity_compiler import compile_trinity

        mock_canon.return_value = {}
        mock_bundle = MagicMock()
        mock_bundle.model_spec.registry_bundle_ref = None
        mock_validate.return_value = mock_bundle
        mock_load_registry.return_value = MagicMock()

        link_report = MagicMock()
        link_report.ok = False
        link_report.issues = []
        mock_link.return_value = (mock_bundle, link_report)
        mock_put_link.return_value = _artifact_ref("link_report")
        mock_put_report.return_value = _artifact_ref("report")

        store = MagicMock()
        store.get_bytes.return_value = b"{}"
        request = _make_compile_request(
            registry_bundle_ref=_artifact_ref("registry"),
            strict_link=True,
        )

        result = compile_trinity(store, request)

        assert result.ok is False
        assert "link_failed" in result.notes


class TestCompileTrinitySuccess:
    def test_compile_trinity_success_all_derived_refs(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        compiler = importlib.import_module("polisyos.foundry.compile.trinity_compiler")
        mock_reg_bundle = MagicMock()
        mock_canon = MagicMock(return_value={})
        mock_validate = MagicMock()
        mock_load_registry = MagicMock(return_value=MagicMock())
        mock_link = MagicMock()
        mock_put_link = MagicMock(return_value=_artifact_ref("link_report"))
        mock_lower = MagicMock()
        mock_build_graph = MagicMock()
        mock_conflict_checker = MagicMock()
        mock_slot_layout = MagicMock()
        mock_treasury = MagicMock()
        mock_put_report = MagicMock(return_value=_artifact_ref("report"))
        monkeypatch.setattr(compiler, "RegistryBundle", mock_reg_bundle)
        monkeypatch.setattr(compiler, "from_canonical_bytes", mock_canon)
        monkeypatch.setattr(compiler.TrinityBundle, "model_validate", mock_validate)
        monkeypatch.setattr(compiler, "load_registry_bundle_content", mock_load_registry)
        monkeypatch.setattr(compiler, "link_trinity", mock_link)
        monkeypatch.setattr(compiler, "put_link_report", mock_put_link)
        monkeypatch.setattr(compiler, "lower_trinity", mock_lower)
        monkeypatch.setattr(compiler, "build_program_graph", mock_build_graph)
        monkeypatch.setattr(compiler, "CompileTimeConflictChecker", mock_conflict_checker)
        monkeypatch.setattr(compiler, "build_slot_layout", mock_slot_layout)
        monkeypatch.setattr(compiler, "build_treasury_plan", mock_treasury)
        monkeypatch.setattr(compiler, "put_compile_report", mock_put_report)
        from polisyos.core.contracts.foundry import LoweredIR, LoweredIRRef, ProgramGraph
        from polisyos.foundry.compile.trinity_compiler import compile_trinity

        mock_canon.return_value = {}
        mock_bundle = MagicMock()
        mock_bundle.model_spec.registry_bundle_ref = None
        mock_validate.return_value = mock_bundle
        mock_load_registry.return_value = MagicMock()

        link_report = MagicMock()
        link_report.ok = True
        link_report.issues = []
        mock_link.return_value = (mock_bundle, link_report)
        mock_put_link.return_value = _artifact_ref("link_report")

        lowered_ir_ref = LoweredIRRef(artifact_id=ArtifactID("sha256:" + "d" * 64))
        lowered_ir = MagicMock(spec=LoweredIR)
        lowered_ir.mechanisms = []
        lowered_ir.constraints = []
        lowered_ir.policy_fidelity_level = "fluid"
        lowered_ir.constraint_mode = "hard_soft_v1"
        mock_lower.return_value = (lowered_ir_ref, lowered_ir, ["trinity_coverage_audit:ok"])

        program_graph = ProgramGraph(
            ir_ref=_artifact_ref("ir"),
            nodes=[],
            edges=[],
            entrypoints=[],
        )
        mock_build_graph.return_value = (program_graph, {})

        conflict_report = MagicMock()
        conflict_report.ok = True
        mock_conflict_checker.return_value.check.return_value = conflict_report

        mock_slot_layout.return_value = MagicMock(schema_version="0.1")
        mock_treasury.return_value = MagicMock(schema_version="0.1")

        artifact_store = FileSystemCAS(tmp_path / "cas")
        policy_ref = artifact_store.put_bytes(
            b"policy",
            PutOptions(
                kind="ir",
                media_type="application/json",
                schema=SchemaInfo(name="test.Trinity", version="1"),
            ),
        )
        registry_ref = artifact_store.put_bytes(
            b"registry",
            PutOptions(
                kind="registry_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="test.RegistryBundle", version="1"),
            ),
        )
        request = _make_compile_request(registry_bundle_ref=registry_ref)
        request.policy_ref = _alternate_manifest_profile(
            artifact_store, policy_ref, version="2.0.0"
        )
        request.registry_bundle_ref = _alternate_manifest_profile(
            artifact_store, registry_ref, version="2.0.0"
        )
        store = MagicMock(wraps=artifact_store)
        store.put_json.return_value = _artifact_ref("stored")
        mock_put_report.return_value = _artifact_ref("report")

        result = compile_trinity(store, request)

        assert result.ok is True
        store.get_bytes.assert_called_once_with(request.policy_ref)
        link_inputs = mock_put_link.call_args.kwargs["inputs"]
        assert [item.manifest_profile_sha256 for item in link_inputs] == [
            request.policy_ref.manifest_profile_sha256,
            request.registry_bundle_ref.manifest_profile_sha256,
        ]
        program_graph_options = next(
            options
            for call in store.put_json.call_args_list
            for options in call.args
            if isinstance(options, PutOptions) and options.kind == "foundry.program_graph"
        )
        assert any(
            item.role == "ir"
            and item.manifest_profile_sha256 == request.policy_ref.manifest_profile_sha256
            for item in program_graph_options.inputs
        )
        assert len(result.derived_refs) == 6
        roles = {d.role for d in result.derived_refs}
        assert roles == {
            "lowered_ir",
            "program_graph",
            "exec_plan",
            "link_report",
            "slot_layout",
            "treasury_plan",
        }


class TestMergeNotes:
    def test_merge_notes_dedup(self) -> None:
        result = _merge_notes(["a", "b", "c"], ["b", "c", "d"])
        assert result == ["a", "b", "c", "d"]

    def test_merge_notes_preserves_order(self) -> None:
        result = _merge_notes(["z", "a"], ["m"])
        assert result == ["z", "a", "m"]

    def test_merge_notes_empty(self) -> None:
        result = _merge_notes([], [])
        assert result == []


def test_trinity_compiler_binds_slot_layout_to_ir_owner() -> None:
    """The compiler must not resolve layout through the compatibility facade."""
    compiler = importlib.import_module("polisyos.foundry.compile.trinity_compiler")
    foundry_facade = importlib.import_module("polisyos.foundry.methods.layout")
    ir_slots = importlib.import_module("polisyos.ir.kernel.slots")
    original = foundry_facade.build_slot_layout
    sentinel = object()

    try:
        foundry_facade.build_slot_layout = sentinel
        reloaded = importlib.reload(compiler)
        assert reloaded.build_slot_layout is ir_slots.build_slot_layout
    finally:
        foundry_facade.build_slot_layout = original
        importlib.reload(compiler)
