from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality.capability_discovery as capability_discovery
import polisyos.runtime.quality.generation_cycle as generation_cycle_module
from polisyos.runtime.quality.acquisition_planner import (
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.capability_discovery import (
    CAPABILITY_INDEX_PATH_ENV,
    CapabilityProviderUnavailableError,
)
from polisyos.runtime.quality.capability_index import CapabilityIndex, EvidenceCapability
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexBuildResult,
    CapabilityIndexCompilerConfig,
    compile_capability_index,
    create_capability_index_fixture_inputs,
)
from polisyos.runtime.quality.capability_resolver import (
    RequirementToCapabilityQuery,
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleError,
    PendingN8ValuePort,
)
from tests.unit.runtime.quality.test_generation_cycle import (
    _AcquisitionGrounding,
    _budget,
    _CounterexampleAwareGenerator,
    _problem,
)


def _build_persisted_fixture_release(tmp_path: Path) -> CapabilityIndexBuildResult:
    """Use the canonical compiler to produce a real DuckDB release and manifest."""

    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    return compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "capability-index",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )


def _query_for(capability: EvidenceCapability) -> RequirementToCapabilityQuery:
    """Build a resolver query against one row emitted by the persisted-index producer."""

    return RequirementToCapabilityQuery.model_validate(
        {
            "requirement_id": "test:e02-configured-capability-index",
            "construct": capability.construct_id,
            "entity_scope": capability.scope.entity_scope,
            "population_filter": (
                {"type": capability.scope.population} if capability.scope.population else {}
            ),
            "geography": capability.scope.geography,
            "time_window": {
                "start": capability.scope.time_start,
                "end": capability.scope.time_end,
            },
            "authority_level": "research",
            "claim_use": "claim_evidence_closeout",
            "required_modalities": capability.modality,
        }
    )


def test_default_n7_resolver_uses_configured_persisted_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid release reaches the existing resolver through the configured loader."""

    release = _build_persisted_fixture_release(tmp_path)
    assert release.capability_index is not None
    monkeypatch.setenv(CAPABILITY_INDEX_PATH_ENV, str(release.primary_duckdb_path))

    loaded_releases: list[CapabilityIndex] = []
    load_release = capability_discovery.load_default_capability_index_release

    def _record_load() -> CapabilityIndex:
        loaded = load_release()
        loaded_releases.append(loaded)
        return loaded

    monkeypatch.setattr(
        capability_discovery,
        "load_default_capability_index_release",
        _record_load,
    )

    def _fixture_fallback_forbidden(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("default N7 resolver used the governed fixture fallback")

    monkeypatch.setattr(
        RequirementToCapabilityResolver,
        "governed_fixture",
        _fixture_fallback_forbidden,
    )

    resolver = GenerationCycleController()._n7_capability_resolver(_problem("configured_n7_index"))

    assert isinstance(resolver, RequirementToCapabilityResolver)
    assert loaded_releases
    loaded = loaded_releases[0]
    assert loaded.release_ref == release.capability_index.release_ref
    assert loaded.metadata["logical_duckdb_sha256"]
    capability = loaded.capabilities[0]
    binding = resolver.resolve(_query_for(capability))
    assert binding.requirement_id == "test:e02-configured-capability-index"
    assert binding.capability_index_ref == loaded.release_ref


@pytest.mark.parametrize(
    ("release_state", "provider_reason"),
    [
        ("unconfigured", "capability_index_release_path_unconfigured"),
        ("missing", "capability_index_release_missing"),
        ("invalid_manifest", "capability_index_release_invalid"),
        ("malformed_database", "capability_index_release_invalid"),
    ],
)
def test_unavailable_configured_release_is_a_typed_n7_error(
    release_state: str,
    provider_reason: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if release_state == "unconfigured":
        monkeypatch.delenv(CAPABILITY_INDEX_PATH_ENV, raising=False)
    elif release_state == "missing":
        monkeypatch.setenv(
            CAPABILITY_INDEX_PATH_ENV,
            str(tmp_path / "missing" / "capability_index_v1.duckdb"),
        )
    else:
        release = _build_persisted_fixture_release(tmp_path)
        if release_state == "malformed_database":
            release.primary_duckdb_path.write_bytes(b"not a DuckDB database")
        else:
            manifest = json.loads(release.manifest_path.read_text(encoding="utf-8"))
            manifest["signature"]["digest"] = "invalid-digest"
            release.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        monkeypatch.setenv(CAPABILITY_INDEX_PATH_ENV, str(release.primary_duckdb_path))

    with pytest.raises(GenerationCycleError) as raised:
        GenerationCycleController()._n7_capability_resolver(
            _problem(f"unavailable_n7_index_{release_state}")
        )

    assert raised.value.code == "n7_capability_index_unavailable"
    cause = raised.value.__cause__
    assert isinstance(cause, CapabilityProviderUnavailableError)
    assert cause.reason_code == provider_reason


def test_explicit_empty_and_any_of_requirements_do_not_load_an_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_resolver(
        _controller: GenerationCycleController,
        _problem: object,
    ) -> None:
        pytest.fail("empty or any_of requirement unexpectedly composed a capability resolver")

    monkeypatch.setattr(
        GenerationCycleController,
        "_n7_capability_resolver",
        _unexpected_resolver,
    )
    controller = GenerationCycleController(repo_root=tmp_path)
    problem = _problem("n7_no_resolver_for_empty_or_any_of")

    assert (
        controller._n7_data_requirement_specs(
            problem,
            acquisition_request={"data_requirement_specs": ()},
        )
        == ()
    )

    any_of_gap = value_input_world_knowledge_requirement_gap(
        claim_ref="value-claim:n7-empty-any-of-control"
    )
    specs = controller._n7_data_requirement_specs(
        problem,
        acquisition_request={"requirement_gap": any_of_gap.model_dump(mode="json")},
    )
    assert specs == (any_of_gap,)


@pytest.mark.asyncio
async def test_unavailable_n7_index_is_routed_without_minting_a_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CAPABILITY_INDEX_PATH_ENV, raising=False)

    run = await GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=tmp_path,
    ).run(
        _problem("n7_configured_index_unavailable"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    assert "n7_capability_index_unavailable" in (generation_cycle_module._N7_ROUTING_FAILURE_CODES)
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.counterexample.diagnostic.code == (
        "n6.acquisition.n7_capability_index_unavailable"
    )
    assert cycle.acquisition_receipt is None
    assert cycle.acquisition_routing_report is None
