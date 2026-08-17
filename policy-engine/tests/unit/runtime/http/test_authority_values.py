"""DS16-C03/C04 — the producer contract for the retired DS4-C23 inventory.

Every assertion here is paired with the construction that makes it fail, because a
completeness check that has never rejected an incomplete inventory proves nothing about
completeness — that is `P29` in test clothing, and this cluster exists to close exactly
the failure mode where a value is dropped silently.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.runtime.http.services.authority_values import (
    INVENTORY_VERSION,
    AuthoritySurface,
    AuthorityValueId,
    RefusedAuthorityValue,
    RunAuthorityProjection,
    SuppliedAuthorityValue,
    ValueRefusalCode,
    authority_value_dispositions,
    authority_value_inventory_artifact,
    build_run_authority_projection,
)

ARTIFACT_PATH = (
    Path(__file__).resolve().parents[4] / "schemas" / "ds16_authority_value_inventory.json"
)


def _digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_every_retired_value_is_dispositioned_exactly_once() -> None:
    projection = build_run_authority_projection("run-ds16")

    dispositioned = [value.value_id for value in projection.values]
    assert set(dispositioned) == set(AuthorityValueId)
    assert len(dispositioned) == len(set(dispositioned))
    assert len(dispositioned) == len(AuthorityValueId)


def test_incomplete_inventory_cannot_be_constructed() -> None:
    """The non-vacuity proof: dropping one member must be refused, not tolerated."""

    complete = authority_value_dispositions()
    dropped = complete[0]

    with pytest.raises(ValidationError) as dropped_error:
        RunAuthorityProjection(
            inventory_version=INVENTORY_VERSION,
            retirement_commit="bc1d01001",
            run_id="run-ds16",
            values=complete[1:],
        )
    assert "incomplete" in str(dropped_error.value)
    assert dropped.value_id.value in str(dropped_error.value)

    with pytest.raises(ValidationError) as duplicate_error:
        RunAuthorityProjection(
            inventory_version=INVENTORY_VERSION,
            retirement_commit="bc1d01001",
            run_id="run-ds16",
            values=(*complete, complete[0]),
        )
    assert "duplicate" in str(duplicate_error.value)


def test_no_value_is_an_optional_field_the_client_could_fill_in() -> None:
    """An absent value is a served refusal carrying its reason, never a null field."""

    for value in build_run_authority_projection("run-ds16").values:
        assert value.state in {"refused", "supplied"}
        assert value.surface in set(AuthoritySurface)
        if value.state == "refused":
            assert value.reason.strip()
            assert value.refusal_code in set(ValueRefusalCode)
            assert value.retired_from.endswith(".ts")


def test_an_owning_surface_is_named_when_and_only_when_one_exists() -> None:
    owned = [
        value
        for value in authority_value_dispositions()
        if value.state == "refused"
        and value.refusal_code is ValueRefusalCode.OWNED_BY_ANOTHER_SURFACE
    ]
    assert owned, "at least one value must point at its real owner"
    assert all(value.owner_surface for value in owned)

    # An owner claimed without the owning code, and a code claiming an owner without
    # naming one, are both refused.
    with pytest.raises(ValidationError):
        RefusedAuthorityValue(
            reason="no producer",
            refusal_code=ValueRefusalCode.NO_RUNTIME_PRODUCER,
            retired_from="x.ts",
            owner_surface="some surface",
            value_id=AuthorityValueId.READINESS_EMBARGO_OVERLAY,
        )
    with pytest.raises(ValidationError):
        RefusedAuthorityValue(
            reason="owned elsewhere",
            refusal_code=ValueRefusalCode.OWNED_BY_ANOTHER_SURFACE,
            retired_from="x.ts",
            value_id=AuthorityValueId.READINESS_LENS_PROJECTION,
        )


def test_supplied_variant_exists_so_a_future_value_needs_no_contract_change() -> None:
    supplied = SuppliedAuthorityValue(
        metric_id="readiness.composite",
        point=None,
        surface=AuthoritySurface.READINESS,
        value_id=AuthorityValueId.READINESS_COMPOSITE_VERDICT,
    )
    assert supplied.state == "supplied"

    # Substituting it for the refusal keeps the projection valid: the inventory is
    # complete either way, which is what lets a value graduate without a schema change.
    graduated = tuple(
        supplied if value.value_id is supplied.value_id else value
        for value in authority_value_dispositions()
    )
    projection = RunAuthorityProjection(
        inventory_version=INVENTORY_VERSION,
        retirement_commit="bc1d01001",
        run_id="run-ds16",
        values=graduated,
    )
    assert sum(value.state == "supplied" for value in projection.values) == 1


def test_persisted_artifact_is_recomputed_from_live_code_not_trusted() -> None:
    """`P29`: the committed artifact is checked against a fresh computation."""

    committed = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    recomputed = authority_value_inventory_artifact()

    assert committed == recomputed
    assert committed["member_count"] == len(AuthorityValueId)

    # And the digest is load-bearing: recomputing it over a mutated payload must give a
    # different hash, otherwise the artifact's identity would not be content-bound.
    payload = {key: value for key, value in recomputed.items() if key != "content_sha256"}
    mutated = {**payload, "member_count": len(AuthorityValueId) + 1}
    assert _digest(mutated) != _digest(payload)
    assert f"sha256:{_digest(payload)}" == recomputed["content_sha256"]


def test_dispositions_do_not_vary_by_run() -> None:
    """A refusal is a property of the value; a run id must not be able to change it."""

    first = build_run_authority_projection("run-a").values
    second = build_run_authority_projection("run-b").values
    assert first == second


def test_authority_values_endpoint_serves_the_complete_inventory(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get(f"/api/v1/runs/{run_id}/authority-values")
    assert response.status_code == 200

    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["inventory_version"] == INVENTORY_VERSION
    assert len(payload["values"]) == len(AuthorityValueId)
    assert {value["value_id"] for value in payload["values"]} == {
        member.value for member in AuthorityValueId
    }
    # The discriminator C05 depends on is present on every member.
    assert all(value["state"] == "refused" for value in payload["values"])
    assert all(value["reason"] for value in payload["values"])
