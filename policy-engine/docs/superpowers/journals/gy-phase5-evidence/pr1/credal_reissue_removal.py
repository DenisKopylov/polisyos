"""Remove one controlled-reissue property in memory and run its unchanged semantic test."""

import sys

import pytest

from tools.quality.validation import check_layer3_gy_promotion_contract as owner

mode = sys.argv[1]
if mode == "remove_transition":
    owner._is_authorized_credal_input_epoch_reissue = lambda *_: False
    node = "test_n9_writer_reissues_only_the_governed_credal_input_epoch"
elif mode == "remove_governing_comparison":
    owner._is_authorized_credal_input_epoch_reissue = lambda *_: True
    node = "test_n9_credal_epoch_reissue_refuses_other_frozen_drift[governing_value]"
else:
    raise ValueError(mode)
raise SystemExit(
    pytest.main([f"tests/repo_quality/tools/test_layer3_gy_promotion_contract.py::{node}", "-q"])
)
