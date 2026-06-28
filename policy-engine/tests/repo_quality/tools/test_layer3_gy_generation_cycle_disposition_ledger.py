from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tools.quality.validation import check_layer3_gy_generation_cycle_disposition_ledger

REPO_ROOT = Path(__file__).resolve().parents[3]


def _issue_codes(report: dict[str, object]) -> set[str]:
    issues = report.get("issues")
    assert isinstance(issues, list)
    return {
        str(issue.get("code"))
        for issue in issues
        if isinstance(issue, dict) and issue.get("code")
    }


def _loaded_ledger() -> dict[str, object]:
    return check_layer3_gy_generation_cycle_disposition_ledger.load_ledger(REPO_ROOT)


def _disposition_counts(ledger: dict[str, object]) -> dict[str, int]:
    owners = ledger["owners"]
    assert isinstance(owners, list)
    counts = dict.fromkeys(
        check_layer3_gy_generation_cycle_disposition_ledger.DISPOSITIONS,
        0,
    )
    for owner in owners:
        assert isinstance(owner, dict)
        disposition = owner.get("disposition")
        assert isinstance(disposition, str)
        assert disposition in counts
        counts[disposition] += 1
    return counts


def _remove_owner_everywhere(ledger: dict[str, object], owner_id: str) -> None:
    owners = ledger["owners"]
    assert isinstance(owners, list)
    ledger["owners"] = [
        owner for owner in owners if isinstance(owner, dict) and owner.get("owner_id") != owner_id
    ]
    mapping = ledger["task_owner_mapping"]
    assert isinstance(mapping, dict)
    for row in mapping.values():
        assert isinstance(row, dict)
        owner_ids = row.get("owner_ids")
        assert isinstance(owner_ids, list)
        row["owner_ids"] = [mapped_owner for mapped_owner in owner_ids if mapped_owner != owner_id]


def _owner_by_id(ledger: dict[str, object], owner_id: str) -> dict[str, object]:
    owners = ledger["owners"]
    assert isinstance(owners, list)
    for owner in owners:
        assert isinstance(owner, dict)
        if owner.get("owner_id") == owner_id:
            return owner
    raise AssertionError(f"owner not found: {owner_id}")


