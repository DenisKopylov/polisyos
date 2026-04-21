"""Latent-separation diagnostics for research-only latent discovery bundles."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_discovery import LatentTrustLevel

SEPARATION_DIAGNOSTICS_KEY = "separation_diagnostics"
SEPARATION_DIAGNOSTIC_INPUTS_KEY = "separation_diagnostic_inputs"

_DIAGNOSTIC_BLOCKS = ("measurement_block", "proxy_block", "environment_block")
_RESOLUTION_LABELS = {
    "measurement_error",
    "proxy_mismatch",
    "latent_confounding",
    "mixed",
    "unresolved",
}
_SEPARATED_PAIRS = {
    "measurement_vs_proxy",
    "proxy_vs_confounding",
    "measurement_vs_confounding",
}
_UNRESOLVED_STATUSES = {
    "",
    "mixed",
    "missing",
    "not_run",
    "unknown",
    "unresolved",
    "insufficient",
    "incomplete",
}
_CONFLICT_STATUSES = {"conflicted", "contradicted", "inconsistent"}
_POSITIVE_STATUSES = {
    "accepted",
    "calibrated",
    "certified",
    "passed",
    "replicated",
    "restored",
    "stable",
    "supported",
    "validated",
}
_REPLICATION_CHANNELS = {
    "held_out_environments",
    "heldout_environments",
    "environment_holdout",
    "alternative_proxy_subsets",
    "independent_discovery_hypothesis",
    "independent_discovery_hypotheses",
    "independent_hypothesis",
    "independent_hypotheses",
}
_TEST_FAMILIES = (
    "single_signal_tetrad",
    "measurement_invariance_dif",
    "proximal_bridge_overidentification",
    "post_calibration_environment_invariance",
)
_MEASUREMENT_TEST_KEYS = ("tetrad_test", "invariance_test")
_PROXY_TEST_KEYS = ("bridge_test", "bridge_stability")
_ENVIRONMENT_TEST_KEYS = ("residual_invariance", "post_calibration_shift")
_POSITIVE_FRAGMENTS = (
    "accepted",
    "calibrated",
    "certified",
    "pass",
    "passed",
    "resolved",
    "restored",
    "stable",
    "supported",
    "validated",
)
_NEGATIVE_FRAGMENTS = (
    "conflicted",
    "contradicted",
    "drift",
    "failed",
    "mismatch",
    "not_restored",
    "rejected",
    "unstable",
    "violated",
)
_MISMATCH_FRAGMENTS = (
    "bad_proxy",
    "drift",
    "failed",
    "flagged",
    "mismatch",
    "noninvariant",
    "proxy_drift",
    "unstable",
    "violated",
)
_RESTORED_ENVIRONMENT_FRAGMENTS = (
    "absorbed",
    "disappeared",
    "resolved",
    "restored",
    "stable",
    "supported",
)
_NOT_RESTORED_ENVIRONMENT_FRAGMENTS = (
    "dependent",
    "drift",
    "failed",
    "not_restored",
    "shift",
    "unstable",
    "violated",
)
_BRIDGE_POSITIVE_FRAGMENTS = (
    "exists",
    "identified",
    "passed",
    "solved",
    "stable",
    "supported",
)
_BRIDGE_NEGATIVE_FRAGMENTS = (
    "failed",
    "missing",
    "not_solved",
    "not_supported",
    "rejected",
    "unstable",
    "violated",
)


class LatentSeparationMeasurementInput(BaseModel):
    """Typed measurement-evidence block used to compute Stage 9.2 diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str | None = None
    tetrad_test: str | None = None
    invariance_test: str | None = None
    repeated_indicator_blocks: list[str] = Field(default_factory=list)
    repeated_indicator_block_variables: dict[str, list[str]] = Field(default_factory=dict)
    flagged_indicators: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LatentSeparationProxyInput(BaseModel):
    """Typed proxy-evidence block used to compute Stage 9.2 diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str | None = None
    bridge_test: str | None = None
    bridge_stability: str | None = None
    proxy_blocks: list[str] = Field(default_factory=list)
    proxy_block_variables: dict[str, list[str]] = Field(default_factory=dict)
    flagged_proxies: list[str] = Field(default_factory=list)
    bridge_plausibility_severity: str | None = None
    bridge_fallback_disposition: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LatentSeparationEnvironmentInput(BaseModel):
    """Typed environment-evidence block used to compute Stage 9.2 diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str | None = None
    residual_invariance: str | None = None
    post_calibration_shift: str | None = None
    environments: list[str] = Field(default_factory=list)
    n_env: int | None = Field(default=None, ge=0)
    shift_type_label: str | None = None
    certification_level: str | None = None
    route_to_latent_aware_discovery: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LatentSeparationDiagnosticInputs(BaseModel):
    """Typed raw Stage 9.2 payload emitted during hypothesis enrichment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_latent_nodes: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    design: dict[str, Any] = Field(default_factory=dict)
    measurement_block: LatentSeparationMeasurementInput | None = None
    proxy_block: LatentSeparationProxyInput | None = None
    environment_block: LatentSeparationEnvironmentInput | None = None
    replication: dict[str, Any] | None = None
    prerequisites_missing: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "LatentSeparationDiagnosticInputs | None":
        if not isinstance(value, Mapping):
            return None
        return cls.model_validate(value)


def compute_latent_separation_diagnostics(
    data: Mapping[str, Any] | None,
    design: Mapping[str, Any] | None = None,
    *,
    rank_tol: float = 0.15,
    invariance_tol: float = 0.25,
    residual_tol: float = 0.15,
    bridge_seed: int = 0,
) -> dict[str, Any]:
    """Compute Stage 9.2 latent-separation diagnostics from data/design inputs.

    The v1 producer is deliberately conservative: unsupported test families
    produce ``unresolved`` evidence rather than raising trust by metadata shape
    alone.
    """

    if not isinstance(data, Mapping):
        return _computed_unresolved_payload(
            reason="data_missing",
            design=_computed_design_payload({}, design),
        )

    design_payload = _computed_design_payload(data, design)
    columns = _column_arrays(data)
    n_obs = _common_length(columns.values())
    if n_obs is None:
        return _computed_unresolved_payload(
            reason="numeric_columns_missing",
            design=design_payload,
        )

    env = _environment_labels(data, design, n_obs=n_obs)
    repeated_blocks = _variable_blocks(
        design_payload.get("repeated_indicator_block_variables")
        or design_payload.get("repeated_indicator_blocks"),
        strings_as_single_block=True,
    )
    proxy_blocks = _variable_blocks(
        design_payload.get("proxy_block_variables")
        or design_payload.get("proxy_blocks"),
        strings_as_single_block=False,
    )

    measurement_block, latent_score = _compute_measurement_block(
        columns,
        repeated_blocks,
        env=env,
        rank_tol=rank_tol,
        invariance_tol=invariance_tol,
    )
    proxy_block = _compute_proxy_block(
        columns,
        proxy_blocks,
        env=env,
        latent_score=latent_score,
        design=design_payload,
        bridge_seed=bridge_seed,
    )
    environment_block = _compute_environment_block(
        columns,
        repeated_blocks,
        env=env,
        latent_score=latent_score,
        design=design_payload,
        residual_tol=residual_tol,
    )
    resolution_label, separated_pairs, conflicts = _computed_resolution(
        measurement_block,
        proxy_block,
        environment_block,
    )

    payload: dict[str, Any] = {
        "resolution_label": resolution_label,
        "status": "computed" if resolution_label != "unresolved" else "unresolved",
        "source": "computed_from_data",
        "design": design_payload,
        "measurement_block": measurement_block,
        "proxy_block": proxy_block,
        "environment_block": environment_block,
        "separated_pairs": separated_pairs,
        "support_scope": _computed_support_scope(design_payload),
    }
    if conflicts:
        payload["conflicts"] = conflicts
    return payload


def compute_latent_separation_diagnostics_from_inputs(
    inputs: Mapping[str, Any] | LatentSeparationDiagnosticInputs | None,
) -> dict[str, Any]:
    """Compute Stage 9.2 diagnostics from typed enrichment inputs."""

    parsed = (
        inputs
        if isinstance(inputs, LatentSeparationDiagnosticInputs)
        else LatentSeparationDiagnosticInputs.from_mapping(inputs)
    )
    if parsed is None:
        return _computed_unresolved_payload(reason="inputs_missing", design={})

    if parsed.data:
        payload = compute_latent_separation_diagnostics(parsed.data, parsed.design)
        if parsed.replication is not None:
            payload["replication"] = dict(parsed.replication)
        if parsed.prerequisites_missing:
            payload["prerequisites_missing"] = list(parsed.prerequisites_missing)
        return payload

    measurement_block = _structured_measurement_block(parsed.measurement_block)
    proxy_block = _structured_proxy_block(parsed.proxy_block)
    environment_block = _structured_environment_block(parsed.environment_block)
    design_payload = _structured_design_payload(parsed)
    if parsed.prerequisites_missing:
        design_payload["prerequisites_missing"] = list(parsed.prerequisites_missing)

    resolution_label, separated_pairs, conflicts = _computed_resolution(
        measurement_block,
        proxy_block,
        environment_block,
    )
    if parsed.prerequisites_missing:
        unresolved = any(
            str(reason).strip()
            for reason in parsed.prerequisites_missing
            if str(reason).strip()
        )
        if unresolved and resolution_label not in {"mixed", "measurement_error", "proxy_mismatch", "latent_confounding"}:
            resolution_label = "unresolved"

    payload: dict[str, Any] = {
        "resolution_label": resolution_label,
        "status": "computed" if resolution_label != "unresolved" else "unresolved",
        "source": "computed_from_inputs",
        "design": design_payload,
        "measurement_block": measurement_block,
        "proxy_block": proxy_block,
        "environment_block": environment_block,
        "separated_pairs": separated_pairs,
        "support_scope": _computed_support_scope(design_payload),
    }
    if parsed.replication is not None:
        payload["replication"] = dict(parsed.replication)
    if parsed.prerequisites_missing:
        payload["prerequisites_missing"] = list(parsed.prerequisites_missing)
    if conflicts:
        payload["conflicts"] = conflicts
    return payload


def metadata_with_computed_latent_separation(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prefer computed Stage 9.2 diagnostics when raw diagnostic inputs exist."""

    if not isinstance(metadata, Mapping):
        return {}
    output = dict(metadata)
    raw_inputs = (
        output.get(SEPARATION_DIAGNOSTIC_INPUTS_KEY)
        or output.get("separation_diagnostics_inputs")
        or output.get("latent_separation_inputs")
    )
    if not isinstance(raw_inputs, Mapping):
        return output

    if _looks_like_structured_inputs(raw_inputs):
        computed = compute_latent_separation_diagnostics_from_inputs(raw_inputs)
        output[SEPARATION_DIAGNOSTICS_KEY] = computed
        output["separation_diagnostics_source"] = computed.get("source", "computed")
        return output

    data_payload = raw_inputs.get("data")
    if not isinstance(data_payload, Mapping):
        data_payload = raw_inputs
    design_payload = (
        raw_inputs.get("design")
        if isinstance(raw_inputs.get("design"), Mapping)
        else output.get("separation_design")
    )
    if not isinstance(design_payload, Mapping):
        design_payload = output.get("latent_separation_design")
    if not isinstance(design_payload, Mapping):
        design_payload = None

    computed = compute_latent_separation_diagnostics(data_payload, design_payload)
    output[SEPARATION_DIAGNOSTICS_KEY] = computed
    output["separation_diagnostics_source"] = "computed"
    return output


