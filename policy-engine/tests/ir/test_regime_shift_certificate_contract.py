from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.invariance import (
    RegimeShiftDataSignature,
    RegimeShiftEnvironmentRecord,
    RegimeShiftIdentificationCertificate,
    RegimeShiftMECContraction,
    RegimeShiftMECContractionEdgeUpdates,
    RegimeShiftMECContractionSummary,
    RegimeShiftSetTestResult,
    RegimeShiftTargetResult,
    load_regime_shift_identification_certificate,
    persist_regime_shift_identification_certificate,
)
from polisyos.ir.refs import RegimeShiftIdentificationCertificateRef


def _certificate() -> RegimeShiftIdentificationCertificate:
    return RegimeShiftIdentificationCertificate(
        data_signature=RegimeShiftDataSignature(
            dataset_ref="dataset:employment_regimes",
            variables=("training_subsidy", "employment_rate"),
            sample_sizes_by_env={"pre": 120, "post": 140},
        ),
        environments=(
            RegimeShiftEnvironmentRecord(env_id="pre", regime_id="baseline"),
            RegimeShiftEnvironmentRecord(env_id="post", regime_id="subsidy"),
        ),
        targets=(
            RegimeShiftTargetResult(
                target="employment_rate",
                envs_used=("pre", "post"),
                accepted_sets=(
                    RegimeShiftSetTestResult(S=("training_subsidy",), p_value=0.43),
                ),
                rejected_sets=(RegimeShiftSetTestResult(S=(), p_value=0.001),),
                estimated_parents=("training_subsidy",),
            ),
        ),
        mec_contraction=RegimeShiftMECContraction(
            edge_updates=RegimeShiftMECContractionEdgeUpdates(
                forced_orientations=(("training_subsidy", "employment_rate"),),
                forbidden_orientations=(("employment_rate", "training_subsidy"),),
            ),
            summary=RegimeShiftMECContractionSummary(edges_oriented_total=1),
        ),
    )


def test_regime_shift_certificate_roundtrips_through_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    certificate = _certificate()

    ref = persist_regime_shift_identification_certificate(store, certificate)
    loaded = load_regime_shift_identification_certificate(store, ref)

    assert isinstance(ref, RegimeShiftIdentificationCertificateRef)
    assert ref.kind == "ir.regime_shift_identification_certificate"
    assert loaded == certificate


def test_regime_shift_certificate_rejects_unknown_target_env() -> None:
    certificate = _certificate()

    with pytest.raises(ValueError, match="unknown envs"):
        RegimeShiftIdentificationCertificate.model_validate(
            certificate.model_dump(mode="json")
            | {
                "targets": [
                    certificate.targets[0]
                    .model_copy(update={"envs_used": ("missing",)})
                    .model_dump(mode="json")
                ]
            }
        )