def test_layer3_gy_generation_cycle_disposition_ledger_is_recomputed_green() -> None:
    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)
    ledger = _loaded_ledger()
    owners = ledger["owners"]
    assert isinstance(owners, list)

    assert report["status"] == "pass"
    assert report["summary"]["disposition_counts"] == _disposition_counts(ledger)
    assert report["summary"]["owner_count"] == len(owners)
    assert report["summary"]["pending_strangle_obligations"] > 0
    assert report["summary"]["landed_strangle_obligations_checked"] >= 6
    assert report["summary"]["strangled_obligations_checked"] >= 6
    assert report["summary"]["task_mapping_missing_owner_count"] == 0
    tasks = ledger["tasks"]
    assert isinstance(tasks, dict)
    assert tasks["GY-N1"]["status"] == "landed"
    assert tasks["GY-N2"]["status"] == "landed"
    assert tasks["GY-S0"]["status"] == "landed"
    assert tasks["GY-S1"]["status"] == "landed"
    assert tasks["GY-N-V"]["status"] == "landed"
    assert report["method_availability_gate"]["decision"] == "stay_on_python_3_14"
    assert report["method_availability_gate"]["expected_unavailable"] == [
        "dowhy",
        "econml",
    ]
    assert report["method_availability_gate"]["expected_optional_available"] == [
        "cvxpy",
    ]
    assert report["method_availability_gate"]["expected_available"] == [
        "foundry_bayesian_bvar",
        "foundry_bayesian_variational",
        "foundry_transport",
        "jax",
        "pymoo",
        "scipy",
        "statsmodels",
    ]


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_fabricated_owner_anchor() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    owners = mutated["owners"]
    assert isinstance(owners, list)
    fabricated = copy.deepcopy(owners[0])
    fabricated["owner_id"] = "fabricated_parallel_owner_probe"
    fabricated["owner_path"] = "src/polisyos/does/not/exist.py:999"
    owners.append(fabricated)

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "owner_anchor_unresolved" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_landed_unstrangled_owner() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    tasks = mutated["tasks"]
    assert isinstance(tasks, dict)
    task = tasks["GY-N6"]
    assert isinstance(task, dict)
    task["status"] = "landed"

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_gy_n1_old_path_live() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    owners = mutated["owners"]
    assert isinstance(owners, list)
    for owner in owners:
        if (
            isinstance(owner, dict)
            and owner.get("owner_id") == "workspace_run_intent_cycle_adapter"
        ):
            receipt = owner["strangle_receipt"]
            assert isinstance(receipt, dict)
            receipt["strangle_condition"] = {
                "kind": "text_absent",
                "path": "src/polisyos/runtime/quality/workspace/loop.py",
                "pattern": "run_intent",
            }
            break
    else:
        raise AssertionError("workspace_run_intent_cycle_adapter owner missing")

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_gy_n2_free_form_only_link() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    owner = _owner_by_id(mutated, "intervention_atom_binding_bridge")
    receipt = owner["strangle_receipt"]
    assert isinstance(receipt, dict)
    receipt["strangle_condition"] = {
        "kind": "text_absent_under",
        "root": "src/polisyos",
        "pattern": "measurement_expectations",
        "suffixes": [".py"],
    }

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_gy_n2_missing_atom_consumption() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    owner = _owner_by_id(mutated, "trinity_candidate_search_bridge")
    receipt = owner["strangle_receipt"]
    assert isinstance(receipt, dict)
    receipt["strangle_condition"] = {
        "kind": "text_absent_under",
        "root": "src/polisyos",
        "pattern": "consume_intervention_atom_for_cycle",
        "suffixes": [".py"],
    }

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_gy_n3_parallel_world_store() -> None:
    probe = REPO_ROOT / "src/polisyos/runtime/quality/parallel_world_store_probe.py"
    try:
        probe.write_text(
            "class ParallelWorldStore:\n"
            "    pass\n",
            encoding="utf-8",
        )

        report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

        assert report["status"] == "fail"
        assert "landed_owner_not_strangled" in _issue_codes(report)
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_gy_n3_synthetic_world_promotion() -> None:
    probe = REPO_ROOT / "src/polisyos/runtime/quality/synthetic_world_production_probe.py"
    try:
        probe.write_text(
            "from polisyos.foundry.agent_sim.world import SyntheticWorld\n",
            encoding="utf-8",
        )

        report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

        assert report["status"] == "fail"
        assert "landed_owner_not_strangled" in _issue_codes(report)
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_hardcoded_substrate_source_list() -> None:
    probe = REPO_ROOT / "src/polisyos/runtime/quality/substrate_hardcoded_source_probe.py"
    try:
        probe.write_text(
            "HARDCODED_SUBSTRATE_SOURCE_IDS = ['worldbank']\n",
            encoding="utf-8",
        )

        report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

        assert report["status"] == "fail"
        assert "landed_owner_not_strangled" in _issue_codes(report)
    finally:
        probe.unlink(missing_ok=True)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_uncapped_substrate_trust_bounds(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import substrate_registry

    def tier_name_presence_only(
        self,
        registration,
        *,
        expected_tier=None,
    ) -> None:
        tier = expected_tier or self.trust_tiers.get(registration.trust_tier.tier)
        if tier is None:
            raise substrate_registry.SubstrateRegistryError(
                "substrate_trust_tier_unresolved",
                f"unknown trust_tier {registration.trust_tier.tier}",
            )

    monkeypatch.setattr(
        substrate_registry.L5CatalogAuthority,
        "validate_trust_tier_bounds",
        tier_name_presence_only,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


@pytest.mark.parametrize(
    "removed_check",
    [
        pytest.param("coverage"),
        pytest.param("identification"),
        pytest.param("coverage_and_identification"),
        pytest.param("known_expected_tier"),
        pytest.param("schema_regime"),
    ],
)
def test_layer3_gy_generation_cycle_disposition_ledger_rejects_uncapped_known_family_honesty(
    monkeypatch,
    removed_check: str,
) -> None:
    from polisyos.runtime.quality import substrate_registry

    def validate_with_removed_known_family_check(self, registration) -> None:
        family_id = registration.family_id
        self.validate_trust_tier_bounds(registration)
        if family_id in self.coverage_rules:
            if removed_check not in {"coverage", "coverage_and_identification"}:
                allowed_coverage = float(self.coverage_rules[family_id])
                if registration.coverage.coverage_score > allowed_coverage + 1e-9:
                    raise substrate_registry.SubstrateRegistryError(
                        "substrate_coverage_inflated",
                        f"{family_id}: {registration.coverage.coverage_score} > {allowed_coverage}",
                    )
            if removed_check not in {"identification", "coverage_and_identification"}:
                expected_identification = self.identification_modes.get(family_id)
                if (
                    expected_identification is not None
                    and registration.identification_mode != expected_identification
                ):
                    raise substrate_registry.SubstrateRegistryError(
                        "substrate_identification_mode_inflated",
                        f"{family_id}: {registration.identification_mode} != {expected_identification}",
                    )
            if removed_check != "known_expected_tier":
                expected_tier = self.expected_trust_tier(family_id)
                self.validate_trust_tier_bounds(registration, expected_tier=expected_tier)
        if removed_check != "schema_regime":
            if (
                registration.schema_regime.schema_regime_id not in self.schema_regimes
                and not registration.schema_regime.schema_regime_id.startswith("dcat:")
                and not registration.schema_regime.schema_regime_id.startswith("manifest:")
            ):
                raise substrate_registry.SubstrateRegistryError(
                    "substrate_schema_regime_unresolved",
                    registration.schema_regime.schema_regime_id,
                )

    monkeypatch.setattr(
        substrate_registry.L5CatalogAuthority,
        "validate_registration",
        validate_with_removed_known_family_check,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_unexercised_substrate_runtime_property(
    monkeypatch,
) -> None:
    from tools.quality.validation import check_production_data_substrate_registry_contract

    original = (
        check_production_data_substrate_registry_contract
        ._substrate_registry_runtime_honesty_properties
    )

    def with_future_runtime_property(repo_root: Path) -> dict[str, str]:
        properties = dict(original(repo_root))
        properties["runtime_code:substrate_future_honesty"] = "substrate_future_honesty"
        return properties

    monkeypatch.setattr(
        check_production_data_substrate_registry_contract,
        "_substrate_registry_runtime_honesty_properties",
        with_future_runtime_property,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_partial_atom_round_trip(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.InterventionAtomBinding.to_trinity_intervention_spec

    def drop_non_key_trinity_field(self):
        return original(self).model_copy(update={"lex_provision_ref": None})

    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_trinity_intervention_spec",
        drop_non_key_trinity_field,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("identification_mode", None),
        ("strategic_response_expected", False),
    ],
)
def test_layer3_gy_generation_cycle_disposition_ledger_rejects_non_default_trinity_field_drop(
    monkeypatch,
    field_name: str,
    bad_value: object,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.InterventionAtomBinding.to_trinity_intervention_spec

    def drop_non_default_trinity_field(self):
        return original(self).model_copy(update={field_name: bad_value})

    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_trinity_intervention_spec",
        drop_non_default_trinity_field,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_corrupt_estimand_source_population(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.build_intervention_atom_binding

    def wrong_source_population(**kwargs):
        kwargs["source_population"] = "corrupted_source_population"
        return original(**kwargs)

    monkeypatch.setattr(
        intervention_atom_binding,
        "build_intervention_atom_binding",
        wrong_source_population,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_corrupt_identification_plan_backend(
    monkeypatch,
) -> None:
    from polisyos.ir.analytics.interventions import IdentificationBackend
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.build_intervention_atom_binding

    def wrong_identification_backend(**kwargs):
        plan = kwargs["identification_plan"]
        kwargs["identification_plan"] = plan.model_copy(
            update={"backend": IdentificationBackend.TYPECHECK}
        )
        return original(**kwargs)

    monkeypatch.setattr(
        intervention_atom_binding,
        "build_intervention_atom_binding",
        wrong_identification_backend,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_intervention_atom_round_trip_compares_complete_atom_schema(monkeypatch) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.build_intervention_atom_binding

    def corrupt_atom_field(atom, field_name: str):
        if field_name == "atom_id":
            return atom.model_copy(update={"atom_id": "atom_" + "f" * 16})
        if field_name == "schema_version":
            return atom.model_copy(update={"schema_version": "corrupt.schema.v1"})
        if field_name == "problem_frame_ref":
            return atom.model_copy(update={"problem_frame_ref": "sha256:" + "d" * 64})
        if field_name == "policy_spec_ref":
            return atom.model_copy(update={"policy_spec_ref": "sha256:" + "e" * 64})
        if field_name == "intervention_id":
            return atom.model_copy(update={"intervention_id": "corrupt_intervention"})
        if field_name == "operator_kind":
            return atom.model_copy(
                update={
                    "operator_kind": atom.operator_kind.model_copy(
                        update={"trinity_kind": "corrupt_kind"}
                    )
                }
            )
        if field_name == "target_selector":
            return atom.model_copy(
                update={
                    "target_selector": atom.target_selector.model_copy(
                        update={"target_population_type": "corrupt_population"}
                    )
                }
            )
        if field_name == "target_world_slots":
            return atom.model_copy(update={"target_world_slots": ("agents.wealth",)})
        if field_name == "read_slots":
            return atom.model_copy(update={"read_slots": ("agents.employment",)})
        if field_name == "direct_effect_bundle":
            return atom.model_copy(
                update={
                    "direct_effect_bundle": atom.direct_effect_bundle.model_copy(
                        update={"mechanism_id": "corrupt_mechanism"}
                    )
                }
            )
        if field_name == "causal_do_expr":
            return atom.model_copy(
                update={
                    "causal_do_expr": atom.causal_do_expr.model_copy(
                        update={"write_variables": ("agents.wealth",)}
                    )
                }
            )
        if field_name == "intended_downstream_estimand":
            return atom.model_copy(
                update={
                    "intended_downstream_estimand": (
                        atom.intended_downstream_estimand.model_copy(
                            update={"source_population": "corrupt_source_population"}
                        )
                    )
                }
            )
        if field_name == "causal_path_or_identification_plan_ref":
            return atom.model_copy(
                update={
                    "causal_path_or_identification_plan_ref": (
                        atom.causal_path_or_identification_plan_ref.model_copy(
                            update={"backend": "corrupt_backend"}
                        )
                    )
                }
            )
        if field_name == "world_model_record_ref":
            return atom.model_copy(update={"world_model_record_ref": "corrupt_world_model"})
        if field_name == "measurement_expectations":
            return atom.model_copy(
                update={"measurement_expectations": {"corrupt": "expectation"}}
            )
        if field_name == "measurement_expectations_authority":
            return atom.model_copy(
                update={"measurement_expectations_authority": "corrupt_authority"}
            )
        if field_name == "content_hash":
            return atom.model_copy(update={"content_hash": "sha256:" + "f" * 64})
        if field_name == "producer_ref":
            return atom.model_copy(update={"producer_ref": "corrupt:producer"})
        if field_name == "provenance_refs":
            return atom.model_copy(update={"provenance_refs": ("corrupt:provenance",)})
        if field_name == "status":
            return atom.model_copy(update={"status": "blocked"})
        raise AssertionError(f"unhandled atom field: {field_name}")

    for field_name in intervention_atom_binding.InterventionAtomBinding.model_fields:
        monkeypatch.setattr(
            intervention_atom_binding,
            "build_intervention_atom_binding",
            lambda field_name=field_name, **kwargs: corrupt_atom_field(
                original(**kwargs),
                field_name,
            ),
        )

        round_trip = (
            check_layer3_gy_generation_cycle_disposition_ledger
            ._intervention_atom_binding_round_trip_report()
        )

        assert round_trip["status"] == "fail", field_name
        assert any(
            issue.get("code") == "intervention_atom_binding_round_trip_field_mismatch"
            for issue in round_trip["issues"]
        ), field_name

    monkeypatch.setattr(
        intervention_atom_binding,
        "build_intervention_atom_binding",
        original,
    )


def test_intervention_atom_round_trip_rejects_uncompared_atom_field(monkeypatch) -> None:
    original_sample = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._sample_intervention_atom_binding_inputs
    )

    def sample_missing_expected_field() -> dict[str, object]:
        sample = dict(original_sample())
        expected = dict(sample["expected_atom_dump"])
        expected.pop("producer_ref")
        sample["expected_atom_dump"] = expected
        return sample

    monkeypatch.setattr(
        check_layer3_gy_generation_cycle_disposition_ledger,
        "_sample_intervention_atom_binding_inputs",
        sample_missing_expected_field,
    )

    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )

    assert round_trip["status"] == "fail"
    assert any(
        issue.get("code")
        == "intervention_atom_binding_round_trip_field_coverage_incomplete"
        for issue in round_trip["issues"]
    )


def test_intervention_atom_round_trip_sample_uses_non_default_projection_values() -> None:
    from polisyos.ir.analytics.interventions import QueryTargetKind

    sample = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._sample_intervention_atom_binding_inputs()
    )
    intervention = sample["intervention"]
    causal = sample["causal"]
    query_target = sample["query_target"]
    causal_context = sample["causal_context"]
    identification_plan = sample["identification_plan"]
    atom = sample["atom"]

    assert intervention.enabled is False
    assert intervention.schedule.end_step == 6
    assert causal.assignments[0].value is not None
    assert query_target.target_kind is QueryTargetKind.CONTRAST
    assert causal_context.interaction_complex_ref is not None
    assert causal_context.interference_certificate_ref is not None
    assert identification_plan.conditions[0].required is False
    assert atom.status == "grounded"
    assert atom.direct_effect_bundle.enabled is False
    assert atom.direct_effect_bundle.schedule["end_step"] == 6
    assert atom.causal_do_expr.assignments[0].value is not None
    assert atom.intended_downstream_estimand.target_kind is QueryTargetKind.CONTRAST
    sample_non_default = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_sample_non_default_report(sample)
    )
    assert sample_non_default["status"] == "pass"
    assert set(sample_non_default["justified_default_fields"]) == set(
        sample_non_default["required_justified_default_fields"]
    )


def test_intervention_atom_round_trip_sample_default_meta_rejects_unjustified_default(
    monkeypatch,
) -> None:
    original_sample = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._sample_intervention_atom_binding_inputs
    )

    def sample_with_default_schedule_end_step() -> dict[str, object]:
        sample = dict(original_sample())
        intervention = sample["intervention"]
        schedule = intervention.schedule.model_copy(update={"end_step": None})
        sample["intervention"] = intervention.model_copy(update={"schedule": schedule})
        return sample

    monkeypatch.setattr(
        check_layer3_gy_generation_cycle_disposition_ledger,
        "_sample_intervention_atom_binding_inputs",
        sample_with_default_schedule_end_step,
    )

    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )
    assert round_trip["status"] == "fail"
    assert any(
        issue.get("code") == "intervention_atom_binding_sample_default_unjustified"
        and issue.get("field_path") == "intervention.schedule.end_step"
        for issue in round_trip["issues"]
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)
    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


def test_intervention_atom_round_trip_sample_roots_are_derived_from_sample_objects(
    monkeypatch,
) -> None:
    from pydantic import BaseModel, ConfigDict

    class FutureRoundTripRoot(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        root_id: str
        enabled: bool = True

    original_sample = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._sample_intervention_atom_binding_inputs
    )

    def sample_with_future_round_trip_root() -> dict[str, object]:
        sample = dict(original_sample())
        sample["future_round_trip_root"] = FutureRoundTripRoot(root_id="future_root")
        return sample

    monkeypatch.setattr(
        check_layer3_gy_generation_cycle_disposition_ledger,
        "_sample_intervention_atom_binding_inputs",
        sample_with_future_round_trip_root,
    )

    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )

    assert round_trip["status"] == "fail"
    assert any(
        issue.get("code") == "intervention_atom_binding_sample_default_unjustified"
        and issue.get("field_path") == "future_round_trip_root.enabled"
        for issue in round_trip["issues"]
    )


