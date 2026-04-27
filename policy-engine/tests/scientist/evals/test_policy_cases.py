from __future__ import annotations

from polisyos.scientist.evals.policy_cases import (
    PolicyCaseDimension,
    default_policy_domain_eval_pack,
)


def test_default_policy_domain_eval_pack_covers_policy_design_dimensions() -> None:
    pack = default_policy_domain_eval_pack()

    assert pack.pack_id == "policy_domain_eval_pack_v1"
    assert pack.covered_dimensions == set(PolicyCaseDimension)
