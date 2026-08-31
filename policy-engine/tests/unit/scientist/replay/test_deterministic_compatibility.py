from __future__ import annotations

import importlib
import importlib.util
import inspect

EXPECTED_PUBLIC_SYMBOLS = (
    "CompletenessLevel",
    "CompletenessReport",
    "MissingArtifact",
    "ReplayBundleMeasurement",
    "ReplayPlan",
    "ReplayStrategy",
    "SeedResolution",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "compare_current_environment",
    "completeness_check",
    "determine_replay_strategy",
    "measure_replayable_audit_bundle",
    "normalize_artifact_id",
    "resolve_effective_seed",
    "set_global_seeds",
    "try_parse_artifact_id",
    "verify_replay",
)


def test_runtime_replay_is_an_exact_identity_preserving_compatibility_facade() -> None:
    """The retired Runtime owner must expose the Scientist-owned objects unchanged."""

    canonical_spec = importlib.util.find_spec("polisyos.scientist.replay.deterministic")
    assert canonical_spec is not None

    canonical = importlib.import_module("polisyos.scientist.replay.deterministic")
    compatibility = importlib.import_module("polisyos.runtime.replay")

    assert tuple(canonical.__all__) == EXPECTED_PUBLIC_SYMBOLS
    assert tuple(compatibility.__all__) == EXPECTED_PUBLIC_SYMBOLS
    for name in EXPECTED_PUBLIC_SYMBOLS:
        canonical_value = getattr(canonical, name)
        compatibility_value = getattr(compatibility, name)
        assert compatibility_value is canonical_value, name
        assert inspect.signature(compatibility_value) == inspect.signature(canonical_value), name

    assert [(member.name, member.value) for member in canonical.ReplayStrategy] == [
        ("FOUNDRY", "foundry"),
        ("SCIENTIST", "scientist"),
        ("NONE", "none"),
    ]
    assert [(member.name, member.value) for member in canonical.CompletenessLevel] == [
        ("COMPLETE", "complete"),
        ("RECOVERABLE", "recoverable"),
        ("INCOMPLETE", "incomplete"),
    ]
    assert [(member.name, member.value) for member in canonical.VerificationMode] == [
        ("BIT_EXACT", "bit_exact"),
        ("CI_BOUNDED", "ci_bounded"),
        ("SKIP", "skip"),
    ]


def test_scientist_replay_consumers_bind_to_the_canonical_owner() -> None:
    """Scientist replay consumers must not resolve their own contracts through Runtime."""

    canonical_spec = importlib.util.find_spec("polisyos.scientist.replay.deterministic")
    assert canonical_spec is not None

    canonical = importlib.import_module("polisyos.scientist.replay.deterministic")
    backend = importlib.import_module("polisyos.scientist.replay.backend")
    verification = importlib.import_module("polisyos.scientist.replay.verification")

    assert backend.ReplayStrategy is canonical.ReplayStrategy
    assert backend.build_replay_plan is canonical.build_replay_plan
    assert backend.verify_replay is canonical.verify_replay
    assert verification.CompletenessLevel is canonical.CompletenessLevel
    assert (
        verification.measure_replayable_audit_bundle
        is canonical.measure_replayable_audit_bundle
    )