@pytest.mark.parametrize("bad_end_step", [None, 9])
def test_layer3_gy_generation_cycle_disposition_ledger_rejects_schedule_end_step_drop_or_corruption(
    monkeypatch,
    bad_end_step: int | None,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.InterventionAtomBinding.to_trinity_intervention_spec

    def drop_schedule_end_step_to_default(self):
        trinity = original(self)
        return trinity.model_copy(
            update={"schedule": trinity.schedule.model_copy(update={"end_step": bad_end_step})}
        )

    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_trinity_intervention_spec",
        drop_schedule_end_step_to_default,
    )

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate(REPO_ROOT)

    assert report["status"] == "fail"
    assert "landed_owner_not_strangled" in _issue_codes(report)


@pytest.mark.parametrize(
    "context_field",
    [
        "interaction_complex_ref",
        "interference_certificate_ref",
    ],
)
def test_intervention_atom_round_trip_rejects_nested_context_default_drops(
    monkeypatch,
    context_field: str,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.build_intervention_atom_binding

    def drop_context_ref_to_default(**kwargs):
        context = kwargs["causal_context"]
        kwargs["causal_context"] = context.model_copy(update={context_field: None})
        return original(**kwargs)

    monkeypatch.setattr(
        intervention_atom_binding,
        "build_intervention_atom_binding",
        drop_context_ref_to_default,
    )

    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )

    assert round_trip["status"] == "fail"
    assert any(
        issue.get("code") == "intervention_atom_binding_round_trip_field_mismatch"
        and issue.get("field") == "causal_do_expr"
        for issue in round_trip["issues"]
    )


