"""Falsify campaign stop/recovery/history properties without editing source bytes."""

from __future__ import annotations

import argparse
import ast
import inspect

import pytest

from polisyos.data_forge.domains.academic.batch import reextraction_campaign as owner

TESTS = "tests/unit/data_forge/domains/academic/batch/test_reextraction_campaign_recovery.py"


def main() -> int:
    """Keep real artifacts and declarations while removing the deciding owner behavior."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("property", choices=["fatal_stop", "recovery_quiescence", "wal"])
    args = parser.parse_args()
    if args.property == "fatal_stop":
        owner.CampaignCheckpoint.active_fatal_stop = lambda self: None
        node = "test_systemic_failure_stops_and_recovery_preserves_completed_work"
    else:
        method = (
            owner.CampaignCheckpoint.recover_fatal_stop
            if args.property == "recovery_quiescence"
            else owner.CampaignCheckpoint._snapshot_history_metadata
        )
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
        if args.property == "recovery_quiescence":
            matches = [
                item
                for item in ast.walk(tree)
                if isinstance(item, ast.If) and "state='dispatched'" in ast.unparse(item.test)
            ]
            if len(matches) != 1:
                raise RuntimeError("recovery_removal_guard_identity_changed")
            matches[0].test = ast.Constant(value=False)
            node = "test_recovery_requires_all_dispatched_attempts_to_settle"
        else:
            matches = [
                item
                for item in ast.walk(tree)
                if isinstance(item, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "selected"
                    for target in item.targets
                )
            ]
            if len(matches) != 1:
                raise RuntimeError("wal_removal_source_identity_changed")
            matches[0].value = ast.parse(
                "[name for name in before if name == 'checkpoint.sqlite3']",
                mode="eval",
            ).body
            node = "test_historical_reader_includes_valid_wal_without_touching_source"
        ast.fix_missing_locations(tree)
        namespace = dict(vars(owner))
        exec(compile(tree, inspect.getsourcefile(method) or "<campaign-owner>", "exec"), namespace)  # noqa: S102 - deliberate in-memory removal, original source and markers unchanged.
        setattr(owner.CampaignCheckpoint, method.__name__, namespace[method.__name__])
    return int(pytest.main([TESTS + "::" + node, "-q"]))


if __name__ == "__main__":
    raise SystemExit(main())
