from __future__ import annotations

from polisyos.ir.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.simulator.diff import NormChangeType, diff_norm_packs


def _rule(norm_id: str, desc: str) -> NormRule:
    return NormRule(
        norm_id=norm_id,
        rule_type=RuleType.OBLIGATION,
        description=desc,
    )


def test_diff_norm_packs_detects_all_change_types() -> None:
    old_pack = NormPack(
        pack_id="normpack.old",
        jurisdiction="ua",
        norms=[
            _rule("n.keep", "keep"),
            _rule("n.modified", "before"),
            _rule("n.removed", "remove"),
        ],
    )
    new_pack = NormPack(
        pack_id="normpack.new",
        jurisdiction="ua",
        norms=[
            _rule("n.keep", "keep"),
            _rule("n.modified", "after"),
            _rule("n.added", "added"),
        ],
    )

    diff = diff_norm_packs(old_pack, new_pack)

    assert diff.added_count == 1
    assert diff.removed_count == 1
    assert diff.modified_count == 1
    assert diff.unchanged_count == 1
    assert sorted(diff.affected_norm_ids) == ["n.added", "n.modified", "n.removed"]

    change_types = {change.norm_id: change.change_type for change in diff.changes}
    assert change_types["n.added"] == NormChangeType.ADDED
    assert change_types["n.removed"] == NormChangeType.REMOVED
    assert change_types["n.modified"] == NormChangeType.MODIFIED
    assert change_types["n.keep"] == NormChangeType.UNCHANGED
