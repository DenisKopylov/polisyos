"""Run the real owner-rejection contract after removing a decisive property."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.fabric.evidence.non_data_acquisition import NonDataAcquisitionRuntime

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.fabric.evidence.non_data_acquisition import AcquisitionEvaluationContext


def main() -> None:
    """Require the relevant actual pytest gate to turn red under one mutant."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mutant", choices=("owner_semantics", "owner_target", "current_use_context")
    )
    args = parser.parse_args()
    selector = "body"
    if args.mutant == "owner_semantics":
        NonDataAcquisitionRuntime._owners_accept = lambda self, **kwargs: True
    elif args.mutant == "owner_target":
        selector = "fake_ref"
        original_persist = NonDataAcquisitionRuntime._persist
        original_resolve = NonDataAcquisitionRuntime._resolve

        def retain_candidate(self: NonDataAcquisitionRuntime, payload: object, kind: str) -> str:
            ref = original_persist(self, payload, kind)
            if kind == "fabric.non_data_acquisition.candidate":
                self._probe_candidate = ref
            return ref

        def resolve_wrong_target(
            self: NonDataAcquisitionRuntime, ref: str, kind: str
        ) -> dict[str, Any]:
            if ref == "sha256:" + "0" * 64:
                ref = self._probe_candidate
            return original_resolve(self, ref, kind)

        NonDataAcquisitionRuntime._persist = retain_candidate
        NonDataAcquisitionRuntime._resolve = resolve_wrong_target
    else:
        original_accept = NonDataAcquisitionRuntime._owners_accept

        def substitute_use(
            self: NonDataAcquisitionRuntime,
            *,
            demand: Mapping[str, Any],
            candidate: Mapping[str, Any],
            context: AcquisitionEvaluationContext,
        ) -> bool:
            forged_context = context.model_copy(
                update={"requested_use": context.requested_use.model_copy(
                    update={"purpose_ref": "purpose:bounded-research"}
                )}
            )
            return original_accept(
                self, demand=demand, candidate=candidate, context=forged_context
            )

        NonDataAcquisitionRuntime._owners_accept = substitute_use
    gate = "tests/unit/fabric/test_non_data_acquisition.py::" + (
        "test_every_semantic_port_receives_bound_current_use_context"
        "[purpose-independent_verification]"
        if args.mutant == "current_use_context"
        else f"test_owner_admission_fails_closed_through_real_runtime[{selector}]"
    )
    result = pytest.main([gate, "-o", "addopts=", "-q"])
    sys.stdout.write(f"mutant={args.mutant}; deciding_gate_exit={int(result)}; expected=1\n")
    if result != pytest.ExitCode.TESTS_FAILED:
        raise SystemExit("decisive property removal did not turn the real gate red")


if __name__ == "__main__":
    main()
