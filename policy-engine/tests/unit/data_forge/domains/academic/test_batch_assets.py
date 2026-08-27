from __future__ import annotations

from polisyos.data_forge.domains.academic.batch_assets import (
    plan_academic_batch_stages,
)


def test_claim_adjudication_asset_records_scientist_authority_owner() -> None:
    plan = next(
        item
        for item in plan_academic_batch_stages()
        if item.stage.stage_id == "claim_adjudicate"
    )

    assert plan.asset_specs[0].owner == "team-scientist"


def test_other_academic_assets_remain_data_forge_owned() -> None:
    plans = plan_academic_batch_stages()

    owners = {
        item.stage.stage_id: item.asset_specs[0].owner
        for item in plans
        if item.stage.stage_id != "claim_adjudicate"
    }

    assert owners
    assert set(owners.values()) == {"team-data-forge"}
