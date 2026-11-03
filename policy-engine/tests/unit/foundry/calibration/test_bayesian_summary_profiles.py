"""Finite point profiles and explicit unknown components in caller-only summaries."""

from __future__ import annotations

import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.foundry.calibration import uncertainty_adapter as owner


def test_finite_summary_mean_uses_exact_binary64_reference() -> None:
    """Large finite draws cannot turn a well-defined point into an infinite claim."""
    for values in ([1e308, 1e308], [1e16, 1.0, -1e16], [-1e308, 1e308]):
        expected = float(sum(map(Fraction.from_float, values)) / len(values))
        summary = owner.summarize_bayesian_calibration_posterior({"theta": values})
        assert summary.posterior_means["theta"] == expected
        assert all(np.isfinite(summary.credible_intervals["theta"]))
        assert summary.parameter_envelopes["theta"].gate_eligible is False


def test_missing_noise_is_not_an_explicit_zero_component() -> None:
    """Unknown emulator noise keeps the total unknown while retaining useful draws."""
    unknown = owner.summarize_bayesian_calibration_posterior({"theta": [0.2, 0.3]})
    explicit = owner.summarize_bayesian_calibration_posterior(
        {"theta": [0.2, 0.3]}, emulator_diagnostics={"emulator_noise_std": 0.0}
    )
    missing = unknown.uncertainty_decomposition["theta"]
    known = explicit.uncertainty_decomposition["theta"]
    assert missing["epistemic"] is not None
    assert missing["aleatoric"] is None and missing["total"] is None
    assert missing["diagnostics"]["component_limitations"]["aleatoric"] == (
        "emulator_noise_std_not_established"
    )
    assert known["diagnostics"]["aleatoric_std"] == 0.0
    assert known["aleatoric"]["confidence_interval"] == (0.25, 0.25)
    assert known["total"] is not None
    for component in ("epistemic", "aleatoric", "total"):
        assert known[component]["gate_eligible"] is False
        assert known[component]["metadata"]["sample_binding_status"] == "caller_input_only"
        assert known[component]["metadata"]["joint_sampling_eligible"] is False
        assert known[component]["metadata"]["approximation"] == "gaussian_components"


def test_single_draw_dispersion_is_unknown_but_multiple_identical_draws_are_zero() -> None:
    single = owner.summarize_bayesian_calibration_posterior(
        {"theta": [0.25]}, emulator_diagnostics={"emulator_noise_std": 0.0}
    ).uncertainty_decomposition["theta"]
    repeated = owner.summarize_bayesian_calibration_posterior(
        {"theta": [0.25, 0.25]}, emulator_diagnostics={"emulator_noise_std": 0.0}
    ).uncertainty_decomposition["theta"]
    assert single["epistemic"] is None and single["total"] is None
    assert single["diagnostics"]["component_limitations"]["epistemic"] == (
        "sample_dispersion_not_established_from_single_draw"
    )
    assert repeated["diagnostics"]["epistemic_std"] == 0.0
    assert repeated["epistemic"]["confidence_interval"] == (0.25, 0.25)
    assert repeated["total"]["gate_eligible"] is False


def test_fresh_candidate_binds_finite_mean_and_detects_owner_removal(tmp_path, monkeypatch) -> None:
    """The actual fresh reader recomputes the profile rather than trusting a marker."""
    values = [1e16, 1.0, -1e16]
    root = tmp_path / "candidate"
    summary = owner.summarize_bayesian_calibration_posterior(
        {"theta": values}, candidate_store=FileSystemCAS(root)
    )
    ref = summary.persisted_candidate_ref
    assert ref is not None
    candidate = owner._load_bayesian_calibration_summary_candidate(FileSystemCAS(root), ref)
    assert candidate.schema_version == "1.1"
    assert candidate.point_reduction == "finite_binary64_mean"
    assert candidate.posterior_means["theta"] == float(Fraction(1, 3))
    with monkeypatch.context() as removed:
        removed.setattr(owner, "finite_binary64_mean", lambda values: float(np.mean(list(values))))
        with pytest.raises(ValueError, match="does not match its retained draw context"):
            owner._load_bayesian_calibration_summary_candidate(FileSystemCAS(root), ref)
    assert (
        owner._load_bayesian_calibration_summary_candidate(FileSystemCAS(root), ref).posterior_means
        == candidate.posterior_means
    )


@pytest.mark.parametrize(
    ("values", "emulator"),
    [
        ([1e16, 1.0, -1e16], {}),
        ([0.25], {}),
        ([0.21, 0.24, 0.25, 0.23, 0.22], {"emulator_noise_std": {"theta": 0.01}}),
    ],
    ids=["cancellation", "singleton_unknown_noise", "explicit_noise"],
)
def test_actual_entry_source_legacy_candidate_still_fresh_reads(tmp_path, values, emulator) -> None:
    """One pinned old module generates real v1 bytes using today's declared dependencies."""
    repo = Path(__file__).resolve().parents[5]
    if not (repo / ".git").exists():
        pytest.skip("Pinned Git-source compatibility witness requires a source checkout")
    old_source = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "show",
            "50389f682411555e03911152f792519116e63cb1:"
            "policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py",
        ],
        text=True,
    )
    name = "_source_qualified_legacy_calibration_adapter"
    module = ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(old_source, "<git:50389f682:uncertainty_adapter.py>", "exec"), module.__dict__)
        root = tmp_path / "old-candidate"
        old = module.summarize_bayesian_calibration_posterior(
            {"theta": values},
            emulator_diagnostics=emulator,
            candidate_store=FileSystemCAS(root),
        )
        expected_old = module._bayesian_calibration_summary_candidate_payload(old).model_dump(
            mode="json"
        )
        assert "uncertainty_decomposition" not in expected_old
        assert "point_reduction" not in expected_old
        old_ref = old.persisted_candidate_ref
        assert old_ref is not None
        exact_bytes = FileSystemCAS(root).get_bytes(old_ref)
        loaded = owner._load_bayesian_calibration_summary_candidate(FileSystemCAS(root), old_ref)
        assert loaded.schema_version == "1.0" and loaded.point_reduction is None
        assert loaded.model_dump(mode="json") == expected_old
        assert loaded.posterior_means["theta"] == float(np.mean(values))
        assert FileSystemCAS(root).get_bytes(old_ref) == exact_bytes
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize(
    ("schema_name", "schema_version"),
    [
        ("polisyos.foundry.calibration.BayesianCalibrationSummaryCandidate", "1.0"),
        ("unrelated.candidate", "1.1"),
    ],
)
def test_candidate_profile_requires_matching_selected_manifest(
    tmp_path, schema_name, schema_version
) -> None:
    """Equal valid point bytes do not admit an unrelated selected profile."""
    store = FileSystemCAS(tmp_path / "candidate-profile")
    summary = owner.summarize_bayesian_calibration_posterior({"theta": [0.2, 0.3]})
    payload = owner._bayesian_calibration_summary_candidate_payload(summary)
    wrong = store.put_json(
        payload,
        PutOptions(
            kind="foundry.calibration.bayesian_posterior_summary_candidate",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected = owner._BayesianCalibrationSummaryCandidateRef.model_validate(
        wrong.model_dump(mode="python")
    )
    with pytest.raises(ValueError, match="manifest does not match its point profile"):
        owner._load_bayesian_calibration_summary_candidate(store, selected)
