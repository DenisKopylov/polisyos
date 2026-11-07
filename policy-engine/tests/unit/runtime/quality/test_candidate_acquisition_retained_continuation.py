"""Owner-boundary checks for retained candidate continuation replay."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from polisyos.runtime.quality.acquisition_evaluation import CandidateAcquisitionEvaluationDecision
from polisyos.runtime.quality.acquisition_retained_continuation import (
    read_candidate_acquisition_retained_continuation,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentTerminalReceipt,
    VerifiedAcquisitionRouteClosure,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


def test_retained_reader_requires_one_typed_prior_source_owner() -> None:
    """A retained read cannot infer or cast its source from a candidate record."""
    decision = CandidateAcquisitionEvaluationDecision.model_construct()
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_construct()

    def read(*, closure: object | None = None, origin: object | None = None) -> None:
        read_candidate_acquisition_retained_continuation(
            store=cast("CoreJSONArtifactStore", None),
            event_log=cast("RuntimeDiagnosticEventLog", None),
            control_store=cast("ControlPlaneStore", None),
            ref=cast("ArtifactRef", None),
            decision=decision,
            terminal=terminal,
            prior_closure=cast("VerifiedAcquisitionRouteClosure | None", closure),
            prior_experiment_origin=cast("VerifiedCandidateExperimentOrigin | None", origin),
        )

    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read()
    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read(closure=object(), origin=object())
    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read(closure=object())
    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read(origin=object())


def test_costed_owner_cannot_be_paired_with_experiment_terminal() -> None:
    """A costed closure never stands in for the separate experiment owner."""
    decision = CandidateAcquisitionEvaluationDecision.model_construct(
        comparison_result="equivalent",
        predicate_provenance="recomputed",
    )
    closure = VerifiedAcquisitionRouteClosure.model_construct()
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_construct(
        terminal_outcome="candidate_evaluation_retained",
        current_continuation_ref=None,
    )

    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read_candidate_acquisition_retained_continuation(
            store=cast("CoreJSONArtifactStore", None),
            event_log=cast("RuntimeDiagnosticEventLog", None),
            control_store=cast("ControlPlaneStore", None),
            ref=cast("ArtifactRef", None),
            decision=decision,
            terminal=terminal,
            prior_closure=closure,
        )
