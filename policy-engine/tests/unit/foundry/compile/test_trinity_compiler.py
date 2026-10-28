from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    CompileRequest,
    FoundryCompileConfig,
    FoundryValidationFlags,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.registry.builder import build_registry_bundle
from polisyos.core.registry.loader import load_registry_bundle_content
from polisyos.foundry._internal.quickstart import (
    build_trivial_trinity_bundle,
    put_trivial_trinity_bundle,
)
from polisyos.foundry.compile.trinity_compiler import _merge_notes
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleRegistry,
    SlotRegistry,
)
from polisyos.ir.linker.reports import LinkIssueCode, LinkReport
from polisyos.ir.trinity import TrinityBundle


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


def test_compile_rejects_trinity_payload_version_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.foundry.compile import trinity_compiler

    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_trivial_trinity_bundle("sha256:" + "1" * 64)
    payload = bundle.model_dump(mode="json")
    payload["schema_version"] = "1.1"
    policy_ref = store.put_json(
        payload,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    request = _make_compile_request(policy_ref)
    monkeypatch.setattr(trinity_compiler, "_resolve_registry_bundle_ref", lambda *_: None)

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_mismatch",
    ):
        trinity_compiler.compile_trinity(store, request)


def _make_compile_request(
    policy_ref: ArtifactRef,
    *,
    registry_bundle_ref: ArtifactRef | None = None,
    strict_link: bool = False,
    strict_schema: bool = False,
    strict_conflict_check: bool = False,
    cost_budget_max_total_ms: int | None = None,
    return_selected_profile: bool = False,
) -> CompileRequest:
    """Build the current typed request with its real empty metric inventory."""
    return CompileRequest(
        input_kind="trinity",
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        compile_config=FoundryCompileConfig(
            determinism_tier="strict_cpu",
            random_seed=42,
            nan_guard_enabled=True,
            mode="dev",
            jit=True,
            max_steps=100,
            estimate_n_agents=100,
            estimate_time_steps=10,
            cost_budget_max_total_ms=cost_budget_max_total_ms,
        ),
        validation_flags=FoundryValidationFlags(
            strict_link=strict_link,
            strict_schema=strict_schema,
            strict_conflict_check=strict_conflict_check,
            allow_extra_params=False,
        ),
        return_selected_profile=return_selected_profile,
    )


class TestCompileTrinityMissing:
    def test_compile_trinity_missing_registry_bundle(self, tmp_path: Path) -> None:
        from polisyos.foundry.compile.trinity_compiler import compile_trinity

        store = FileSystemCAS(tmp_path / "cas")
        bundle = build_trivial_trinity_bundle("sha256:" + "c" * 64)
        payload = bundle.model_dump(mode="python")
        payload["model_spec"]["registry_bundle_ref"] = None
        bundle_without_registry = TrinityBundle.model_validate(payload)
        policy_ref = put_trivial_trinity_bundle(store, bundle_without_registry)
        result = compile_trinity(store, _make_compile_request(policy_ref))

        assert result.ok is False
        assert "missing_registry_bundle" in result.notes


class TestCompileTrinityLowering:
    def test_compile_trinity_lowering_exception(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polisyos.foundry.compile import trinity_compiler

        store = FileSystemCAS(tmp_path / "cas")
        registry = build_default_registry_bundle(store)
        bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))
        policy_ref = put_trivial_trinity_bundle(store, bundle)
        request = _make_compile_request(policy_ref, registry_bundle_ref=registry.bundle_ref)
        lowering_calls: list[None] = []

        def fail_lowering(*_args: object, **_kwargs: object) -> None:
            lowering_calls.append(None)
            raise ValueError("missing_runtime_mechanism_support:unknown_mech")

        monkeypatch.setattr(trinity_compiler, "lower_trinity", fail_lowering)
        result = trinity_compiler.compile_trinity(store, request)

        assert lowering_calls == [None]
        assert result.ok is False
        assert any("semantic_lowering_failed" in note for note in result.notes)

    def test_compile_trinity_strict_link_failure(self, tmp_path: Path) -> None:
        from polisyos.foundry.compile import trinity_compiler

        store = FileSystemCAS(tmp_path / "cas")
        registry = build_default_registry_bundle(store)
        bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))
        payload = bundle.model_dump(mode="python")
        payload["policy_spec"]["interventions"][0]["kind"] = "unknown_mech"
        invalid_bundle = TrinityBundle.model_validate(payload)
        policy_ref = put_trivial_trinity_bundle(store, invalid_bundle)
        request = _make_compile_request(
            policy_ref,
            registry_bundle_ref=registry.bundle_ref,
            strict_link=True,
        )

        result = trinity_compiler.compile_trinity(store, request)

        assert result.ok is False
        assert "link_failed" in result.notes
        link_report_ref = next(
            derived.ref for derived in result.derived_refs if derived.role == "link_report"
        )
        link_report = LinkReport.model_validate(
            from_canonical_bytes(store.get_bytes(link_report_ref))
        )
        assert link_report.ok is False
        assert any(issue.code == LinkIssueCode.UNKNOWN_MECHANISM for issue in link_report.issues)


class TestCompileTrinitySuccess:
    def test_compile_trinity_success_all_derived_refs(self, tmp_path: Path) -> None:
        compiler = importlib.import_module("polisyos.foundry.compile.trinity_compiler")
        store = FileSystemCAS(tmp_path / "cas")
        registry = build_default_registry_bundle(store)
        bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))
        policy_ref = put_trivial_trinity_bundle(store, bundle)
        selected_policy_ref = _alternate_manifest_profile(store, policy_ref, version="2.0.0")
        selected_registry_ref = _alternate_manifest_profile(
            store,
            registry.bundle_ref,
            version="2.0.0",
        )
        request = _make_compile_request(
            selected_policy_ref,
            registry_bundle_ref=selected_registry_ref,
            return_selected_profile=True,
        )

        result = compiler.compile_trinity(store, request)

        assert result.ok is True
        assert result.exec_plan_ref is not None
        link_report_ref = next(
            derived.ref for derived in result.derived_refs if derived.role == "link_report"
        )
        link_inputs = store.get_manifest(link_report_ref).inputs
        assert [item.manifest_profile_sha256 for item in link_inputs] == [
            selected_policy_ref.manifest_profile_sha256,
            selected_registry_ref.manifest_profile_sha256,
        ]
        program_graph_ref = next(
            derived.ref for derived in result.derived_refs if derived.role == "program_graph"
        )
        program_graph_inputs = store.get_manifest(program_graph_ref).inputs
        assert any(
            item.role == "ir"
            and item.manifest_profile_sha256 == selected_policy_ref.manifest_profile_sha256
            for item in program_graph_inputs
        )
        treasury_ref = next(
            derived.ref for derived in result.derived_refs if derived.role == "treasury_plan"
        )
        assert store.get_manifest(result.exec_plan_ref).inputs == [
            input_ref_from_artifact_ref(program_graph_ref, role="program_graph"),
            input_ref_from_artifact_ref(treasury_ref, role="treasury_plan"),
        ]
        assert len(result.derived_refs) == 6
        roles = {derived.role for derived in result.derived_refs}
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
