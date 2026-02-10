from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.contracts.backtest import BacktestReportRef as CoreBacktestReportRef
from polisyos.core.contracts.causal import CausalEffectReportRef as CoreCausalEffectReportRef
from polisyos.core.contracts.distributional import (
    DistributionalReportRef as CoreDistributionalReportRef,
)
from polisyos.core.contracts.hte import (
    HTEResultRef as CoreHTEResultRef,
    PolicyRecommendationRef as CorePolicyRecommendationRef,
)
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef as CoreUncertaintyEnvelopeRef
from polisyos.ir.refs import (
    BacktestReportRef as IrBacktestReportRef,
    CausalEffectReportRef as IrCausalEffectReportRef,
    DistributionalReportRef as IrDistributionalReportRef,
    HTEResultRef as IrHTEResultRef,
    PolicyRecommendationRef as IrPolicyRecommendationRef,
    UncertaintyEnvelopeRef as IrUncertaintyEnvelopeRef,
)

_ID = "sha256:" + "a" * 64


def test_core_contract_facades_reexport_ir_ref_types() -> None:
    assert CoreBacktestReportRef is IrBacktestReportRef
    assert CoreCausalEffectReportRef is IrCausalEffectReportRef
    assert CoreDistributionalReportRef is IrDistributionalReportRef
    assert CoreHTEResultRef is IrHTEResultRef
    assert CorePolicyRecommendationRef is IrPolicyRecommendationRef
    assert CoreUncertaintyEnvelopeRef is IrUncertaintyEnvelopeRef


def test_core_contract_facades_accept_core_artifact_id_values() -> None:
    core_id = CoreArtifactID.model_validate(_ID)

    refs = [
        CoreBacktestReportRef(artifact_id=core_id),
        CoreCausalEffectReportRef(artifact_id=core_id),
        CoreDistributionalReportRef(artifact_id=core_id),
        CoreHTEResultRef(artifact_id=core_id),
        CorePolicyRecommendationRef(artifact_id=core_id),
        CoreUncertaintyEnvelopeRef(artifact_id=core_id),
    ]

    for ref in refs:
        assert str(ref.artifact_id) == _ID
        assert ref.artifact_id.hex == "a" * 64
