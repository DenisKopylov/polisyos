"""Remove the decisive subject property and run the unchanged real consumer gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "probe", choices=(
            "subject_comparison", "source_forwarding", "proof_source_binding", "report_envelope"
        )
    )
    args = parser.parse_args()
    if args.probe == "report_envelope":
        from tools.quality.validation import (
            check_layer3_gy_intervention_substrate_contract as owner,
        )

        arguments = [
            "tests/repo_quality/tools/test_layer3_gy_intervention_substrate_contract.py", "-q",
            "--junitxml=docs/superpowers/journals/corr-evidence/b/s3-own-envelope-removal.xml",
        ]
        with patch.object(owner, "_report_is_synthetic", lambda _payload: True):
            returncode = int(pytest.main(arguments))
        Path("docs/superpowers/journals/corr-evidence/b/s3-removal-pytest-invocation.json").write_text(
            json.dumps({
                "invocation": "pytest.main", "argv": ["pytest", *arguments],
                "returncode": returncode,
                "complete_output_capture": "s3-own-envelope-removal-final.json",
            }, indent=2) + "\n", encoding="utf-8",
        )
        return returncode
    if args.probe == "proof_source_binding":
        from polisyos.runtime.quality import grounding_calibration as owner

        with patch.object(owner, "_world_matches_proof_input", lambda *_args: True):
            return int(pytest.main([
                "tests/unit/runtime/quality/test_grounding_calibration.py::"
                "test_actual_proof_world_pin_replays_original_bytes_time_and_structural_reference",
                "tests/unit/runtime/quality/test_grounding_calibration.py::"
                "test_proof_world_pin_refuses_rehashed_false_source_metadata", "-q",
            ]))
    if args.probe == "subject_comparison":
        from polisyos.foundry.validation import legal_correspondence as owner

        context = patch.object(owner, "_same_subject", lambda _lever, _norm: True)
    else:
        from polisyos.runtime.quality import intervention_substrate as owner

        original = owner.recognize_legal_correspondence
        context = patch.object(owner, "recognize_legal_correspondence",
                               lambda store, _ref, request: original(store, None, request))
    with context:
        return int(pytest.main([
            "tests/unit/runtime/quality/test_intervention_substrate.py::"
            "test_phase5_real_unrelated_law_target_cannot_authorize_a_knob", "-q"]))


if __name__ == "__main__":
    raise SystemExit(main())
