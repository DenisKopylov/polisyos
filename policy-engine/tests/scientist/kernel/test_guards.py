"""Tests for polisyos.scientist.kernel.guards — advance_phase, require_artifacts."""
from __future__ import annotations

import pytest

from polisyos.scientist.kernel.fsm import Phase
from polisyos.scientist.kernel.guards import advance_phase, require_artifacts


# ---------------------------------------------------------------------------
# advance_phase
# ---------------------------------------------------------------------------

class TestAdvancePhase:
    def test_valid_transition_intake_to_frame(self):
        state = {"phase": "INTAKE"}
        result = advance_phase(state, Phase.FRAME)
        assert result["phase"] == "FRAME"

    def test_valid_transition_frame_to_preflight(self):
        state = {"phase": "FRAME"}
        result = advance_phase(state, Phase.PREFLIGHT_GOV)
        assert result["phase"] == "PREFLIGHT_GOV"

    def test_self_transition_archive(self):
        state = {"phase": "ARCHIVE"}
        result = advance_phase(state, Phase.ARCHIVE)
        assert result["phase"] == "ARCHIVE"

    def test_self_transition_execute(self):
        state = {"phase": "EXECUTE"}
        result = advance_phase(state, Phase.EXECUTE)
        assert result["phase"] == "EXECUTE"

    def test_invalid_transition_raises(self):
        state = {"phase": "INTAKE"}
        with pytest.raises(ValueError, match="INTAKE -> EXECUTE is not allowed"):
            advance_phase(state, Phase.EXECUTE)

    def test_invalid_transition_decide_to_intake(self):
        state = {"phase": "DECIDE"}
        with pytest.raises(ValueError, match="DECIDE -> INTAKE is not allowed"):
            advance_phase(state, Phase.INTAKE)

    def test_missing_phase_defaults_to_intake(self):
        state = {}
        result = advance_phase(state, Phase.FRAME)
        assert result["phase"] == "FRAME"

    def test_none_phase_defaults_to_intake(self):
        state = {"phase": None}
        result = advance_phase(state, Phase.FRAME)
        assert result["phase"] == "FRAME"

    def test_mutates_state_in_place(self):
        state = {"phase": "INTAKE", "other": 42}
        result = advance_phase(state, Phase.FRAME)
        assert result is state
        assert state["other"] == 42

    def test_phase_stored_as_string_value(self):
        state = {"phase": "INTAKE"}
        advance_phase(state, Phase.FRAME)
        assert state["phase"] == "FRAME"
        assert isinstance(state["phase"], str)


# ---------------------------------------------------------------------------
# require_artifacts
# ---------------------------------------------------------------------------

class TestRequireArtifacts:
    def test_all_present(self):
        state = {"a": 1, "b": "hello", "c": [1, 2]}
        result = require_artifacts(state, ["a", "b", "c"])
        assert result is state

    def test_empty_required_list(self):
        state = {"x": 1}
        result = require_artifacts(state, [])
        assert result is state

    def test_missing_single_key(self):
        state = {"a": 1}
        with pytest.raises(ValueError, match="Missing required artifacts.*b"):
            require_artifacts(state, ["a", "b"])

    def test_missing_multiple_keys(self):
        state = {}
        with pytest.raises(ValueError, match="x.*y"):
            require_artifacts(state, ["x", "y"])

    def test_none_value_treated_as_missing(self):
        state = {"a": None}
        with pytest.raises(ValueError, match="a"):
            require_artifacts(state, ["a"])

    def test_falsy_zero_treated_as_missing(self):
        state = {"a": 0}
        with pytest.raises(ValueError, match="a"):
            require_artifacts(state, ["a"])

    def test_falsy_empty_string_treated_as_missing(self):
        state = {"a": ""}
        with pytest.raises(ValueError, match="a"):
            require_artifacts(state, ["a"])

    def test_falsy_empty_list_treated_as_missing(self):
        state = {"a": []}
        with pytest.raises(ValueError, match="a"):
            require_artifacts(state, ["a"])

    def test_truthy_values_pass(self):
        state = {"a": True, "b": 1, "c": "data", "d": [1]}
        result = require_artifacts(state, ["a", "b", "c", "d"])
        assert result is state