def separation_diagnostics_payload(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return normalized Stage 9.2 diagnostics from bundle metadata."""
    if not isinstance(metadata, Mapping):
        return None
    payload = metadata.get(SEPARATION_DIAGNOSTICS_KEY)
    if not isinstance(payload, Mapping):
        return None
    return _normalize_payload(payload)


def certify_latent_separation_trust(
    metadata: Mapping[str, Any] | None,
    *,
    fallback: LatentTrustLevel = LatentTrustLevel.RESEARCH,
) -> LatentTrustLevel:
    """Derive trust from Stage 9.2 diagnostics when they are present."""
    diagnostics = separation_diagnostics_payload(metadata)
    if diagnostics is None:
        return fallback
    if not _has_sufficient_design(diagnostics):
        return LatentTrustLevel.RESEARCH
    if _resolution_label(diagnostics) in {"", "mixed", "unresolved"}:
        return LatentTrustLevel.RESEARCH
    if _has_unresolved_block(diagnostics) or _has_direct_conflict(diagnostics):
        return LatentTrustLevel.RESEARCH
    if not _has_complete_falsification_payload(diagnostics):
        return LatentTrustLevel.RESEARCH
    certified_pairs = certified_latent_separation_pairs(diagnostics)
    if not certified_pairs:
        return LatentTrustLevel.RESEARCH
    if _has_replication_evidence(diagnostics, certified_pairs):
        return LatentTrustLevel.VALIDATED
    return LatentTrustLevel.CONDITIONAL


def merge_latent_separation_diagnostics_payloads(
    values: list[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Merge diagnostics from multiple latent hypotheses without dropping provenance."""
    normalized = [_normalize_payload(value) for value in values if isinstance(value, Mapping)]
    if not normalized:
        return None
    if len(normalized) == 1:
        return normalized[0]

    labels = [_resolution_label(value) for value in normalized]
    same_label = (
        bool(labels)
        and len(set(labels)) == 1
        and labels[0] not in {"", "mixed", "unresolved"}
    )
    pair_sets = [set(_normalized_pairs(value)) for value in normalized]
    shared_pairs = set.intersection(*pair_sets) if pair_sets else set()
    union_pairs = sorted(set.union(*pair_sets)) if pair_sets else []
    base = dict(normalized[0])
    base["source_diagnostics"] = normalized

    if same_label and shared_pairs:
        base["resolution_label"] = labels[0]
        base["separated_pairs"] = sorted(shared_pairs)
        replication = dict(
            base.get("replication") if isinstance(base.get("replication"), dict) else {}
        )
        replication.setdefault("status", "passed")
        replication.setdefault("independent_discovery_hypothesis", True)
        replication.setdefault("replicated_resolution_label", labels[0])
        replication.setdefault("replicated_separated_pairs", sorted(shared_pairs))
        base["replication"] = replication
        return base

    base["resolution_label"] = "mixed"
    base["separated_pairs"] = union_pairs
    base["conflicts"] = _dedupe_strings(
        [
            *list(base.get("conflicts", []) or []),
            "latent_separation:inconsistent_resolution_across_hypotheses",
        ]
    )
    return base


def latent_separation_assumption_surfaces(
    diagnostics: Mapping[str, Any] | None,
) -> list[str]:
    """Human-readable assumptions surfaced by Stage 9.2 diagnostics."""
    payload = _normalize_payload(diagnostics) if isinstance(diagnostics, Mapping) else None
    if payload is None:
        return []
    surfaces = [
        f"latent_separation_resolution:{_resolution_label(payload) or 'unresolved'}",
        *(
            f"latent_separation_pair:{pair}"
            for pair in _normalized_pairs(payload)
        ),
    ]
    for scope in payload.get("support_scope", []) or []:
        text = str(scope).strip()
        if text:
            surfaces.append(f"latent_separation_scope:{text}")
    design = payload.get("design")
    if isinstance(design, Mapping):
        if _environment_count(design) >= 2:
            surfaces.append("latent_separation_design:multi_environment")
        if _proxy_block_count(design) >= 2:
            surfaces.append("latent_separation_design:two_proxy_blocks")
        if _repeated_indicator_block_count(design) >= 1:
            surfaces.append("latent_separation_design:repeated_indicators")
    return _dedupe_strings(surfaces)


def latent_separation_falsification_surfaces(
    diagnostics: Mapping[str, Any] | None,
) -> list[str]:
    """Falsification-test family surfaces required by Stage 9.2 diagnostics."""
    payload = _normalize_payload(diagnostics) if isinstance(diagnostics, Mapping) else None
    if payload is None:
        return []
    tests = [f"latent_separation:{family}" for family in _TEST_FAMILIES]
    for block_name in _DIAGNOSTIC_BLOCKS:
        block = payload.get(block_name)
        if not isinstance(block, Mapping):
            continue
        for key in (
            "test",
            "tests",
            "tetrad_test",
            "invariance_test",
            "bridge_test",
            "bridge_stability",
            "residual_invariance",
            "post_calibration_shift",
        ):
            value = block.get(key)
            if isinstance(value, list):
                tests.extend(f"latent_separation:{str(item).strip()}" for item in value)
            elif value is not None:
                tests.append(f"latent_separation:{str(value).strip()}")
    return _dedupe_strings(tests)


def certified_latent_separation_pairs(
    diagnostics: Mapping[str, Any] | None,
) -> list[str]:
    """Return pairwise separations whose evidence satisfies Stage 9.2 rules."""
    payload = _normalize_payload(diagnostics) if isinstance(diagnostics, Mapping) else None
    if payload is None:
        return []
    certified: list[str] = []
    for pair in _normalized_pairs(payload):
        pair_is_certified = (
            (
                pair == "measurement_vs_proxy"
                and _certifies_measurement_vs_proxy(payload)
            )
            or (
                pair == "proxy_vs_confounding"
                and _certifies_proxy_vs_confounding(payload)
            )
            or (
                pair == "measurement_vs_confounding"
                and _certifies_measurement_vs_confounding(payload)
            )
        )
        if pair_is_certified:
            certified.append(pair)
    return _dedupe_strings(certified)


def _looks_like_structured_inputs(payload: Mapping[str, Any]) -> bool:
    return any(
        key in payload
        for key in (
            "measurement_block",
            "proxy_block",
            "environment_block",
            "candidate_latent_nodes",
            "prerequisites_missing",
        )
    )


def _structured_measurement_block(
    block: LatentSeparationMeasurementInput | None,
) -> dict[str, Any]:
    if block is None:
        return {
            "status": "unsupported",
            "tetrad_test": "single_signal_tetrad_unresolved",
            "invariance_test": "measurement_invariance_unresolved",
            "reason": "measurement_block_missing",
        }
    status = block.status or _default_block_status(
        block.tetrad_test,
        block.invariance_test,
    )
    payload: dict[str, Any] = {
        "status": status,
        "tetrad_test": block.tetrad_test or "single_signal_tetrad_unresolved",
        "invariance_test": block.invariance_test or "measurement_invariance_unresolved",
    }
    if block.repeated_indicator_blocks:
        payload["repeated_indicator_blocks"] = list(block.repeated_indicator_blocks)
    if block.repeated_indicator_block_variables:
        payload["repeated_indicator_block_variables"] = {
            key: list(value) for key, value in block.repeated_indicator_block_variables.items()
        }
    if block.flagged_indicators:
        payload["flagged_indicators"] = list(block.flagged_indicators)
    payload.update(dict(block.metadata))
    return payload


def _structured_proxy_block(
    block: LatentSeparationProxyInput | None,
) -> dict[str, Any]:
    if block is None:
        return {
            "status": "unsupported",
            "bridge_test": "proximal_bridge_unresolved",
            "bridge_stability": "cross_environment_unresolved",
            "reason": "proxy_block_missing",
        }
    status = block.status or _default_block_status(
        block.bridge_test,
        block.bridge_stability,
    )
    payload: dict[str, Any] = {
        "status": status,
        "bridge_test": block.bridge_test or "proximal_bridge_unresolved",
        "bridge_stability": block.bridge_stability or "cross_environment_unresolved",
    }
    if block.proxy_blocks:
        payload["proxy_blocks"] = list(block.proxy_blocks)
    if block.proxy_block_variables:
        payload["proxy_block_variables"] = {
            key: list(value) for key, value in block.proxy_block_variables.items()
        }
    if block.flagged_proxies:
        payload["flagged_proxies"] = list(block.flagged_proxies)
    if block.bridge_plausibility_severity is not None:
        payload["bridge_plausibility_severity"] = block.bridge_plausibility_severity
    if block.bridge_fallback_disposition is not None:
        payload["bridge_fallback_disposition"] = block.bridge_fallback_disposition
    payload.update(dict(block.metadata))
    return payload


def _structured_environment_block(
    block: LatentSeparationEnvironmentInput | None,
) -> dict[str, Any]:
    if block is None:
        return {
            "status": "unsupported",
            "residual_invariance": "post_calibration_residual_invariance_unresolved",
            "post_calibration_shift": "unresolved",
            "reason": "environment_block_missing",
        }
    status = block.status or _default_block_status(
        block.residual_invariance,
        block.post_calibration_shift,
    )
    payload: dict[str, Any] = {
        "status": status,
        "residual_invariance": (
            block.residual_invariance or "post_calibration_residual_invariance_unresolved"
        ),
        "post_calibration_shift": block.post_calibration_shift or "unresolved",
    }
    if block.environments:
        payload["environments"] = list(block.environments)
    if block.n_env is not None:
        payload["n_env"] = int(block.n_env)
    if block.shift_type_label is not None:
        payload["shift_type_label"] = block.shift_type_label
    if block.certification_level is not None:
        payload["certification_level"] = block.certification_level
    if block.route_to_latent_aware_discovery is not None:
        payload["route_to_latent_aware_discovery"] = bool(
            block.route_to_latent_aware_discovery
        )
    payload.update(dict(block.metadata))
    return payload


def _structured_design_payload(inputs: LatentSeparationDiagnosticInputs) -> dict[str, Any]:
    design_payload = dict(inputs.design)
    measurement = inputs.measurement_block
    proxy = inputs.proxy_block
    environment = inputs.environment_block
    if measurement is not None:
        if measurement.repeated_indicator_blocks:
            design_payload.setdefault(
                "repeated_indicator_blocks",
                list(measurement.repeated_indicator_blocks),
            )
        if measurement.repeated_indicator_block_variables:
            design_payload.setdefault(
                "repeated_indicator_block_variables",
                {
                    key: list(value)
                    for key, value in measurement.repeated_indicator_block_variables.items()
                },
            )
    if proxy is not None:
        if proxy.proxy_blocks:
            design_payload.setdefault("proxy_blocks", list(proxy.proxy_blocks))
        if proxy.proxy_block_variables:
            design_payload.setdefault(
                "proxy_block_variables",
                {key: list(value) for key, value in proxy.proxy_block_variables.items()},
            )
    if environment is not None:
        if environment.environments:
            design_payload.setdefault("environments", list(environment.environments))
        if environment.n_env is not None:
            design_payload["n_env"] = int(environment.n_env)
    if "n_env" not in design_payload and isinstance(design_payload.get("environments"), list):
        design_payload["n_env"] = len(design_payload["environments"])
    return _computed_design_payload({}, design_payload)


def _default_block_status(*values: object) -> str:
    tokens = [_normalize_token(value) for value in values if str(value or "").strip()]
    if any(token in _CONFLICT_STATUSES for token in tokens):
        return "conflicted"
    if any(any(fragment in token for fragment in _NEGATIVE_FRAGMENTS) for token in tokens):
        return "failed"
    if any(any(fragment in token for fragment in _POSITIVE_FRAGMENTS) for token in tokens):
        return "passed"
    return "unsupported"


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    label = _normalize_token(normalized.get("resolution_label"))
    normalized["resolution_label"] = label
    normalized["separated_pairs"] = _normalized_pairs(normalized)
    if "support_scope" in normalized:
        normalized["support_scope"] = _dedupe_strings(
            [str(value) for value in list(normalized.get("support_scope") or [])]
        )
    return normalized


def _resolution_label(payload: Mapping[str, Any]) -> str:
    return _normalize_token(payload.get("resolution_label"))


def _normalized_pairs(payload: Mapping[str, Any]) -> list[str]:
    values = payload.get("separated_pairs", [])
    if isinstance(values, str):
        raw = [values]
    elif isinstance(values, list | tuple | set):
        raw = list(values)
    else:
        raw = []
    return [
        value
        for value in _dedupe_strings(str(item) for item in raw)
        if value in _SEPARATED_PAIRS
    ]


def _has_sufficient_design(payload: Mapping[str, Any]) -> bool:
    design = payload.get("design")
    if not isinstance(design, Mapping):
        return False
    return (
        _environment_count(design) >= 2
        and _proxy_block_count(design) >= 2
        and _repeated_indicator_block_count(design) >= 1
    )


def _has_complete_falsification_payload(payload: Mapping[str, Any]) -> bool:
    measurement_block = payload.get("measurement_block")
    proxy_block = payload.get("proxy_block")
    environment_block = payload.get("environment_block")
    return (
        isinstance(measurement_block, Mapping)
        and isinstance(proxy_block, Mapping)
        and isinstance(environment_block, Mapping)
        and _block_has_required_tests(measurement_block, _MEASUREMENT_TEST_KEYS)
        and _block_has_required_tests(proxy_block, _PROXY_TEST_KEYS)
        and _block_has_required_tests(environment_block, _ENVIRONMENT_TEST_KEYS)
    )


def _environment_count(design: Mapping[str, Any]) -> int:
    explicit = _as_int(design.get("n_env"))
    if explicit is not None:
        return explicit
    environments = design.get("environments")
    if isinstance(environments, list | tuple | set):
        return len(environments)
    return 0


def _proxy_block_count(design: Mapping[str, Any]) -> int:
    explicit = _as_int(design.get("n_proxy_blocks"))
    if explicit is not None:
        return explicit
    blocks = design.get("proxy_blocks")
    if isinstance(blocks, Mapping):
        return len(blocks)
    if isinstance(blocks, list | tuple | set):
        return len(blocks)
    return 0


def _repeated_indicator_block_count(design: Mapping[str, Any]) -> int:
    explicit = _as_int(design.get("n_repeated_indicator_blocks"))
    if explicit is not None:
        return explicit
    blocks = design.get("repeated_indicator_blocks")
    if isinstance(blocks, Mapping):
        return len(blocks)
    if isinstance(blocks, list | tuple | set):
        return len(blocks)
    return 0


def _has_unresolved_block(payload: Mapping[str, Any]) -> bool:
    for block_name in _DIAGNOSTIC_BLOCKS:
        block = payload.get(block_name)
        if not isinstance(block, Mapping):
            return True
        status = _normalize_token(block.get("status"))
        if status in _UNRESOLVED_STATUSES:
            return True
        if status in _CONFLICT_STATUSES:
            return True
    return False


def _certifies_measurement_vs_proxy(payload: Mapping[str, Any]) -> bool:
    label = _resolution_label(payload)
    measurement_block = payload.get("measurement_block")
    proxy_block = payload.get("proxy_block")
    environment_block = payload.get("environment_block")
    if not all(
        isinstance(block, Mapping)
        for block in (measurement_block, proxy_block, environment_block)
    ):
        return False
    if label == "measurement_error":
        return _measurement_block_supported(measurement_block) and _environment_restored(
            environment_block
        )
    if label == "proxy_mismatch":
        return _proxy_mismatch_supported(measurement_block, proxy_block)
    return False


def _certifies_proxy_vs_confounding(payload: Mapping[str, Any]) -> bool:
    label = _resolution_label(payload)
    measurement_block = payload.get("measurement_block")
    proxy_block = payload.get("proxy_block")
    if not isinstance(measurement_block, Mapping) or not isinstance(proxy_block, Mapping):
        return False
    if label == "latent_confounding":
        return _measurement_block_supported(measurement_block) and _bridge_supported(
            proxy_block
        )
    if label == "proxy_mismatch":
        return _measurement_block_supported(measurement_block) and _proxy_mismatch_supported(
            measurement_block,
            proxy_block,
        )
    return False


def _certifies_measurement_vs_confounding(payload: Mapping[str, Any]) -> bool:
    label = _resolution_label(payload)
    measurement_block = payload.get("measurement_block")
    proxy_block = payload.get("proxy_block")
    environment_block = payload.get("environment_block")
    if not all(
        isinstance(block, Mapping)
        for block in (measurement_block, proxy_block, environment_block)
    ):
        return False
    if label == "latent_confounding":
        return (
            _measurement_block_supported(measurement_block)
            and _bridge_supported(proxy_block)
            and _environment_not_restored(environment_block)
        )
    if label == "measurement_error":
        return (
            _measurement_block_supported(measurement_block)
            and _environment_restored(environment_block)
            and _bridge_not_supported(proxy_block)
        )
    return False


def _has_direct_conflict(payload: Mapping[str, Any]) -> bool:
    status = _normalize_token(payload.get("status"))
    if status in _CONFLICT_STATUSES:
        return True
    for key in ("conflicts", "contradictions", "conflicting_tests", "direct_conflicts"):
        values = payload.get(key)
        if isinstance(values, str) and values.strip():
            return True
        if isinstance(values, list | tuple | set) and any(str(value).strip() for value in values):
            return True
    return False


def _has_replication_evidence(
    payload: Mapping[str, Any],
    certified_pairs: list[str],
) -> bool:
    replication = payload.get("replication")
    if not isinstance(replication, Mapping):
        return False
    status = _normalize_token(replication.get("status"))
    has_channel = status in _POSITIVE_STATUSES or any(
        bool(replication.get(channel)) for channel in _REPLICATION_CHANNELS
    )
    if not has_channel:
        return False
    replicated_label = _normalize_token(replication.get("replicated_resolution_label"))
    if replicated_label and replicated_label != _resolution_label(payload):
        return False
    replicated_pairs = replication.get("replicated_separated_pairs")
    if replicated_pairs is None:
        return True
    pair_set = set(certified_pairs)
    replicated_pair_set = set(
        _normalized_pairs({"separated_pairs": replicated_pairs})
    )
    return bool(pair_set) and pair_set.issubset(replicated_pair_set)


def _block_has_required_tests(
    block: Mapping[str, Any],
    required_keys: tuple[str, ...],
) -> bool:
    return all(_has_observation(block.get(key)) for key in required_keys)


def _measurement_block_supported(block: Mapping[str, Any]) -> bool:
    status = _normalize_token(block.get("status"))
    return _matches_any(status, _POSITIVE_FRAGMENTS) and not _matches_any(
        block,
        _NEGATIVE_FRAGMENTS,
    )


def _bridge_supported(block: Mapping[str, Any]) -> bool:
    if _bridge_not_supported(block):
        return False
    return _matches_any(block.get("bridge_test"), _BRIDGE_POSITIVE_FRAGMENTS) and _matches_any(
        block.get("bridge_stability"),
        _BRIDGE_POSITIVE_FRAGMENTS,
    )


def _bridge_not_supported(block: Mapping[str, Any]) -> bool:
    return _matches_any(block, _BRIDGE_NEGATIVE_FRAGMENTS)


def _environment_restored(block: Mapping[str, Any]) -> bool:
    if _environment_not_restored(block):
        return False
    return _matches_any(
        block.get("residual_invariance"),
        _RESTORED_ENVIRONMENT_FRAGMENTS,
    ) or _matches_any(block.get("post_calibration_shift"), _RESTORED_ENVIRONMENT_FRAGMENTS)


def _environment_not_restored(block: Mapping[str, Any]) -> bool:
    return _matches_any(
        block.get("residual_invariance"),
        _NOT_RESTORED_ENVIRONMENT_FRAGMENTS,
    ) or _matches_any(
        block.get("post_calibration_shift"),
        _NOT_RESTORED_ENVIRONMENT_FRAGMENTS,
    )


def _proxy_mismatch_supported(
    measurement_block: Mapping[str, Any],
    proxy_block: Mapping[str, Any],
) -> bool:
    return _matches_any(measurement_block, _MISMATCH_FRAGMENTS) or _matches_any(
        proxy_block,
        _MISMATCH_FRAGMENTS + _BRIDGE_NEGATIVE_FRAGMENTS,
    )


def _has_observation(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list | tuple | set):
        return bool(value)
    return True


def _normalize_token(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _as_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_strings(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _iter_signal_tokens(value: object) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        token = _normalize_token(value)
        if token:
            yield token
        return
    if isinstance(value, bool):
        yield _normalize_token(value)
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_signal_tokens(nested)
        return
    if isinstance(value, list | tuple | set):
        for nested in value:
            yield from _iter_signal_tokens(nested)
        return
    token = _normalize_token(value)
    if token:
        yield token


def _matches_any(value: object, fragments: tuple[str, ...]) -> bool:
    fragment_set = tuple(_normalize_token(fragment) for fragment in fragments)
    for token in _iter_signal_tokens(value):
        if any(fragment in token for fragment in fragment_set):
            return True
    return False


def _computed_design_payload(
    data: Mapping[str, Any],
    design: Mapping[str, Any] | None,
) -> dict[str, Any]:
    design_map = dict(design or {})
    n_obs = _common_length(_column_arrays(data).values())
    env = _environment_labels(data, design, n_obs=n_obs) if n_obs is not None else None
    proxy_blocks = _variable_blocks(
        design_map.get("proxy_blocks"),
        strings_as_single_block=False,
    )
    repeated_blocks = _variable_blocks(
        design_map.get("repeated_indicator_blocks"),
        strings_as_single_block=True,
    )
    if not repeated_blocks:
        repeated_blocks = _variable_blocks(
            design_map.get("indicator_blocks"),
            strings_as_single_block=True,
        )
    if not proxy_blocks:
        proxy_blocks = _variable_blocks(
            design_map.get("proximal_proxy_blocks"),
            strings_as_single_block=False,
        )
    environments = sorted({str(value) for value in env}) if env is not None else []
    n_env = _as_int(design_map.get("n_env"))
    return {
        **design_map,
        "n_env": n_env if n_env is not None else len(environments),
        "environments": list(design_map.get("environments") or environments),
        "proxy_blocks": [block_id for block_id, _ in proxy_blocks],
        "proxy_block_variables": {
            block_id: list(variables) for block_id, variables in proxy_blocks
        },
        "repeated_indicator_blocks": [block_id for block_id, _ in repeated_blocks],
        "repeated_indicator_block_variables": {
            block_id: list(variables) for block_id, variables in repeated_blocks
        },
        "treatment": str(
            design_map.get("treatment")
            or design_map.get("treatment_variable")
            or "treatment"
        ),
        "outcome": str(
            design_map.get("outcome")
            or design_map.get("outcome_variable")
            or "outcome"
        ),
    }


def _computed_unresolved_payload(
    *,
    reason: str,
    design: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "resolution_label": "unresolved",
        "status": "unresolved",
        "source": "computed_from_data",
        "design": dict(design),
        "measurement_block": {
            "status": "unsupported",
            "tetrad_test": "single_signal_tetrad_unresolved",
            "invariance_test": "measurement_invariance_unresolved",
            "reason": reason,
        },
        "proxy_block": {
            "status": "unsupported",
            "bridge_test": "proximal_bridge_unresolved",
            "bridge_stability": "cross_environment_unresolved",
            "reason": reason,
        },
        "environment_block": {
            "status": "unsupported",
            "residual_invariance": "post_calibration_residual_invariance_unresolved",
            "post_calibration_shift": "unresolved",
            "reason": reason,
        },
        "separated_pairs": [],
        "support_scope": [],
    }


def _compute_measurement_block(
    columns: Mapping[str, np.ndarray],
    repeated_blocks: list[tuple[str, tuple[str, ...]]],
    *,
    env: np.ndarray | None,
    rank_tol: float,
    invariance_tol: float,
) -> tuple[dict[str, Any], np.ndarray | None]:
    block_id, variables, matrix = _first_available_block(columns, repeated_blocks)
    if matrix is None or len(variables) < 2:
        return (
            {
                "status": "unsupported",
                "tetrad_test": "single_signal_tetrad_unresolved",
                "invariance_test": "measurement_invariance_unresolved",
                "reason": "repeated_indicator_block_missing",
            },
            None,
        )

    standardized = _standardize_matrix(matrix)
    latent_score = _first_component_score(standardized)
    rank_ratio = _rank_residual_ratio(standardized)
    tetrad_value = _max_tetrad_residual(standardized) if standardized.shape[1] >= 4 else None
    structure_passed = (
        tetrad_value <= rank_tol
        if tetrad_value is not None
        else rank_ratio <= rank_tol
    )
    invariance_status, invariance_drift = _measurement_invariance_status(
        standardized,
        latent_score,
        env=env,
        tol=invariance_tol,
    )
    invariance_passed = invariance_status == "measurement_invariance_passed"
    status = (
        "passed"
        if structure_passed and invariance_passed
        else "failed"
        if invariance_status != "measurement_invariance_unresolved"
        else "unsupported"
    )
    tetrad_label = (
        "single_signal_tetrad_passed"
        if structure_passed
        else "single_signal_tetrad_failed"
    )
    return (
        {
            "status": status,
            "test": "single_signal_tetrad_or_rank",
            "block_id": block_id,
            "variables": list(variables),
            "tetrad_test": tetrad_label,
            "invariance_test": invariance_status,
            "rank_residual_ratio": float(rank_ratio),
            "max_tetrad_residual": None if tetrad_value is None else float(tetrad_value),
            "max_loading_drift": None if invariance_drift is None else float(invariance_drift),
        },
        latent_score,
    )


def _compute_proxy_block(
    columns: Mapping[str, np.ndarray],
    proxy_blocks: list[tuple[str, tuple[str, ...]]],
    *,
    env: np.ndarray | None,
    latent_score: np.ndarray | None,
    design: Mapping[str, Any],
    bridge_seed: int,
) -> dict[str, Any]:
    if len(proxy_blocks) < 2:
        return {
            "status": "unsupported",
            "bridge_test": "proximal_bridge_unresolved",
            "bridge_stability": "cross_environment_unresolved",
            "reason": "two_disjoint_proxy_blocks_required",
        }
    treatment = _column_for_name(columns, str(design.get("treatment") or "treatment"))
    outcome = _column_for_name(columns, str(design.get("outcome") or "outcome"))
    first_proxy = _first_column_from_block(columns, proxy_blocks[0][1])
    second_proxy = _first_column_from_block(columns, proxy_blocks[1][1])
    if treatment is None or outcome is None or first_proxy is None or second_proxy is None:
        return {
            "status": "unsupported",
            "bridge_test": "proximal_bridge_unresolved",
            "bridge_stability": "cross_environment_unresolved",
            "reason": "outcome_treatment_or_proxy_columns_missing",
        }
    covariates = _covariate_matrix(columns, design, latent_score=latent_score)
    if covariates is None:
        return {
            "status": "unsupported",
            "bridge_test": "proximal_bridge_unresolved",
            "bridge_stability": "cross_environment_unresolved",
            "reason": "covariates_or_latent_score_missing",
        }

    bridge_test, bridge_metadata = _proximal_bridge_status(
        outcome=outcome,
        treatment=treatment,
        covariates=covariates,
        treatment_proxy=first_proxy,
        outcome_proxy=second_proxy,
        bridge_seed=bridge_seed,
    )
    stability, drift = _proxy_stability_status(first_proxy, second_proxy, env=env)
    status = (
        "passed"
        if bridge_test == "proximal_bridge_solved" and stability == "cross_environment_stable"
        else "failed"
    )
    return {
        "status": status,
        "bridge_test": bridge_test,
        "bridge_stability": stability,
        "proxy_blocks": [proxy_blocks[0][0], proxy_blocks[1][0]],
        "proxy_variables": [str(proxy_blocks[0][1][0]), str(proxy_blocks[1][1][0])],
        "cross_environment_proxy_corr_drift": drift,
        **bridge_metadata,
    }


def _compute_environment_block(
    columns: Mapping[str, np.ndarray],
    repeated_blocks: list[tuple[str, tuple[str, ...]]],
    *,
    env: np.ndarray | None,
    latent_score: np.ndarray | None,
    design: Mapping[str, Any],
    residual_tol: float,
) -> dict[str, Any]:
    if env is None or len(set(env.tolist())) < 2:
        return {
            "status": "unsupported",
            "residual_invariance": "post_calibration_residual_invariance_unresolved",
            "post_calibration_shift": "unresolved",
            "reason": "at_least_two_environments_required",
        }
    treatment = _column_for_name(columns, str(design.get("treatment") or "treatment"))
    outcome = _column_for_name(columns, str(design.get("outcome") or "outcome"))
    if treatment is None or outcome is None:
        return {
            "status": "unsupported",
            "residual_invariance": "post_calibration_residual_invariance_unresolved",
            "post_calibration_shift": "unresolved",
            "reason": "outcome_or_treatment_missing",
        }
    if latent_score is None:
        _, _, matrix = _first_available_block(columns, repeated_blocks)
        latent_score = _first_component_score(_standardize_matrix(matrix)) if matrix is not None else None
    if latent_score is None:
        return {
            "status": "unsupported",
            "residual_invariance": "post_calibration_residual_invariance_unresolved",
            "post_calibration_shift": "unresolved",
            "reason": "calibration_score_missing",
        }
    covariates = _covariate_matrix(columns, design, latent_score=None)
    residual_design = [np.ones(outcome.shape[0]), treatment, latent_score]
    if covariates is not None and covariates.size:
        residual_design.extend(covariates[:, index] for index in range(covariates.shape[1]))
    design_matrix = np.column_stack(residual_design)
    coef, *_ = np.linalg.lstsq(design_matrix, outcome, rcond=None)
    residual = outcome - design_matrix @ coef
    residual_std = float(np.std(residual))
    if residual_std <= 1.0e-12:
        residual_std = 1.0
    means = [float(np.mean(residual[env == value])) for value in sorted(set(env.tolist()))]
    drift = (max(means) - min(means)) / residual_std if means else float("inf")
    restored = bool(np.isfinite(drift) and drift <= residual_tol)
    return {
        "status": "passed",
        "residual_invariance": (
            "post_calibration_residual_invariance_restored"
            if restored
            else "post_calibration_residual_invariance_failed"
        ),
        "post_calibration_shift": "absorbed" if restored else "not_restored",
        "standardized_environment_residual_drift": float(drift),
        "environment_residual_means": means,
    }


def _computed_resolution(
    measurement_block: Mapping[str, Any],
    proxy_block: Mapping[str, Any],
    environment_block: Mapping[str, Any],
) -> tuple[str, list[str], list[str]]:
    measurement_passed = _measurement_block_supported(measurement_block)
    measurement_failed = _matches_any(measurement_block, _MISMATCH_FRAGMENTS + _NEGATIVE_FRAGMENTS)
    bridge_supported = _bridge_supported(proxy_block)
    bridge_failed = _bridge_not_supported(proxy_block) or _matches_any(proxy_block, _MISMATCH_FRAGMENTS)
    environment_restored = _environment_restored(environment_block)
    environment_not_restored = _environment_not_restored(environment_block)

    if measurement_failed and (bridge_supported or environment_restored):
        return (
            "mixed",
            ["measurement_vs_proxy"],
            ["latent_separation:measurement_conflicts_with_proxy_or_environment"],
        )
    if measurement_failed:
        return "proxy_mismatch", ["measurement_vs_proxy"], []
    if measurement_passed and bridge_failed and environment_restored:
        return "measurement_error", ["measurement_vs_confounding"], []
    if measurement_passed and bridge_failed:
        return "proxy_mismatch", ["proxy_vs_confounding"], []
    if measurement_passed and bridge_supported and environment_not_restored:
        return "latent_confounding", ["measurement_vs_confounding"], []
    if measurement_passed and not bridge_supported and environment_restored:
        return "measurement_error", ["measurement_vs_confounding"], []
    if any(
        _normalize_token(block.get("status")) == "unsupported"
        for block in (measurement_block, proxy_block, environment_block)
    ):
        return "unresolved", [], []
    return "mixed", [], ["latent_separation:conflicting_or_indeterminate_signals"]


def _computed_support_scope(design: Mapping[str, Any]) -> list[str]:
    scope: list[str] = []
    if _environment_count(design) >= 2:
        scope.append("multi-environment")
    if _proxy_block_count(design) >= 2:
        scope.append("proximal-proxy-blocks")
    if _repeated_indicator_block_count(design) >= 1:
        scope.append("repeated-indicators")
    return scope


def _proximal_bridge_status(
    *,
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray,
    treatment_proxy: np.ndarray,
    outcome_proxy: np.ndarray,
    bridge_seed: int,
) -> tuple[str, dict[str, Any]]:
    try:
        from polisyos.foundry.methods.catalog.causal.frontier import (
            ProximalBridgeEstimator,
        )
    except ImportError as exc:
        return (
            "proximal_bridge_failed",
            {
                "bridge_r_squared": None,
                "proxy_strength": None,
                "bridge_plausibility_severity": "unavailable",
                "bridge_fallback_disposition": "import_failed",
                "bridge_import_error": str(exc),
            },
        )

    result = ProximalBridgeEstimator.pure_step(
        {
            "outcome": outcome,
            "treatment": treatment,
            "covariates": covariates,
            "treatment_proxy": treatment_proxy,
            "outcome_proxy": outcome_proxy,
        },
        {"n_bootstrap": 50, "__seed__": bridge_seed},
    )
    report = result.get("report")
    metadata = dict(getattr(report, "metadata", {}) or {})
    proximal_result = result.get("proximal_result")
    if isinstance(proximal_result, Mapping):
        metadata.setdefault("bridge_r_squared", proximal_result.get("bridge_r_squared"))
        metadata.setdefault("proxy_strength", proximal_result.get("proxy_strength"))
        metadata.setdefault(
            "bridge_plausibility_severity",
            proximal_result.get("bridge_plausibility_severity"),
        )
        metadata.setdefault(
            "bridge_fallback_disposition",
            proximal_result.get("bridge_fallback_disposition"),
        )
    status = _normalize_token(getattr(getattr(report, "status", ""), "value", getattr(report, "status", "")))
    fallback = _normalize_token(metadata.get("bridge_fallback_disposition"))
    severity = _normalize_token(metadata.get("bridge_plausibility_severity"))
    solved = (
        status == "success"
        and fallback not in {"block_point_estimate", "require_bounds"}
        and severity not in {"red", "critical"}
    )
    return (
        "proximal_bridge_solved" if solved else "proximal_bridge_failed",
        {
            "bridge_r_squared": metadata.get("bridge_r_squared"),
            "proxy_strength": metadata.get("proxy_strength"),
            "bridge_plausibility_severity": metadata.get("bridge_plausibility_severity"),
            "bridge_fallback_disposition": metadata.get("bridge_fallback_disposition"),
        },
    )


def _proxy_stability_status(
    left: np.ndarray,
    right: np.ndarray,
    *,
    env: np.ndarray | None,
) -> tuple[str, float | None]:
    if env is None or len(set(env.tolist())) < 2:
        return "cross_environment_unresolved", None
    corrs: list[float] = []
    for value in sorted(set(env.tolist())):
        mask = env == value
        if int(np.sum(mask)) < 3:
            continue
        corr = _safe_corr(left[mask], right[mask])
        if corr is not None:
            corrs.append(corr)
    if len(corrs) < 2:
        return "cross_environment_unresolved", None
    drift = float(max(corrs) - min(corrs))
    signs = {corr >= 0.0 for corr in corrs if abs(corr) > 1.0e-6}
    stable = drift <= 0.35 and len(signs) <= 1
    return ("cross_environment_stable" if stable else "cross_environment_unstable", drift)


def _measurement_invariance_status(
    matrix: np.ndarray,
    latent_score: np.ndarray,
    *,
    env: np.ndarray | None,
    tol: float,
) -> tuple[str, float | None]:
    if env is None or len(set(env.tolist())) < 2:
        return "measurement_invariance_unresolved", None
    global_loadings = _indicator_loadings(matrix, latent_score)
    drifts: list[float] = []
    for value in sorted(set(env.tolist())):
        mask = env == value
        if int(np.sum(mask)) < matrix.shape[1] + 2:
            continue
        score = _first_component_score(matrix[mask])
        loadings = _indicator_loadings(matrix[mask], score)
        drifts.append(float(np.max(np.abs(loadings - global_loadings))))
    if not drifts:
        return "measurement_invariance_unresolved", None
    drift = max(drifts)
    return (
        "measurement_invariance_passed" if drift <= tol else "measurement_invariance_failed",
        float(drift),
    )


def _column_arrays(data: Mapping[str, Any]) -> dict[str, np.ndarray]:
    columns: dict[str, np.ndarray] = {}
    for payload in (data.get("columns"), data.get("variables")):
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                array = _numeric_vector(value)
                if array is not None:
                    columns[str(key)] = array
    for key, value in data.items():
        if key in {"columns", "variables", "data", "design"}:
            continue
        array = _numeric_vector(value)
        if array is not None:
            columns[str(key)] = array
    return columns


def _environment_labels(
    data: Mapping[str, Any],
    design: Mapping[str, Any] | None,
    *,
    n_obs: int,
) -> np.ndarray | None:
    for payload in (
        data.get("environment"),
        data.get("environments"),
        data.get("env"),
        data.get("domain"),
        data.get("site"),
        (design or {}).get("environment") if isinstance(design, Mapping) else None,
    ):
        if payload is None:
            continue
        array = np.asarray(payload)
        if array.ndim == 1 and array.shape[0] == n_obs:
            return array.astype(str)
    return None


def _variable_blocks(
    value: Any,
    *,
    strings_as_single_block: bool,
) -> list[tuple[str, tuple[str, ...]]]:
    blocks: list[tuple[str, tuple[str, ...]]] = []
    if isinstance(value, Mapping):
        for key, payload in value.items():
            variables = _variables_from_block_payload(payload)
            if variables:
                blocks.append((str(key), variables))
        return blocks
    if isinstance(value, str):
        return [(value, (value,))]
    if not isinstance(value, (list, tuple, set)):
        return []
    items = list(value)
    if items and all(isinstance(item, str) for item in items):
        if strings_as_single_block:
            return [("block_0", tuple(str(item) for item in items))]
        return [(str(item), (str(item),)) for item in items]
    for index, item in enumerate(items):
        if isinstance(item, Mapping):
            block_id = str(item.get("block_id") or item.get("name") or f"block_{index}")
            variables = _variables_from_block_payload(item)
        else:
            block_id = f"block_{index}"
            variables = _variables_from_block_payload(item)
        if variables:
            blocks.append((block_id, variables))
    return blocks


def _variables_from_block_payload(payload: Any) -> tuple[str, ...]:
    if isinstance(payload, Mapping):
        payload = payload.get("variables") or payload.get("columns") or payload.get("items")
    if isinstance(payload, str):
        return (payload,)
    if isinstance(payload, (list, tuple, set)):
        return tuple(str(item) for item in payload if str(item).strip())
    return ()


def _first_available_block(
    columns: Mapping[str, np.ndarray],
    blocks: list[tuple[str, tuple[str, ...]]],
) -> tuple[str, tuple[str, ...], np.ndarray | None]:
    for block_id, variables in blocks:
        arrays = [_column_for_name(columns, variable) for variable in variables]
        if all(array is not None for array in arrays):
            return block_id, variables, np.column_stack(arrays)
    return "", (), None


def _first_column_from_block(
    columns: Mapping[str, np.ndarray],
    variables: tuple[str, ...],
) -> np.ndarray | None:
    for variable in variables:
        column = _column_for_name(columns, variable)
        if column is not None:
            return column
    return None


def _column_for_name(columns: Mapping[str, np.ndarray], name: str) -> np.ndarray | None:
    return columns.get(name)


def _covariate_matrix(
    columns: Mapping[str, np.ndarray],
    design: Mapping[str, Any],
    *,
    latent_score: np.ndarray | None,
) -> np.ndarray | None:
    covariates = design.get("covariates")
    if isinstance(covariates, str):
        covariates = [covariates]
    arrays: list[np.ndarray] = []
    if isinstance(covariates, (list, tuple, set)):
        for variable in covariates:
            column = _column_for_name(columns, str(variable))
            if column is not None:
                arrays.append(column)
    if latent_score is not None:
        arrays.append(latent_score)
    if not arrays:
        return None
    return np.column_stack(arrays)


def _common_length(values: Iterable[np.ndarray]) -> int | None:
    lengths = {int(value.shape[0]) for value in values if value.ndim == 1}
    if len(lengths) == 1:
        return next(iter(lengths))
    return None


def _numeric_vector(value: Any) -> np.ndarray | None:
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        return None
    return array


def _standardize_matrix(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    centered = arr - np.mean(arr, axis=0, keepdims=True)
    scale = np.std(centered, axis=0, keepdims=True)
    scale[scale <= 1.0e-12] = 1.0
    return centered / scale


def _first_component_score(matrix: np.ndarray) -> np.ndarray:
    _, _, vt = np.linalg.svd(matrix, full_matrices=False)
    score = matrix @ vt[0, :]
    return -score if float(np.sum(vt[0, :])) < 0.0 else score


def _rank_residual_ratio(matrix: np.ndarray) -> float:
    singular_values = np.linalg.svd(matrix, full_matrices=False, compute_uv=False)
    denom = float(np.sum(singular_values ** 2))
    if denom <= 1.0e-12:
        return 1.0
    return float(np.sum(singular_values[1:] ** 2) / denom)


def _max_tetrad_residual(matrix: np.ndarray) -> float:
    cov = np.cov(matrix, rowvar=False)
    scale = max(float(np.max(np.abs(cov))) ** 2, 1.0e-12)
    residuals: list[float] = []
    for i in range(cov.shape[0]):
        for j in range(i + 1, cov.shape[0]):
            for k in range(cov.shape[0]):
                for ell in range(k + 1, cov.shape[0]):
                    if len({i, j, k, ell}) != 4:
                        continue
                    residuals.append(abs(float(cov[i, j] * cov[k, ell] - cov[i, k] * cov[j, ell])) / scale)
    return max(residuals) if residuals else 0.0


def _indicator_loadings(matrix: np.ndarray, score: np.ndarray) -> np.ndarray:
    values = [_safe_corr(matrix[:, index], score) or 0.0 for index in range(matrix.shape[1])]
    return np.asarray(values, dtype=float)


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.shape[0] != right.shape[0] or left.shape[0] < 2:
        return None
    if float(np.std(left)) <= 1.0e-12 or float(np.std(right)) <= 1.0e-12:
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    return value if np.isfinite(value) else None


__all__ = [
    "SEPARATION_DIAGNOSTICS_KEY",
    "SEPARATION_DIAGNOSTIC_INPUTS_KEY",
    "compute_latent_separation_diagnostics",
    "compute_latent_separation_diagnostics_from_inputs",
    "certified_latent_separation_pairs",
    "certify_latent_separation_trust",
    "LatentSeparationDiagnosticInputs",
    "LatentSeparationEnvironmentInput",
    "LatentSeparationMeasurementInput",
    "LatentSeparationProxyInput",
    "latent_separation_assumption_surfaces",
    "latent_separation_falsification_surfaces",
    "metadata_with_computed_latent_separation",
    "merge_latent_separation_diagnostics_payloads",
    "separation_diagnostics_payload",
]
