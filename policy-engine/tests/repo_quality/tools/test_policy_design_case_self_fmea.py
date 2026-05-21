"""Compatibility entrypoint for archived self-FMEA validation checks."""

from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    test_policy_design_case_blocks_malformed_non_adversarial_self_fmea_record,
    test_policy_design_case_blocks_missing_non_adversarial_self_fmea_record,
)  # noqa: F401
