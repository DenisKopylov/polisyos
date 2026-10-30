"""Actual served-profile selection over a larger synthetic registry inventory.

These tests establish candidate software composition only. They do not supply
Catalog admission, calibration, law, cost, grounding, or current authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextOffer
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
    build_cycle_substrate_context,
    cycle_job_design_problem_ref,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateRegistration,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from tests._helpers import acquisition_chain
from tests._helpers import acquisition_served_history as fixture
from tests._helpers import world_model_record as wmr_fixture
from tests._helpers.candidate_cycle_source_profile import (
    build_candidate_cycle_substrate_route_inputs,
)


@pytest.mark.parametrize("extra_required_entry", [False, True])
def test_served_profile_uses_actual_wmr_selection_with_complete_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_required_entry: bool,
) -> None:
    """Unselected inventory stays intact; every required entry reaches admission."""
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "source", include_owner_slot_manifest=True
    )
    problem = acquisition_chain.controlled_served_wdi_problem(
        source.problem, raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST
    )
    base = wmr_fixture._substrate_registry()
    registration = base.entries[0].model_dump(mode="python", exclude={"entry_content_hash"})
    entries = list(base.entries)
    entries.append(
        build_substrate_registry_entry(
            SubstrateRegistration.model_validate(
                {**registration, "source_id": "test:unselected", "family_id": "test_unselected"}
            )
        )
    )
    if extra_required_entry:
        entries.append(
            build_substrate_registry_entry(
                SubstrateRegistration.model_validate(
                    {**registration, "source_id": "test:additional_required"}
                )
            )
        )
    registry = build_substrate_registry(
        entries,
        producer_ref="test.served_profile_selection",
        source_catalog_refs=base.source_catalog_refs,
    )
    # Only seed the existing synthetic default input. Real WMR/context/NCM
    # producers and admission validators remain in place.
    monkeypatch.setattr(wmr_fixture, "_substrate_registry", lambda: registry)
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    with tenant_scope(None, tenant_id=fixture.TENANT, cell_id=fixture.CELL):
        profile, declaration = fixture._served_wdi_candidate_profile(
            tmp_path=tmp_path / "profile",
            store=store,
            problem=problem,
            source_owner_root=source.root,
        )
        owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(profile,), model_declarations=(declaration,), store=store
        )
        offer = owner.admit_context(
            problem=problem,
            job_id="job-selection",
            run_id="run-selection",
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
        )
        assert isinstance(offer, CandidateSimulationContextOffer)
        context = offer.context
        expected = {
            entry.entry_content_hash for entry in registry.resolve(family_id="firm_fundamentals")
        }
        assert context.substrate_registry.model_dump(mode="json") == (
            registry.model_dump(mode="json")
        )
        assert set(context.selected_registry_entry_hashes) == expected
        assert {
            entry.entry_content_hash
            for entry in context.world_model_record.substrate_registry_ref.resolved_entries
        } == expected
        assert expected < {entry.entry_content_hash for entry in registry.entries}
        assert context.world_model_record.authority_status == "limited"
        assert context.authority_purpose == "cycle_input_candidate_only"
        assert "grounding_not_established" in profile.limitations
        assert declaration.assumption == "declared_candidate_scm_not_empirically_grounded"
        # Reproduce the original class through the actual validator, keeping
        # complete inventory and genuine WMR bytes unchanged.
        with pytest.raises(ValueError, match="cycle_substrate_selected_entry_wmr_unresolved"):
            build_cycle_substrate_context(
                design_problem_ref=cycle_job_design_problem_ref(problem),
                domain=problem.domain,
                substrate_registry=registry,
                selected_registry_entry_hashes=tuple(
                    entry.entry_content_hash for entry in registry.entries
                ),
                world_model_record=context.world_model_record,
                intervention_substrate=context.intervention_substrate,
                candidate_levers=context.candidate_levers,
                transport_context=context.transport_context,
                source_pack_content_hash=context.source_pack_content_hash,
                substrate_input_content_hash=context.substrate_input_content_hash,
            )