@pytest.mark.parametrize(
    ("context_field", "ref_class_name", "artifact_digit"),
    [
        ("interaction_complex_ref", "InteractionComplexRef", "6"),
        ("interference_certificate_ref", "InterferenceCertificateRef", "7"),
    ],
)
def test_intervention_atom_round_trip_rejects_nested_context_corruptions(
    monkeypatch,
    context_field: str,
    ref_class_name: str,
    artifact_digit: str,
) -> None:
    from polisyos.ir.registry import refs
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.build_intervention_atom_binding
    ref_class = getattr(refs, ref_class_name)

    def corrupt_context_ref(**kwargs):
        context = kwargs["causal_context"]
        kwargs["causal_context"] = context.model_copy(
            update={context_field: ref_class(artifact_id="sha256:" + artifact_digit * 64)}
        )
        return original(**kwargs)

    monkeypatch.setattr(
        intervention_atom_binding,
        "build_intervention_atom_binding",
        corrupt_context_ref,
    )

    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )

    assert round_trip["status"] == "fail"
    assert any(
        issue.get("code") == "intervention_atom_binding_round_trip_field_mismatch"
        and issue.get("field") == "causal_do_expr"
        for issue in round_trip["issues"]
    )


def test_intervention_atom_round_trip_rejects_identification_condition_default_drop(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original = intervention_atom_binding.build_intervention_atom_binding

    def drop_identification_condition_required_to_default(**kwargs):
        plan = kwargs["identification_plan"]
        conditions = tuple(
            condition.model_copy(update={"required": True})
            if index == 0
            else condition
            for index, condition in enumerate(plan.conditions)
        )
        kwargs["identification_plan"] = plan.model_copy(update={"conditions": conditions})
        return original(**kwargs)

    monkeypatch.setattr(
        intervention_atom_binding,
        "build_intervention_atom_binding",
        drop_identification_condition_required_to_default,
    )

    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )

    assert round_trip["status"] == "fail"
    assert any(
        issue.get("code") == "intervention_atom_binding_round_trip_field_mismatch"
        and issue.get("field") == "causal_path_or_identification_plan_ref"
        for issue in round_trip["issues"]
    )


