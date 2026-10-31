from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.foundry.compile._lowering import (
    _merge_effective_params,
    audit_trinity_field_coverage,
    lower_trinity,
)


@pytest.mark.parametrize("return_selected_profile", [False, True])
def test_real_lowering_records_each_effective_parameter_child(
    tmp_path, return_selected_profile: bool
) -> None:
    """The persisted lowering exposes real parameter children without changing legacy refs."""
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.contracts.foundry import LoweredIR
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.registry.loader import load_registry_bundle_content
    from polisyos.foundry._internal.quickstart import build_trivial_trinity_bundle
    from polisyos.foundry.compile.trinity_compiler import _link_registries
    from polisyos.ir.linker import link_trinity
    from polisyos.ir.trinity import TrinityBundle

    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=return_selected_profile)
    bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))
    policy = store.put_json(
        bundle,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=TrinityBundle.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        return_selected_profile=return_selected_profile,
    )
    content = load_registry_bundle_content(store, registry.bundle_ref)
    linked, report = link_trinity(bundle, _link_registries(content))
    assert report.ok
    ref, lowered, _ = lower_trinity(
        store,
        policy_ref=policy,
        registry_bundle_ref=registry.bundle_ref,
        bundle=bundle,
        linked_bundle=linked,
        registry_content=content,
        return_selected_profile=return_selected_profile,
    )
    assert lowered.mechanisms
    persisted = validate_core_model_json_artifact(LoweredIR, store, ref)
    manifest = store.get_manifest(ref)
    for mechanism in persisted.mechanisms:
        assert mechanism.effective_params_ref is not None
        expected = input_ref_from_artifact_ref(
            mechanism.effective_params_ref,
            role=f"effective_params:{mechanism.intervention_ids[0]}",
        )
        assert sum(item == expected for item in manifest.inputs) == 1
        assert bool(expected.manifest_profile_sha256) is return_selected_profile


def _artifact_ref(kind: str = "ir") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "a" * 64),
        kind=kind,
        media_type="application/json",
    )


def _make_bundle(
    *,
    interventions=None,
    mechanism_bindings=None,
    hard_constraints=None,
    soft_constraints=None,
    fidelity_level=None,
):
    """Build a minimal mock TrinityBundle."""
    from polisyos.foundry.contracts.fidelity import FidelityLevel

    fidelity = fidelity_level or FidelityLevel.SURROGATE_FLUID

    intervention_mocks = interventions or []
    problem_frame = MagicMock()
    problem_frame.hard_constraints = hard_constraints or []
    problem_frame.soft_constraints = soft_constraints or []

    policy_spec = MagicMock()
    policy_spec.interventions = intervention_mocks
    policy_spec.mechanism_bindings = mechanism_bindings or []
    policy_spec.parameters = []
    policy_spec.global_schedule = None

    model_spec = MagicMock()
    model_spec.fidelity_level = fidelity
    model_spec.time_semantics = None
    model_spec.environment_config = None

    bundle = MagicMock()
    bundle.problem_frame = problem_frame
    bundle.policy_spec = policy_spec
    bundle.model_spec = model_spec
    return bundle


def _make_intervention(intervention_id: str, kind: str, **kwargs):
    mock = MagicMock()
    mock.intervention_id = intervention_id
    mock.kind = kind
    mock.enabled = True
    mock.priority = kwargs.get("priority", 0)
    mock.target = kwargs.get("target")
    mock.params = kwargs.get("params", {})
    mock.schedule = kwargs.get("schedule")
    mock.notes = kwargs.get("notes", [])
    return mock


class TestAuditTrinityFieldCoverage:
    def test_coverage_audit_ok(self) -> None:
        notes = audit_trinity_field_coverage(strict=False)
        assert "trinity_coverage_audit:ok" in notes or any("mismatch" in n for n in notes)

    def test_coverage_audit_returns_list(self) -> None:
        notes = audit_trinity_field_coverage(strict=False)
        assert isinstance(notes, list)
        assert len(notes) >= 1


class TestLowerTrinity:
    @patch("polisyos.foundry.compile._lowering.has_runtime_mechanism_support", return_value=True)
    @patch(
        "polisyos.foundry.compile._lowering.resolve_runtime_fidelity",
        return_value=MagicMock(value="fluid"),
    )
    def test_lower_trinity_produces_mechanisms(self, mock_fidelity, mock_support) -> None:
        intervention = _make_intervention("i1", "flat_tax")
        bundle = _make_bundle(interventions=[intervention])

        linked_bundle = MagicMock()
        linked_intervention = MagicMock()
        linked_intervention.reads_slots = ["income"]
        linked_intervention.writes_slots = ["tax"]
        linked_bundle.bindings.interventions = [linked_intervention]
        linked_intervention.intervention_id = "i1"

        registry_content = MagicMock()
        registry_content.mechanism_registry.mechanisms = {"flat_tax": MagicMock(params={})}
        registry_content.constraint_registry = MagicMock(constraints={})

        store = MagicMock()
        store.put_json.return_value = ArtifactRef(
            artifact_id=ArtifactID("sha256:" + "c" * 64),
            kind="foundry.lowered_ir",
            media_type="application/json",
        )

        ir_ref, lowered_ir, notes = lower_trinity(
            store,
            policy_ref=_artifact_ref("ir"),
            registry_bundle_ref=_artifact_ref("registry"),
            bundle=bundle,
            linked_bundle=linked_bundle,
            registry_content=registry_content,
        )

        assert len(lowered_ir.mechanisms) == 1
        assert lowered_ir.mechanisms[0].mechanism_id == "flat_tax"

    @patch("polisyos.foundry.compile._lowering.has_runtime_mechanism_support", return_value=False)
    def test_lower_trinity_missing_runtime_support_raises(self, mock_support) -> None:
        intervention = _make_intervention("i1", "unknown_mech")
        bundle = _make_bundle(interventions=[intervention])

        linked_bundle = MagicMock()
        linked_bundle.bindings.interventions = []

        registry_content = MagicMock()
        registry_content.mechanism_registry.mechanisms = {}
        registry_content.constraint_registry = MagicMock(constraints={})

        store = MagicMock()

        with pytest.raises(ValueError, match="missing_runtime_mechanism_support"):
            lower_trinity(
                store,
                policy_ref=_artifact_ref("ir"),
                registry_bundle_ref=_artifact_ref("registry"),
                bundle=bundle,
                linked_bundle=linked_bundle,
                registry_content=registry_content,
            )


