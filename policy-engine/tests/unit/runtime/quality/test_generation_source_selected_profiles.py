"""Generic N4 source writes retain the exact Core profile selected by CAS."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_generic_n4_source_returns_selected_profile_and_preserves_parent_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real generic source production and replay bind full selected CAS lineage."""

    from polisyos.core import artifacts
    from polisyos.core.artifacts import (
        FileSystemCAS,
        artifact_manifest_profile_sha256,
        input_ref_from_artifact_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_source import (
        SOURCE_KIND,
        SOURCE_SCHEMA,
        GenerationSourceRepository,
        _candidate_simulation_write_options,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import (
        _authenticated_tenant_scope,
        _TestCurrentJobExecutionOwner,
    )
    from tests.unit.runtime.quality.test_generic_n5_v3_binding import (
        _prepare_generic_facade_owner_case,
    )

    case = await _prepare_generic_facade_owner_case(tmp_path, monkeypatch)
    store = case["store"]
    repository = GenerationSourceRepository(store)
    prior_handoff = case["handoff"]
    source_run_id = "source-selected-profile-test"

    with _authenticated_tenant_scope(
        tenant_id=case["tenant_id"],
        cell_id=case["cell_id"],
    ):
        context_owner = CycleSubstrateContextArtifactOwner(
            store=store,
            control_store=_TestCurrentJobExecutionOwner(
                prior_handoff.job_id,
                prior_handoff.run_id,
            ),
        )
        context_ref = context_owner.persist_for_current_job(
            prior_handoff.context,
            problem=case["problem"],
            return_selected_profile=True,
        )
    assert context_ref.manifest_profile_sha256 is not None
    handoff = prior_handoff.model_copy(update={"context_job_ref": context_ref})
    source_read_kwargs = {
        "run_id": source_run_id,
        "expected_run_id": handoff.run_id,
        "expected_job_id": handoff.job_id,
        "expected_tenant_id": case["tenant_id"],
        "expected_cell_id": case["cell_id"],
        "context_job_ref": handoff.context_job_ref,
        "profile_ref": handoff.profile_ref,
    }

    with _authenticated_tenant_scope(
        tenant_id=case["tenant_id"],
        cell_id=case["cell_id"],
    ):
        source_ref = repository.persist_ref(
            run_id=source_run_id,
            expected_run_id=handoff.run_id,
            cycle_index=0,
            problem=case["problem"],
            organ=case["organ"],
            execution_scope="contract_testing",
            job_id=handoff.job_id,
            tenant_id=case["tenant_id"],
            cell_id=case["cell_id"],
            context_job_ref=handoff.context_job_ref,
            profile_ref=handoff.profile_ref,
        )
        assert source_ref.manifest_profile_sha256 is not None
        source_manifest = store.get_manifest(source_ref)
        assert source_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            source_manifest
        )
        assert handoff.context_job_ref.manifest_profile_sha256 is not None
        assert handoff.profile_ref.manifest_profile_sha256 is not None
        parent_inputs = (
            input_ref_from_artifact_ref(
                handoff.context_job_ref,
                role="cycle_substrate_context_job",
            ),
            input_ref_from_artifact_ref(
                handoff.profile_ref,
                role="generic_cycle_simulation_profile",
            ),
        )
        assert tuple(source_manifest.inputs) == parent_inputs

        source = repository.load(source_ref, **source_read_kwargs)
        assert source.problem == case["problem"]
        assert source.cycle_substrate_context == handoff.context
        assert source.generation_result == case["organ"].result

        # A second valid CAS manifest for the same bytes but a different
        # writer profile must not be accepted as the configured producer.
        writer_options = _candidate_simulation_write_options(
            kind=SOURCE_KIND,
            schema_name=SOURCE_SCHEMA,
            schema_version="1.0",
            job_id=handoff.job_id,
            run_id=handoff.run_id,
            tenant_id=case["tenant_id"],
            cell_id=case["cell_id"],
            source_ref=source.content_hash,
            input_refs=tuple(source_manifest.inputs),
        )
        assert writer_options.producer is not None
        foreign_options = replace(
            writer_options,
            producer=writer_options.producer.model_copy(
                update={"component": "tests.foreign_generation_source_writer"}
            ),
        )
        source_bytes = store.get_bytes(source_ref)
        foreign_ref = store.put_bytes(
            source_bytes,
            foreign_options,
            return_selected_profile=True,
        )
        assert foreign_ref.artifact_id == source_ref.artifact_id
        assert foreign_ref.manifest_profile_sha256 is not None
        assert foreign_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
        assert foreign_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            store.get_manifest(foreign_ref)
        )
        with pytest.raises(ValueError, match="generation_source_owner_profile_mismatch"):
            repository.load(foreign_ref, **source_read_kwargs)

        # A profileless default view over those same bytes is not repaired by
        # inferring a profile from a later manifest read.
        profileless_store = FileSystemCAS(tmp_path / "profileless-foreign-source-cas")
        profileless_ref = profileless_store.put_bytes(source_bytes, foreign_options)
        assert profileless_ref.artifact_id == source_ref.artifact_id
        assert profileless_ref.manifest_profile_sha256 is None
        assert (
            artifact_manifest_profile_sha256(profileless_store.get_manifest(profileless_ref))
            != source_ref.manifest_profile_sha256
        )
        with pytest.raises(ValueError, match="generation_source_owner_profile_mismatch"):
            GenerationSourceRepository(profileless_store).load(
                profileless_ref,
                **source_read_kwargs,
            )

        class ProfilelessDelegatingWriter:
            """Delegate a real CAS write while suppressing its selected ref."""

            def __init__(self, inner: Any) -> None:
                self.inner = inner
                self.requested_selections: list[bool] = []
                self.returned_refs: list[artifacts.ArtifactRef] = []

            def __getattr__(self, name: str) -> Any:
                return getattr(self.inner, name)

            def put_bytes(
                self,
                data: bytes,
                options: Any,
                *,
                return_selected_profile: bool = False,
            ) -> artifacts.ArtifactRef:
                self.requested_selections.append(return_selected_profile)
                ref = self.inner.put_bytes(data, options)
                self.returned_refs.append(ref)
                return ref

        profileless_writer = ProfilelessDelegatingWriter(store)
        profileless_repository = GenerationSourceRepository(profileless_writer)
        scoped_write_kwargs = {
            "run_id": source.run_id,
            "expected_run_id": handoff.run_id,
            "cycle_index": source.cycle_index + 1,
            "problem": case["problem"],
            "organ": case["organ"],
            "execution_scope": "contract_testing",
            "job_id": handoff.job_id,
            "tenant_id": case["tenant_id"],
            "cell_id": case["cell_id"],
            "context_job_ref": handoff.context_job_ref,
            "profile_ref": handoff.profile_ref,
        }
        with pytest.raises(
            ValueError,
            match="generation_source_generic_selected_profile_not_returned",
        ):
            profileless_repository.persist_ref(**scoped_write_kwargs)
        assert profileless_writer.requested_selections == [True]
        assert len(profileless_writer.returned_refs) == 1
        assert profileless_writer.returned_refs[0].manifest_profile_sha256 is None