def test_intervention_atom_round_trip_rejects_default_field_projection_drops(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import intervention_atom_binding

    original_trinity = intervention_atom_binding.InterventionAtomBinding.to_trinity_intervention_spec
    original_causal = intervention_atom_binding.InterventionAtomBinding.to_node_intervention
    original_query = intervention_atom_binding.InterventionAtomBinding.to_query_target

    def drop_enabled_to_default(self):
        return original_trinity(self).model_copy(update={"enabled": True})

    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_trinity_intervention_spec",
        drop_enabled_to_default,
    )
    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )
    assert round_trip["status"] == "fail"
    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_trinity_intervention_spec",
        original_trinity,
    )

    def drop_assignment_value_to_default(self):
        causal = original_causal(self)
        assignment = causal.assignments[0].model_copy(update={"value": None})
        return causal.model_copy(update={"assignments": (assignment,)})

    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_node_intervention",
        drop_assignment_value_to_default,
    )
    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )
    assert round_trip["status"] == "fail"
    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_node_intervention",
        original_causal,
    )

    def drop_query_target_kind_to_default(self):
        return original_query(self).model_copy(update={"target_kind": "expectation"})

    monkeypatch.setattr(
        intervention_atom_binding.InterventionAtomBinding,
        "to_query_target",
        drop_query_target_kind_to_default,
    )
    round_trip = (
        check_layer3_gy_generation_cycle_disposition_ledger
        ._intervention_atom_binding_round_trip_report()
    )
    assert round_trip["status"] == "fail"


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_stale_python314_claim() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    gate = mutated["method_availability_gate"]
    assert isinstance(gate, dict)
    expected = gate["expected"]
    assert isinstance(expected, dict)
    econml = expected["econml"]
    assert isinstance(econml, dict)
    econml["available"] = True

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "method_availability_gate_drift" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_mapped_owner_missing() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    mapping = mutated["task_owner_mapping"]
    assert isinstance(mapping, dict)
    gy_n1 = mapping["GY-N1"]
    assert isinstance(gy_n1, dict)
    missing_owner_id = gy_n1["owner_ids"][0]
    owners = mutated["owners"]
    assert isinstance(owners, list)
    mutated["owners"] = [
        owner
        for owner in owners
        if isinstance(owner, dict) and owner.get("owner_id") != missing_owner_id
    ]

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "task_mapping_owner_missing_from_ledger" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_notebook_owner_omitted() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    _remove_owner_everywhere(mutated, "mock_generator_outputs")

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "notebook_owner_missing_from_ledger" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_notebook_disposition_softening() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    owner = _owner_by_id(mutated, "s2_fixed_credit_guarantee_body")
    owner["disposition"] = "USE_AS_IS"
    owner.pop("strangle_receipt")

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "disposition_mismatch_with_notebook" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_rejects_shifted_notebook_ref() -> None:
    ledger = _loaded_ledger()
    mutated = copy.deepcopy(ledger)
    owner = _owner_by_id(mutated, "nl_pipeline_authority_publication")
    owner["source_notebook_refs"] = [
        "architecture/policy_design_case/layer3_gy_n0_investigation.md:2494",
    ]

    report = check_layer3_gy_generation_cycle_disposition_ledger.validate_ledger(
        REPO_ROOT,
        mutated,
    )

    assert report["status"] == "fail"
    assert "source_notebook_ref_unresolved" in _issue_codes(report)


def test_layer3_gy_generation_cycle_disposition_ledger_corrupt_field_drift_returns_failure() -> None:
    report = check_layer3_gy_generation_cycle_disposition_ledger.corrupt_field_drift_check(
        REPO_ROOT,
    )

    assert report["status"] == "fail"
    assert "corrupt_field_drift_detected" in _issue_codes(report)
