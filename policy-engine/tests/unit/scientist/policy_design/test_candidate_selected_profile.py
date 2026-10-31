from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import _resolve_candidate
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import (
    load_policy_candidate_schema,
    persist_policy_candidate_schema,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


@pytest.mark.parametrize("foreign", ["kind", "schema"])
def test_candidate_owner_and_real_consumer_refuse_foreign_selected_profile(
    tmp_path, foreign: str
) -> None:
    """Same candidate bytes in a foreign manifest cannot be selected as this owner."""
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    selected = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    assert selected.manifest_profile_sha256 is not None
    assert load_policy_candidate_schema(store, selected) == candidate
    legacy = selected.model_copy(update={"manifest_profile_sha256": None})
    assert load_policy_candidate_schema(store, legacy) == candidate
    ctx = cast("ExecutionContext", SimpleNamespace(store=store, _engine_invocation=None))
    state = ExperimentState(
        run_id="synthetic-candidate",
        params={"policy_candidate_ref": selected.model_dump(mode="json")},
    )
    assert _resolve_candidate(ctx, state) == (candidate, selected)
    original_manifest = store.get_manifest(selected)
    counterfeit = store.put_bytes(
        store.get_bytes(selected),
        PutOptions(
            kind="test.foreign_candidate" if foreign == "kind" else original_manifest.kind,
            media_type=original_manifest.media_type,
            schema=(
                SchemaInfo(name="test.ForeignCandidate", version="1.0")
                if foreign == "schema"
                else original_manifest.artifact_schema
            ),
            canon=original_manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert counterfeit.artifact_id == selected.artifact_id
    assert counterfeit.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert store.verify(counterfeit).ok
    with pytest.raises(CanonicalProfileRefusalError):
        load_policy_candidate_schema(store, counterfeit)
    state.params["policy_candidate_ref"] = counterfeit.model_dump(mode="json")
    with pytest.raises(CanonicalProfileRefusalError):
        _resolve_candidate(ctx, state)
