from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from _helpers.runtime_http import (
    _record_fixture_owner,
    _runtime_api_request,
    build_runtime_api_env,
    close_runtime_api_env,
)

from polisyos.core.artifacts import PutOptions, profile_bound_ref
from polisyos.core.security.tenant_context import tenant_scope

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

# Raw packet fixtures deliberately use runtime assertions for behavioral signals.
# ruff: noqa: S101


@pytest.fixture
def runtime_api_env(tmp_path: Path) -> Iterator[Mapping[str, object]]:
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def test_equilibria_refuses_selected_profile_instead_of_softening_to_missing(
    runtime_api_env: Mapping[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    run_id = runtime_api_env["core_run_id"]
    run = context.run_index.get_run(run_id)
    store = context.store
    selected_ref = next(
        ref
        for ref in run.details.root_artifacts
        if ref.kind == "foundry.equilibrium_multiplicity_report"
    )
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        manifest = store.get_manifest(selected_ref)
        raw_payload = store.get_bytes(selected_ref)
        assert manifest.canon is not None

        shared_options = {
            "kind": manifest.kind,
            "media_type": manifest.media_type,
            "schema": manifest.artifact_schema,
            "producer": manifest.producer,
            "env": manifest.env,
            "inputs": manifest.inputs,
            "governance": manifest.governance,
            "tenant_context": manifest.tenant_context,
            "same_input_closure": manifest.same_input_closure,
            "authority": manifest.authority,
            "warnings": manifest.warnings,
        }
        selected_nonconformant_ref = profile_bound_ref(
            store,
            store.put_bytes(
                raw_payload,
                PutOptions(
                    **shared_options,
                    canon=manifest.canon.model_copy(update={"forbid_floats": True}),
                ),
            ),
        )
        id_default_conformant_ref = profile_bound_ref(
            store,
            store.put_bytes(
                raw_payload,
                PutOptions(**shared_options, canon=manifest.canon),
            ),
        )

    assert selected_nonconformant_ref.artifact_id == id_default_conformant_ref.artifact_id
    assert (
        selected_nonconformant_ref.manifest_profile_sha256
        != id_default_conformant_ref.manifest_profile_sha256
    )
    _record_fixture_owner(
        store,
        selected_nonconformant_ref,
        id_default_conformant_ref,
        tenant_id=tenant_id,
        cell_id=cell_id,
        runtime_api_env=runtime_api_env,
    )

    root_artifacts = [
        selected_nonconformant_ref if ref == selected_ref else ref
        for ref in run.details.root_artifacts
    ]
    assert selected_nonconformant_ref in root_artifacts
    bad_run = replace(
        run,
        details=run.details.model_copy(update={"root_artifacts": root_artifacts}),
    )
    monkeypatch.setattr(context.run_index, "get_run", lambda _run_id: bad_run)

    response = _runtime_api_request(
        runtime_api_env,
        runtime_api_env["client"].get,
        f"/api/v1/debug/runs/{run_id}/equilibria",
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "canon_profile_payload_nonconformant"
