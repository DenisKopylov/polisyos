"""Admit retained reference-sampler corpora from a configured method CAS pair.

This bridge preserves a supplied finite corpus. It establishes neither posterior
mixing nor fit/noise/source-law authority, and does not create a CalibrationReport.
"""

from __future__ import annotations

import base64
import binascii
import math
import numbers
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from polisyos.core import artifacts, canon
from polisyos.ir.analytics import (
    PosteriorParameterBinding,
    PosteriorSummaryContext,
    UncertaintyEnvelope,
    admit_posterior_summary_profiles,
    validate_raw_posterior_summary_envelope,
)

from .uncertainty_adapter import summarize_bayesian_calibration_posterior

ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
ArtifactManifest = artifacts.ArtifactManifest
PutOptions = artifacts.PutOptions
SchemaInfo = artifacts.SchemaInfo

_LAYOUT = {
    "axis_order": ["chain", "draw", "parameter"],
    "array_order": "C",
    "dtype": "<f8",
    "canonicalization_version": "foundry.bayesian.draws.v1",
}
_METHODS = {
    "bayesian.sampling.hmc@1.0.0": ("bayesian_hmc_regression", "hmc"),
    "bayesian.sampling.nuts@1.0.0": ("bayesian_nuts_regression", "nuts"),
}
_RECORDED_PARAMETERS = {
    "num_warmup",
    "num_samples",
    "num_chains",
    "credible_mass",
    "step_size",
    "n_leapfrog",
    "max_depth",
    "max_tree_depth",
}


