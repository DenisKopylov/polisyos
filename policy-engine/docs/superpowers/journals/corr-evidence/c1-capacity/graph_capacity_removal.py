"""Remove real graph storage properties while retaining their markers and schemas."""

from __future__ import annotations

import argparse
import unittest
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

from polisyos.data_forge.domains.academic.batch import _graph_staging as owner


def main() -> int:
    """Run one focused synthetic falsifier with only its runtime property removed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "property",
        choices=(
            "nested_commit",
            "group_capacity",
            "pair_capacity",
            "cross_direction",
            "namespace_usage",
            "source_provenance",
            "pair_bytes",
            "resolver_limits",
            "output_disk",
        ),
    )
    args = parser.parse_args()
    staging_tests = (
        "tests.unit.data_forge.domains.academic.batch.test_graph_staging.GraphStagingTests."
    )
    graph_tests = (
        "tests.unit.data_forge.domains.academic.batch.test_graph_capacity.GraphCapacityTests."
    )
    if args.property == "nested_commit":
        owner.DiskGroups._put = lambda *args, **kwargs: None
        node = staging_tests + "test_nested_edit_survives_reopen_and_exception_rolls_back"
    elif args.property == "namespace_usage":
        owner.StagingStore.observe_namespace = lambda *args, **kwargs: None
        node = (
            staging_tests
            + "test_usage_reconciles_all_registered_namespaces_and_applied_configuration"
        )
    elif args.property in {"group_capacity", "pair_capacity", "pair_bytes", "resolver_limits"}:
        original = owner.StagingStore.check
        removed = {
            "group_capacity": {"max_group_contributions"},
            "pair_capacity": {"max_pair_contributions"},
            "pair_bytes": {"max_pair_bytes"},
            "resolver_limits": {"max_resolver_vocabulary_entries", "max_resolver_vocabulary_bytes"},
        }[args.property]

        def without_selected_limit(
            self: owner.StagingStore, limit: str, identity: object, observed: int
        ) -> None:
            if limit not in removed:
                original(self, limit, identity, observed)

        owner.StagingStore.check = without_selected_limit
        node = {
            "group_capacity": staging_tests
            + "test_contribution_refusal_precedes_decode_and_mutation",
            "pair_capacity": graph_tests
            + "test_whole_pair_capacity_refuses_even_when_each_direction_fits",
            "pair_bytes": staging_tests
            + "test_pair_bytes_accept_exact_reservation_then_refuse_next_before_decode",
            "resolver_limits": graph_tests
            + "test_resolver_vocabulary_accepts_measured_bounds_and_refuses_each_smaller_budget",
        }[args.property]
    elif args.property == "output_disk":
        owner.enforce_owned_output_budget = (
            lambda paths, limits, **kwargs: owner.measure_owned_output_bytes(paths)
        )
        node = graph_tests + "test_direct_synthesis_counts_queue_bytes_in_shared_output_budget"
    elif args.property == "source_provenance":
        from polisyos.data_forge.domains.academic.batch import edge_synthesize

        edge_synthesize.observe_stored_source_provenance = lambda *args, **kwargs: None
        node = (
            graph_tests + "test_raw_only_source_ancestry_overrides_missing_and_false_caller_markers"
        )
    else:
        original = owner.DiskGroups.edit

        @contextmanager
        def without_cross_direction_merge(
            self: owner.DiskGroups,
            key: object,
            default_factory: Callable[[], dict[str, Any]],
            *,
            contribution: object,
            contribution_delta: int = 1,
        ) -> Iterator[dict[str, Any]]:
            with original(
                self,
                key,
                default_factory,
                contribution=contribution,
                contribution_delta=contribution_delta,
            ) as payload:
                if self.pair and contribution_delta:
                    payload.clear()
                    payload.update(default_factory())
                yield payload

        owner.DiskGroups.edit = without_cross_direction_merge
        node = graph_tests + "test_synthetic_synthesis_reconciles_opposing_directions_globally"
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName(node)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
