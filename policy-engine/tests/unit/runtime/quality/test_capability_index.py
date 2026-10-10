from __future__ import annotations

from pathlib import Path

from polisyos.core.contracts.capability_discovery import CapabilityDiscoveryRequest
from polisyos.core.contracts.search import SearchRequest
from polisyos.runtime.quality.capability_discovery import (
    CapabilityIndexCapabilityDiscoveryProvider,
)
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    compile_capability_index,
    create_capability_index_fixture_inputs,
)


def test_compiled_method_candidate_keeps_execution_authority_out_of_discovery(
    tmp_path: Path,
) -> None:
    """The compiled producer feeds a real owner query without upgrading candidates."""

    fixture_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    compiled = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=fixture_root,
            output_dir=tmp_path / "release",
            mode="fixture",
            generated_at="2026-10-10T00:00:00Z",
        )
    )
    method = next(
        capability
        for capability in compiled.capability_index.capabilities
        if "foundry_method_contract" in capability.modality
    )
    provider = CapabilityIndexCapabilityDiscoveryProvider(
        resource_kind="method",
        capability_index=compiled.capability_index,
    )

    result = provider.search(
        CapabilityDiscoveryRequest(
            search=SearchRequest(
                request_id="compiled-method-candidate-query",
                query_text=method.construct_id,
                construct_refs=(f"construct:{method.construct_id}",),
                intent="find the release-indexed method candidate",
                required_layers=("L1", "L7"),
                authority_purpose="research_method_discovery",
                allowed_modes=("exact", "lexical"),
                budget={"top_k": 5},
                rule_version="policyos.dx0.capability-index-consumer.v1",
            ),
            resource_kinds=("method",),
            audience="EXPERT",
        )
    )

    assert result.owner_receipt.index_release_ref == compiled.capability_index.release_ref
    selected = tuple(row for row in result.rows if row.capability_ref == method.capability_id)
    assert selected
    assert all("execution_authority" in row.may_not_use_for for row in selected)
    assert all("publication_authority" in row.may_not_use_for for row in selected)
