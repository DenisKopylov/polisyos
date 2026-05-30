from __future__ import annotations

from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.simulator.mutator import MutationIntent, NormPackMutator


def _rule(norm_id: str, desc: str) -> NormRule:
    return NormRule(
        norm_id=norm_id,
        rule_type=RuleType.OBLIGATION,
        description=desc,
    )


def test_mutator_builds_new_pack_with_intent_metadata() -> None:
    base = NormPack(
        pack_id="normpack.base",
        jurisdiction="ua",
        effective_date="2026-01-01",
        norms=[_rule("n.a", "A"), _rule("n.b", "B")],
    )
    intent = MutationIntent(
        scenario_label="tax-reform-a",
        reason="evaluate stricter obligation",
        requested_by="qa",
        ticket_ref="POL-13",
    )

    updated = (
        NormPackMutator(base)
        .modify_norm("n.a", description="A+")
        .remove_norm("n.b")
        .add_norm(_rule("n.c", "C"))
        .build(intent)
    )

    assert updated.pack_id != base.pack_id
    assert updated.metadata["_mutation_base_pack_id"] == base.pack_id
    assert updated.metadata["_mutation_intent"]["scenario_label"] == "tax-reform-a"
    assert sorted(rule.norm_id for rule in updated.norms) == ["n.a", "n.c"]


def test_mutator_is_deterministic_for_same_ops_and_intent() -> None:
    base = NormPack(
        pack_id="normpack.base",
        jurisdiction="ua",
        norms=[_rule("n.a", "A"), _rule("n.b", "B")],
    )
    intent = MutationIntent(scenario_label="s1", reason="r1")

    pack_1 = NormPackMutator(base).modify_norm("n.a", description="A+").build(intent)
    pack_2 = NormPackMutator(base).modify_norm("n.a", description="A+").build(intent)

    assert pack_1.pack_id == pack_2.pack_id
