from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.contracts.backtest import BacktestReportRef as CoreBacktestReportRef
from polisyos.core.contracts.causal import (
    CausalModelEnsembleRef as CoreCausalModelEnsembleRef,
    CausalDiscoveryReportRef as CoreCausalDiscoveryReportRef,
)
from polisyos.core.contracts.causal import CausalEffectReportRef as CoreCausalEffectReportRef
from polisyos.core.contracts.causal import CausalGraphModelRef as CoreCausalGraphModelRef
from polisyos.core.contracts.causal import CausalQueryResultRef as CoreCausalQueryResultRef
from polisyos.core.contracts.causal import (
    LiteratureCausalPriorRef as CoreLiteratureCausalPriorRef,
)
from polisyos.core.contracts.causal import (
    StructuralCausalModelSpecRef as CoreStructuralCausalModelSpecRef,
)
from polisyos.core.contracts.distributional import (
    DistributionalReportRef as CoreDistributionalReportRef,
)
from polisyos.core.contracts.hte import (
    HTEResultRef as CoreHTEResultRef,
)
from polisyos.core.contracts.hte import (
    PolicyRecommendationRef as CorePolicyRecommendationRef,
)
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef as CoreUncertaintyEnvelopeRef
from polisyos.ir.refs import (
    BacktestReportRef as IrBacktestReportRef,
)
from polisyos.ir.refs import (
    CausalModelEnsembleRef as IrCausalModelEnsembleRef,
)
from polisyos.ir.refs import (
    CausalDiscoveryReportRef as IrCausalDiscoveryReportRef,
)
from polisyos.ir.refs import (
    CausalEffectReportRef as IrCausalEffectReportRef,
)
from polisyos.ir.refs import (
    CausalGraphModelRef as IrCausalGraphModelRef,
)
from polisyos.ir.refs import (
    CausalQueryResultRef as IrCausalQueryResultRef,
)
from polisyos.ir.refs import (
    DistributionalReportRef as IrDistributionalReportRef,
)
from polisyos.ir.refs import (
    HTEResultRef as IrHTEResultRef,
)
from polisyos.ir.refs import (
    LiteratureCausalPriorRef as IrLiteratureCausalPriorRef,
)
from polisyos.ir.refs import (
    PolicyRecommendationRef as IrPolicyRecommendationRef,
)
from polisyos.ir.refs import (
    StructuralCausalModelSpecRef as IrStructuralCausalModelSpecRef,
)
from polisyos.ir.refs import (
    UncertaintyEnvelopeRef as IrUncertaintyEnvelopeRef,
)

_ID = "sha256:" + "a" * 64


def test_core_contract_facades_reexport_ir_ref_types() -> None:
    assert CoreBacktestReportRef is IrBacktestReportRef
    assert CoreCausalModelEnsembleRef is IrCausalModelEnsembleRef
    assert CoreCausalDiscoveryReportRef is IrCausalDiscoveryReportRef
    assert CoreCausalEffectReportRef is IrCausalEffectReportRef
    assert CoreCausalGraphModelRef is IrCausalGraphModelRef
    assert CoreCausalQueryResultRef is IrCausalQueryResultRef
    assert CoreLiteratureCausalPriorRef is IrLiteratureCausalPriorRef
    assert CoreStructuralCausalModelSpecRef is IrStructuralCausalModelSpecRef
    assert CoreDistributionalReportRef is IrDistributionalReportRef
    assert CoreHTEResultRef is IrHTEResultRef
    assert CorePolicyRecommendationRef is IrPolicyRecommendationRef
    assert CoreUncertaintyEnvelopeRef is IrUncertaintyEnvelopeRef


def test_core_contract_facades_accept_core_artifact_id_values() -> None:
    core_id = CoreArtifactID.model_validate(_ID)

    refs = [
        CoreBacktestReportRef(artifact_id=core_id),
        CoreCausalModelEnsembleRef(artifact_id=core_id),
        CoreCausalDiscoveryReportRef(artifact_id=core_id),
        CoreCausalEffectReportRef(artifact_id=core_id),
        CoreCausalGraphModelRef(artifact_id=core_id),
        CoreCausalQueryResultRef(artifact_id=core_id),
        CoreLiteratureCausalPriorRef(artifact_id=core_id),
        CoreStructuralCausalModelSpecRef(artifact_id=core_id),
        CoreDistributionalReportRef(artifact_id=core_id),
        CoreHTEResultRef(artifact_id=core_id),
        CorePolicyRecommendationRef(artifact_id=core_id),
        CoreUncertaintyEnvelopeRef(artifact_id=core_id),
    ]

    for ref in refs:
        assert str(ref.artifact_id) == _ID
        assert ref.artifact_id.hex == "a" * 64