class BayesianFitBinding(BaseModel):
    """Expected recorded fit identity; parameter units are optional declarations.

    ``effective_parameters`` compares only diagnostics retained by this producer.
    It is not a claim that the complete requested hyperparameters were persisted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    method_fqn: Literal["bayesian.sampling.hmc@1.0.0", "bayesian.sampling.nuts@1.0.0"]
    source_refs: dict[str, ArtifactRef]
    seed: StrictInt
    effective_parameters: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, PosteriorParameterBinding] = Field(default_factory=dict)

    @field_validator("source_refs")
    @classmethod
    def _admit_sources(cls, refs: dict[str, ArtifactRef]) -> dict[str, ArtifactRef]:
        if set(refs) != {"features", "target"}:
            raise ValueError("Bayesian fit requires exact configured features and target refs")
        # MethodBackend's current result edges retain content IDs, not selected
        # manifest profiles. A selected source view cannot be claimed here.
        if any(ref.manifest_profile_sha256 is not None for ref in refs.values()):
            raise ValueError("selected source manifest profile is not retained by MethodBackend")
        return refs

    @field_validator("effective_parameters")
    @classmethod
    def _admit_effective_parameters(cls, params: dict[str, Any]) -> dict[str, Any]:
        if set(params) - _RECORDED_PARAMETERS:
            raise ValueError("requested hyperparameter identity is not retained by this producer")
        if any(
            isinstance(value, bool)
            or not isinstance(value, numbers.Real)
            or not math.isfinite(float(value))
            for value in params.values()
        ):
            raise ValueError("effective parameters require finite real non-bool values")
        return params


@dataclass(frozen=True)
class PersistedBayesianFit:
    """Freshly read finite-law envelopes and their exact configured CAS references."""

    envelope_refs: dict[str, ArtifactRef]
    envelopes: dict[str, UncertaintyEnvelope]
    corpus_hash: str


def _read_json(
    store: ArtifactStore, ref: ArtifactRef, *, kind: str, schema_name: str
) -> tuple[dict[str, Any], ArtifactManifest]:
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    data = store.get_bytes(ref)
    if (
        ref.kind != kind
        or ref.media_type != "application/json"
        or manifest.kind != kind
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != schema_name
        or schema.version != ("1.1" if kind == "ir.uncertainty_envelope" else "0.1.0")
        or canon.content_hash(data, prefix=True) != str(ref.artifact_id)
        or not store.verify(ref).ok
    ):
        raise ValueError("Bayesian fit CAS kind/schema/content is invalid")
    raw = canon.from_canonical_bytes(data)
    if not isinstance(raw, dict):
        raise ValueError("Bayesian fit CAS payload must be an object")
    return raw, manifest


def _admit_corpus(
    result: dict[str, Any], evidence: dict[str, Any], binding: BayesianFitBinding
) -> tuple[dict[str, np.ndarray], list[str], str, float]:
    posterior = result.get("result")
    artifacts = evidence.get("artifacts")
    if not isinstance(posterior, dict) or not isinstance(artifacts, dict):
        raise ValueError("Bayesian fit has no retained reference-sampler corpus")
    corpus = artifacts.get("posterior_draws")
    if not isinstance(corpus, dict) or not isinstance(corpus.get("payload"), dict):
        raise ValueError("Bayesian fit has no retained reference-sampler corpus")
    payload = corpus["payload"]
    method_name, kernel = _METHODS[binding.method_fqn]
    digest = canon.content_hash(
        canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False)), prefix=True
    )
    virtual_ref = f"artifact://foundry/bayesian/posterior/{digest}"
    repro = posterior.get("reproducibility")
    execution_repro = evidence.get("reproducibility")
    if (
        payload.get("schema") != "foundry.bayesian.draws.v1"
        or set(payload)
        != {"schema", "method_name", "sampler_kernel", "stage", "draw_layout", "parameters"}
        or set(corpus) != {"artifact_ref", "artifact_hash", "payload"}
        or payload.get("stage") != "posterior"
        or payload.get("method_name") != method_name
        or payload.get("sampler_kernel") != kernel
        or posterior.get("method_name") != method_name
        or posterior.get("sampler_kernel") != kernel
        or posterior.get("sampler_family") != "mcmc"
        or payload.get("draw_layout") != _LAYOUT
        or posterior.get("draw_layout") != _LAYOUT
        or corpus.get("artifact_hash") != digest
        or corpus.get("artifact_ref") != virtual_ref
        or posterior.get("draws_ref") != virtual_ref
        or not isinstance(repro, dict)
        or repro != artifacts.get("sampler_reproducibility")
        or repro.get("replay_output_hash") != digest
        or repro.get("draw_layout") != _LAYOUT
        or repro.get("effective_runtime_backend") != "numpy"
        or repro.get("requested_runtime_backend") != "numpy"
        or repro.get("effective_determinism_tier") not in {"statistical", "library_deterministic"}
        or not isinstance(repro.get("determinism_envelope"), dict)
        or repro.get("envelope_id")
        != canon.content_hash(
            canon.to_canonical_bytes(
                repro["determinism_envelope"], canon.CanonSpec(forbid_floats=False)
            ),
            prefix=True,
        )
        or repro["determinism_envelope"].get("sampler_kernel") != kernel
        or repro["determinism_envelope"].get("effective_runtime_backend") != "numpy"
        or type(repro.get("root_seed")) is not int
        or repro.get("root_seed") != binding.seed
        or not isinstance(execution_repro, dict)
        or type(execution_repro.get("seed")) is not int
        or execution_repro.get("seed") != binding.seed
        or execution_repro.get("tier") != repro.get("effective_determinism_tier")
    ):
        raise ValueError("Bayesian fit corpus/layout/reproducibility binding is invalid")
    diagnostics = posterior.get("diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("Bayesian fit recorded diagnostics are missing")
    for key, value in binding.effective_parameters.items():
        actual = diagnostics.get(key)
        if isinstance(actual, bool) or not isinstance(actual, numbers.Real) or actual != value:
            raise ValueError("Bayesian fit recorded effective parameters mismatch")
    parameters = payload.get("parameters")
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError("Bayesian fit corpus parameters are missing")
    draws: dict[str, np.ndarray] = {}
    common_shape: tuple[int, int] | None = None
    for name, record in sorted(parameters.items()):
        if not isinstance(name, str) or not name.strip() or not isinstance(record, dict):
            raise ValueError("Bayesian fit parameter record is invalid")
        shape = record.get("shape")
        if (
            not isinstance(shape, list)
            or set(record) != {"shape", "dtype", "data_base64"}
            or len(shape) < 2
            or any(type(dim) is not int or dim <= 0 for dim in shape)
            or record.get("dtype") != "<f8"
            or not isinstance(record.get("data_base64"), str)
        ):
            raise ValueError("Bayesian fit chain-major shape/dtype is invalid")
        pair = (shape[0], shape[1])
        if common_shape is not None and pair != common_shape:
            raise ValueError("Bayesian fit parameters do not share chain/draw rows")
        common_shape = pair
        try:
            data = base64.b64decode(record["data_base64"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Bayesian fit corpus base64 is invalid") from exc
        if len(data) != math.prod(shape) * 8:
            raise ValueError("Bayesian fit corpus byte length disagrees with shape")
        array = np.frombuffer(data, dtype="<f8").reshape(shape)
        if not np.all(np.isfinite(array)):
            raise ValueError("Bayesian fit corpus requires finite float64 values")
        flat = array.reshape(pair[0] * pair[1], -1)
        labels = [name] if flat.shape[1] == 1 else [f"{name}_{i}" for i in range(flat.shape[1])]
        for i, label in enumerate(labels):
            if label in draws:
                raise ValueError("Bayesian fit flattened parameter labels collide")
            draws[label] = flat[:, i]
    if common_shape is None:
        raise ValueError("Bayesian fit corpus is empty")
    chains, count = common_shape
    for key, actual in (("num_chains", chains), ("num_samples", count)):
        recorded = diagnostics.get(key)
        if (
            isinstance(recorded, bool)
            or not isinstance(recorded, numbers.Real)
            or recorded != actual
        ):
            raise ValueError("Bayesian fit corpus work differs from recorded diagnostics")
    mass = diagnostics.get("credible_mass")
    if isinstance(mass, bool) or not isinstance(mass, numbers.Real) or not 0 < float(mass) < 1:
        raise ValueError("Bayesian fit credible mass is invalid")
    if set(posterior.get("posterior_means", {})) != set(draws):
        raise ValueError("Bayesian fit posterior parameter labels disagree with corpus")
    ids = [
        f"{digest}:chain:{chain}:draw:{draw}" for chain in range(chains) for draw in range(count)
    ]
    return draws, ids, digest, float(mass)


def persist_bayesian_fit_envelopes(
    store: ArtifactStore,
    result_ref: ArtifactRef,
    evidence_ref: ArtifactRef,
    binding: BayesianFitBinding,
) -> PersistedBayesianFit:
    """Resolve a real method pair, retain its complete law, persist and reopen it.

    All pair/source/corpus admission precedes envelope publication and any
    downstream evaluator. Lineage is a checked recorded relation; it does not
    establish the producer's statistical model or truth of its observations.
    """
    # Revalidate all supplied records, including model_copy-created values,
    # before the first configured-store callback.
    binding = BayesianFitBinding.model_validate(binding.model_dump(mode="python"))
    result_ref = ArtifactRef.model_validate(result_ref.model_dump(mode="python"))
    evidence_ref = ArtifactRef.model_validate(evidence_ref.model_dump(mode="python"))
    if (
        result_ref.kind != "scientist.method_result.bayesian.sampling"
        or evidence_ref.kind != "scientist.method_evidence"
        or result_ref.media_type != "application/json"
        or evidence_ref.media_type != "application/json"
    ):
        raise ValueError("Bayesian fit selected result/evidence kind is invalid")
    result, result_manifest = _read_json(
        store,
        result_ref,
        kind="scientist.method_result.bayesian.sampling",
        schema_name="polisyos.scientist.MethodResult",
    )
    evidence, evidence_manifest = _read_json(
        store,
        evidence_ref,
        kind="scientist.method_evidence",
        schema_name="polisyos.scientist.MethodExecutionEvidence",
    )
    expected_sources = sorted(
        (f"input:{name}", str(ref.artifact_id), None) for name, ref in binding.source_refs.items()
    )
    actual_sources = sorted(
        (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
        for edge in result_manifest.inputs
    )
    actual_pair = [
        (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
        for edge in evidence_manifest.inputs
    ]
    if (
        actual_sources != expected_sources
        or actual_pair
        != [("method_result", str(result_ref.artifact_id), result_ref.manifest_profile_sha256)]
        or evidence.get("result_ref") != str(result_ref.artifact_id)
        or evidence.get("method_fqn") != binding.method_fqn
        or evidence.get("backend") != "bayesian"
        or evidence.get("execution_backend") != "bayesian"
        or evidence.get("authority_purpose") != "method_execution"
        or evidence.get("authoritative_for") != ["execution_reproducibility"]
        or evidence.get("may_not_use_for") != ["governance_admissibility", "method_validity"]
    ):
        raise ValueError("Bayesian fit result/evidence/source relationship mismatch")
    for ref in binding.source_refs.values():
        manifest = store.get_manifest(ref)
        data = store.get_bytes(ref)
        if (
            manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
            or canon.content_hash(data, prefix=True) != str(ref.artifact_id)
            or not store.verify(ref).ok
        ):
            raise ValueError("Bayesian fit configured source content is invalid")
    draws, ids, digest, mass = _admit_corpus(result, evidence, binding)
    lineage = {"method_result": result_ref, "method_evidence": evidence_ref, **binding.source_refs}
    context = PosteriorSummaryContext.model_validate(
        {
            "parameters": {
                name: value.model_dump(mode="json") for name, value in binding.parameters.items()
            },
            "lineage_refs": {name: ref.model_dump(mode="json") for name, ref in lineage.items()},
            "purpose": "method_execution",
        }
    )
    summary = summarize_bayesian_calibration_posterior(
        draws,
        credible_mass=mass,
        draw_ids=ids,
        sample_axis="chain_draw",
        context=context,
        posterior_diagnostics={
            "corpus_hash": digest,
            "finite_corpus_only": True,
            "requested_hyperparameter_identity": "not_established",
            "source_law_authority": "not_established",
            "mixing_authority": "not_established",
            "recorded_reproducibility": result["result"]["reproducibility"],
        },
    )
    inputs = [
        artifacts.input_ref_from_artifact_ref(ref, role=role) for role, ref in lineage.items()
    ]
    refs = {
        name: store.put_json(
            envelope.model_dump(mode="python", round_trip=True),
            PutOptions(
                kind="ir.uncertainty_envelope",
                media_type="application/json",
                schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
                inputs=inputs,
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        for name, envelope in summary.parameter_envelopes.items()
    }
    reopened: dict[str, UncertaintyEnvelope] = {}
    for name, ref in refs.items():
        raw, _ = _read_json(
            store, ref, kind="ir.uncertainty_envelope", schema_name="ir.uncertainty_envelope"
        )
        validate_raw_posterior_summary_envelope(raw)
        reopened[name] = UncertaintyEnvelope.model_validate(raw)
    admit_posterior_summary_profiles(reopened)
    return PersistedBayesianFit(refs, reopened, digest)


__all__ = ["BayesianFitBinding", "PersistedBayesianFit", "persist_bayesian_fit_envelopes"]
