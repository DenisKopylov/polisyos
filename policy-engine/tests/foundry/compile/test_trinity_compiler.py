from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import CompileResult

from polisyos.foundry.compile.trinity_compiler import _merge_notes


def _artifact_ref(kind: str = "test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "a" * 64),
        kind=kind,
        media_type="application/json",
    )


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
        self, mock_put_report, mock_canon,
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
            registry_bundle_ref=_artifact_ref("registry"), strict_link=True,
        )

        result = compile_trinity(store, request)

        assert result.ok is False
        assert "link_failed" in result.notes


class TestCompileTrinitySuccess:
    @patch("polisyos.foundry.compile.trinity_compiler.RegistryBundle")
    @patch("polisyos.foundry.compile.trinity_compiler.from_canonical_bytes")
    @patch("polisyos.foundry.compile.trinity_compiler.TrinityBundle.model_validate")
    @patch("polisyos.foundry.compile.trinity_compiler.load_registry_bundle_content")
    @patch("polisyos.foundry.compile.trinity_compiler.link_trinity")
    @patch("polisyos.foundry.compile.trinity_compiler.put_link_report")
    @patch("polisyos.foundry.compile.trinity_compiler.lower_trinity")
    @patch("polisyos.foundry.compile.trinity_compiler.build_program_graph")
    @patch("polisyos.foundry.compile.trinity_compiler.CompileTimeConflictChecker")
    @patch("polisyos.foundry.compile.trinity_compiler.build_slot_layout")
    @patch("polisyos.foundry.compile.trinity_compiler.build_treasury_plan")
    @patch("polisyos.foundry.compile.trinity_compiler.put_compile_report")
    def test_compile_trinity_success_all_derived_refs(
        self,
        mock_put_report,
        mock_treasury,
        mock_slot_layout,
        mock_conflict_checker,
        mock_build_graph,
        mock_lower,
        mock_put_link,
        mock_link,
        mock_load_registry,
        mock_validate,
        mock_canon,
        mock_reg_bundle,
    ) -> None:
        from polisyos.foundry.compile.trinity_compiler import compile_trinity
        from polisyos.core.contracts.foundry import LoweredIR, LoweredIRRef, ProgramGraph

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

        store = MagicMock()
        store.get_bytes.return_value = b"{}"
        store.put_json.return_value = _artifact_ref("stored")
        mock_put_report.return_value = _artifact_ref("report")

        request = _make_compile_request(registry_bundle_ref=_artifact_ref("registry"))

        result = compile_trinity(store, request)

        assert result.ok is True
        assert len(result.derived_refs) == 6
        roles = {d.role for d in result.derived_refs}
        assert roles == {
            "lowered_ir", "program_graph", "exec_plan",
            "link_report", "slot_layout", "treasury_plan",
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
