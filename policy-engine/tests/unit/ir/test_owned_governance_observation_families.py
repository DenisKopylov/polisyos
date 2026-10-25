from __future__ import annotations

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.analytics.dependence_structure import (
    build_dependence_structure,
    persist_dependence_structure,
)
from polisyos.ir.analytics.microsim_calibration import (
    build_microsim_calibration_report,
    persist_microsim_calibration_report,
)
from polisyos.ir.analytics.mobility import (
    MobilityReport,
    load_mobility_report,
    persist_mobility_report,
)
from polisyos.ir.analytics.survey_quality import (
    build_survey_quality_certificate,
    persist_survey_quality_certificate,
)
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.governance.phase1 import (
    build_phase1_gate_summary,
    load_phase1_flagship_dataset_ids,
)
from polisyos.ir.governance.validation import ValidationReport, persist_validation_report
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.observation.causal_execution import (
    CausalExecutionBundle,
    persist_causal_execution_bundle,
)
from polisyos.ir.observation.causal_readiness import (
    CausalReadinessBundle,
    persist_causal_readiness_bundle,
)
from polisyos.ir.registry.refs import MobilityReportRef


class CountingStore:
    def __init__(self, store):
        self.store = store
        self.put_calls = 0

    def __getattr__(self, name):
        return getattr(self.store, name)

    def put_json(self, *args, **kwargs):
        self.put_calls += 1
        return self.store.put_json(*args, **kwargs)


@pytest.mark.parametrize(
    ("writer", "payload"),
    [
        (persist_validation_report, ValidationReport(error_summary="valid", issues=[])),
        (persist_causal_execution_bundle, CausalExecutionBundle()),
        (persist_causal_readiness_bundle, CausalReadinessBundle()),
        (
            persist_dependence_structure,
            build_dependence_structure(
                regime="panel",
                class_label="shared",
                calibrated=True,
                recommended_covariance="driscoll_kraay",
                source_method="tests.owner",
            ),
        ),
        (
            persist_survey_quality_certificate,
            build_survey_quality_certificate(
                target_estimand="E[Y]",
                overall_pass=True,
            ),
        ),
        (
            persist_microsim_calibration_report,
            build_microsim_calibration_report(compatibility_status="compatible"),
        ),
        (
            persist_mobility_report,
            MobilityReport(
                analysis_type="transition_matrix",
                status="ok",
                summary_metrics={"n_obs": 10},
            ),
        ),
    ],
)
def test_unregistered_family_override_refuses_before_cas(writer, payload, tmp_path) -> None:
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")))

    with pytest.raises(CanonViolation):
        writer(store, payload, schema_version="9.9")

    assert store.put_calls == 0


def test_phase1_does_not_admit_a_schema_matching_but_unregistered_certificate(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    store = ensure_ir_artifact_store(cas)
    dataset_id = load_phase1_flagship_dataset_ids()[0]
    certificate = build_survey_quality_certificate(
        target_estimand="E[Y]",
        dataset_id=dataset_id,
        data_origin="government",
        overall_pass=True,
    )
    put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.survey_quality_certificate",
        schema_name="ir.survey_quality_certificate",
        schema_version="9.9",
        canon_spec=CanonSpec(forbid_floats=False),
    )

    summary = build_phase1_gate_summary(store)

    assert dataset_id not in summary.certified_flagship_dataset_ids
    assert summary.flagship_dataset_coverage_ready is False


