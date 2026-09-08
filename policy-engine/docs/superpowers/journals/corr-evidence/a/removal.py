"""Remove runtime properties while retaining contracts, markers and happy controls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "probe",
        choices=(
            "cap",
            "candidate_charging",
            "pair_sign",
            "event_binding",
            "binder_guard",
            "persisted_result",
            "synthetic_ancestry",
            "frame_content",
            "cg3_authority",
            "cg3_legacy_epoch",
        ),
    )
    args = parser.parse_args()
    if args.probe == "cg3_legacy_epoch":
        from polisyos.runtime.quality import grounding_admission

        with patch.object(
            grounding_admission,
            "_implicit_v1_artifact_projection",
            lambda payload, **_epoch: payload,
        ):
            return int(
                pytest.main(
                    [
                        "tests/unit/runtime/quality/test_grounding_admission.py::"
                        "test_legacy_cg3_producer_control_preserves_its_own_serialized_epoch",
                        "-q",
                        "--tb=short",
                    ]
                )
            )
    if args.probe == "cg3_authority":
        from polisyos.runtime.quality import grounding_admission

        with patch.object(
            grounding_admission, "_synthetic_admission_input", lambda *_inputs: False
        ):
            return int(
                pytest.main(
                    [
                        "tests/unit/runtime/quality/test_grounding_admission.py::"
                        "test_real_novel_lever_admits_and_records_content_addressed_patch",
                        "tests/unit/runtime/quality/test_grounding_admission.py::"
                        "test_synthetic_reference_cannot_be_laundered_by_a_false_cg2_flag",
                        "-q",
                        "--tb=short",
                    ]
                )
            )
    if args.probe == "frame_content":
        from polisyos.runtime.quality import grounding_calibration

        with patch.object(grounding_calibration, "_validated_frame", lambda frame: frame):
            return int(
                pytest.main(
                    [
                        "tests/unit/runtime/quality/test_grounding_calibration.py::"
                        "test_frame_intakes_recompute_mutable_nested_content",
                        "-q",
                        "--tb=short",
                    ]
                )
            )
    if args.probe in {"pair_sign", "binder_guard", "persisted_result"}:
        from polisyos.runtime.quality import grounding_bind, grounding_relation
        from tools.quality.validation.check_grounding_refusal_sensitivity import main as check

        original = grounding_relation._axis_relation

        def removed(axis: str, proposal: object, atom: object, **kwargs: bool) -> tuple[str, str]:
            if axis == "sign":
                return "equivalent", "sign marker retained; substantive comparison removed"
            return original(axis, proposal, atom, **kwargs)

        sys.argv = [
            "check",
            "--check",
            "--world-cas",
            ".tmp/gy-s-composed-wmr-cas",
            "--world-ref",
            "sha256:e96949676a6f0c9278cc8a82bf083d34f982e90b1c071097e953b2ffbb585bb5",
            "--declarations",
            "architecture/policy_design_case/corr/grounding-2026-09-08",
        ]
        if args.probe == "persisted_result":
            source = Path("architecture/policy_design_case/corr/grounding_refusal_sensitivity.json")
            payload = json.loads(source.read_bytes())
            # The artifact remains marked and its declaration unchanged; only the
            # decisive consumer authority outcome is dishonestly changed.
            payload["outcomes"][0]["governed_authority"] = True
            with TemporaryDirectory(prefix="corr-refusal-drift-", dir=".tmp") as folder:
                retained = Path(folder) / "synthetic-result.json"
                retained.write_text(json.dumps(payload))
                sys.argv.extend(["--report", str(retained)])
                return check()
        context = (
            patch.object(grounding_relation, "_axis_relation", removed)
            if args.probe == "pair_sign"
            else patch.object(grounding_bind, "_has_selected_critical_veto", lambda _cert: False)
        )
        with context:
            return check()
    from polisyos.runtime.quality import grounding_risk
    from polisyos.runtime.quality.grounding_bind import GroundingBindGate

    nodes = {
        "cap": "test_only_owner_admissions_charge_and_exhaustion_preserves_candidate",
        "candidate_charging": "test_refused_candidate_does_not_spend_any_admission_budget",
        "event_binding": "test_admission_event_cannot_be_transplanted_to_a_different_binding",
        "synthetic_ancestry": (
            "test_governed_resolver_recomputes_synthetic_ancestry_despite_false_flag"
        ),
    }
    if args.probe == "cap":
        context = patch.object(grounding_risk, "_budget_has_capacity", lambda _count: True)
    elif args.probe == "candidate_charging":
        original = GroundingBindGate._risk_ledger

        def charge_attempt(
            self: GroundingBindGate,
            ledger: object,
            *,
            calibration: object,
            admission: grounding_risk.GroundingRunAdmission | None = None,
        ) -> object:
            result = original(self, ledger, calibration=calibration, admission=admission)
            if admission is not None and admission.status != "admitted":
                return result.model_copy(update={"total_spend": 0.01})
            return result

        context = patch.object(GroundingBindGate, "_risk_ledger", charge_attempt)
    elif args.probe == "synthetic_ancestry":
        from polisyos.runtime.quality import grounding_bind

        context = patch.object(grounding_bind, "_synthetic_reference", lambda _reference: False)
    else:

        def ignore_binding_inputs(
            self: grounding_risk.GroundingRunBudget,
            receipt: grounding_risk.GroundingRunAdmission,
            **_inputs: str,
        ) -> bool:
            return any(
                ref == receipt.event_ref and row.binding_key == receipt.binding_key
                for ref, row in self._read_chain()
            )

        context = patch.object(
            grounding_risk.GroundingRunBudget, "binding_evidence_matches", ignore_binding_inputs
        )
    with context:
        return int(
            pytest.main(
                [f"tests/unit/runtime/quality/test_grounding_risk.py::{nodes[args.probe]}", "-q"]
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