class TestMergeEffectiveParams:
    def test_includes_mechanism_param_defaults_before_overrides(self) -> None:
        mechanism_spec = SimpleNamespace(
            params={
                "rate": SimpleNamespace(default_value="0.15"),
                "cap": SimpleNamespace(default=10),
            }
        )
        binding = SimpleNamespace(config_overrides={"cap": 20})
        intervention = SimpleNamespace(params={"rate": "0.25"})

        merged = _merge_effective_params(
            mechanism_spec=mechanism_spec,
            binding=binding,
            intervention=intervention,
        )

        assert merged == {"rate": "0.25", "cap": 20}

    @patch("polisyos.foundry.compile._lowering.has_runtime_mechanism_support", return_value=True)
    @patch(
        "polisyos.foundry.compile._lowering.resolve_runtime_fidelity",
        return_value=MagicMock(value="relaxed"),
    )
    def test_lower_trinity_fidelity_resolution(self, mock_fidelity, mock_support) -> None:
        from polisyos.foundry.contracts.fidelity import FidelityLevel

        intervention = _make_intervention("i1", "flat_tax")
        bundle = _make_bundle(
            interventions=[intervention],
            fidelity_level=FidelityLevel.RELAXED_DISCRETE,
        )

        linked_bundle = MagicMock()
        linked_intervention = MagicMock()
        linked_intervention.intervention_id = "i1"
        linked_intervention.reads_slots = []
        linked_intervention.writes_slots = []
        linked_bundle.bindings.interventions = [linked_intervention]

        registry_content = MagicMock()
        registry_content.mechanism_registry.mechanisms = {"flat_tax": MagicMock(params={})}
        registry_content.constraint_registry = MagicMock(constraints={})

        store = MagicMock()
        store.put_json.return_value = ArtifactRef(
            artifact_id=ArtifactID("sha256:" + "c" * 64),
            kind="foundry.lowered_ir",
            media_type="application/json",
        )

        _, lowered_ir, _ = lower_trinity(
            store,
            policy_ref=_artifact_ref("ir"),
            registry_bundle_ref=_artifact_ref("registry"),
            bundle=bundle,
            linked_bundle=linked_bundle,
            registry_content=registry_content,
        )

        assert lowered_ir.mechanisms[0].selected_fidelity == "relaxed"

    @patch("polisyos.foundry.compile._lowering.has_runtime_mechanism_support", return_value=True)
    @patch(
        "polisyos.foundry.compile._lowering.resolve_runtime_fidelity",
        return_value=MagicMock(value="fluid"),
    )
    def test_soft_governance_constraint_without_runtime_semantics_is_not_lowered(
        self,
        mock_fidelity,
        mock_support,
    ) -> None:
        bundle = _make_bundle(
            soft_constraints=[
                SimpleNamespace(
                    constraint_id="wartime_budget_feasibility",
                    slot_id=None,
                    operator=None,
                    value="fiscally_bounded_targeting_required",
                    penalty_weight="1",
                    notes=["requires governance review"],
                )
            ],
        )
        linked_bundle = MagicMock()
        linked_bundle.bindings.interventions = []

        registry_content = MagicMock()
        registry_content.mechanism_registry.mechanisms = {}
        registry_content.constraint_registry = MagicMock(
            constraints={
                "wartime_budget_feasibility": SimpleNamespace(
                    slot_id=None,
                    operator=None,
                    unit_id=None,
                    constraint_type="budget",
                )
            }
        )

        store = MagicMock()
        store.put_json.return_value = ArtifactRef(
            artifact_id=ArtifactID("sha256:" + "d" * 64),
            kind="foundry.lowered_ir",
            media_type="application/json",
        )

        _, lowered_ir, notes = lower_trinity(
            store,
            policy_ref=_artifact_ref("ir"),
            registry_bundle_ref=_artifact_ref("registry"),
            bundle=bundle,
            linked_bundle=linked_bundle,
            registry_content=registry_content,
        )

        assert lowered_ir.constraints == []
        assert "governance_constraint_not_lowered:wartime_budget_feasibility" in notes