def test_unproven_legacy_mobility_history_remains_opaque_not_typed(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    payload = {
        "schema_version": "1.0",
        "artifact_name": "mobility_report_v1.json",
        "analysis_type": "transition_matrix",
        "status": "ok",
        "summary_metrics": {"n_obs": 10},
    }
    selected = put_json_artifact(
        store,
        payload,
        kind="ir.mobility_report",
        schema_name="ir.mobility_report",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = MobilityReportRef.model_validate(selected)

    assert get_json_artifact(store, ref) == payload
    with pytest.raises(CanonViolation):
        load_mobility_report(store, ref)


@pytest.mark.parametrize(
    ("writer", "payload"),
    [
        (persist_validation_report, ValidationReport(error_summary="valid", issues=[])),
        (persist_causal_execution_bundle, CausalExecutionBundle()),
        (persist_causal_readiness_bundle, CausalReadinessBundle()),
        (
            persist_dependence_structure,
            build_dependence_structure(
                regime="panel",
                class_label="shared",
                calibrated=True,
                recommended_covariance="driscoll_kraay",
                source_method="tests.owner",
            ),
        ),
        (
            persist_survey_quality_certificate,
            build_survey_quality_certificate(
                target_estimand="E[Y]",
                overall_pass=True,
            ),
        ),
        (
            persist_microsim_calibration_report,
            build_microsim_calibration_report(compatibility_status="compatible"),
        ),
        (
            persist_mobility_report,
            MobilityReport(
                schema_version="2.0",
                analysis_type="transition_matrix",
                status="ok",
                summary_metrics={"n_obs": 10},
            ),
        ),
    ],
)
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_name", False),
        ("schema_name", 0),
        ("schema_name", ""),
        ("schema_name", None),
        ("schema_version", False),
        ("schema_version", 0),
        ("schema_version", ""),
    ],
)
def test_present_malformed_family_overrides_refuse_before_cas(
    writer, payload, field, value, tmp_path
) -> None:
    store = CountingStore(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas")))

    with pytest.raises(CanonViolation):
        writer(store, payload, **{field: value})

    assert store.put_calls == 0


@pytest.mark.parametrize("schema_version", [None, False, 0, ""])
def test_mobility_report_treats_present_invalid_version_as_invalid(schema_version) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MobilityReport.model_validate(
            {
                "schema_version": schema_version,
                "analysis_type": "transition_matrix",
                "status": "ok",
            }
        )


def test_mobility_report_only_infers_version_when_discriminator_is_absent() -> None:
    report = MobilityReport.model_validate({"analysis_type": "transition_matrix", "status": "ok"})

    assert report.schema_version == "1.0"


def test_mobility_writer_keeps_documented_none_as_omitted_version(tmp_path) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    report = MobilityReport.model_validate(
        {
            "schema_version": "2.0",
            "analysis_type": "transition_matrix",
            "status": "ok",
            "population": {},
        }
    )

    ref = persist_mobility_report(store, report, schema_version=None)

    loaded = load_mobility_report(store, ref)
    assert loaded.schema_version == "2.0"


def test_existing_academic_corpus_discovers_and_executes_two_unseen_resources(tmp_path) -> None:
    from polisyos.data_forge.domains.academic.knowledge.search import ScholarKnowledgeGraph
    from polisyos.data_forge.domains.academic.knowledge.types import EstimateCandidate, WorkRecord
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    db_path = tmp_path / "unseen-resource-corpus.duckdb"
    estimates = [
        EstimateCandidate(value=2.0, variable_hint="macro.g528_unseen_resource"),
        EstimateCandidate(value=4.0, variable_hint="macro.g528_unseen_resource"),
    ]
    records = (
        WorkRecord(
            id="g528-unseen-resource-alpha",
            title="G528 unseen resource alpha",
            abstract="g528 unseen resource discovery fixture",
            estimates=[estimates[0]],
            trust_score=0.8,
            study_design="synthetic_fixture",
            metadata={"synthetic": True, "fixture_scope": "g528_resource_extension"},
        ),
        WorkRecord(
            id="g528-unseen-resource-beta",
            title="G528 unseen resource beta",
            abstract="g528 unseen resource discovery fixture",
            estimates=[estimates[1]],
            trust_score=0.8,
            study_design="synthetic_fixture",
            metadata={"synthetic": True, "fixture_scope": "g528_resource_extension"},
        ),
    )
    stats = build_synthetic_academic_skg_source(records=records, db_path=db_path)
    assert stats.works == 2
    assert stats.estimates == 2

    graph = ScholarKnowledgeGraph(db_path, tmp_path / "unseen-resource-index")
    try:
        discovered = graph.find_relevant_works("g528 unseen resource discovery", top_k=10)
        assert {record.id for record in discovered} == {
            "g528-unseen-resource-alpha",
            "g528-unseen-resource-beta",
        }

        prior = graph.get_parameter_prior(
            "macro.g528_unseen_resource",
            prefer_simulation_ready=False,
        )
        assert prior is not None
        assert prior.n_studies == 2
        assert prior.prior_mean == 3.0
    finally:
        graph.close()
