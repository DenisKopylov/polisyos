"""Reuse a genuine six-fold MethodJob report at installed consumer boundaries.

Scratch-only independent carrier; all native product imports must be installed.
No admitted Runtime Node, identification appointment or study budget is invented.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.foundry.methods.components.value_evidence import MethodValueRefusal, project_method_value_evidence
from polisyos.ir.analytics.causal import (
    CausalEffectReport, EstimationStatus, ProofBundle, load_causal_effect_report,
    load_proof_bundle, persist_causal_effect_report, persist_proof_bundle,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType, persist_causal_graph_model
from polisyos.ir.analytics.uncertainty import UncertaintySource, persist_uncertainty_envelope
from polisyos.ir.artifacts import put_json_artifact
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass


def _fixture():
    path=Path(os.environ['E02_TMLE_FIXTURE_PATH'])
    spec=importlib.util.spec_from_file_location('installed_native_tmle_carrier',path)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context(store,state):
    profile=ValidationProfile.strict()
    profile=replace(profile,thresholds={**profile.thresholds,'uncertainty_min_gate_eligible_ratio':0.0})
    return PassContext(ir=None,state={'_store':store,**state},registry_bundle=None,
        profile=profile,run_id='installed-synthetic-tmle-candidate')


def test_installed_native_tmle_configured_job_and_actual_boundaries(tmp_path,monkeypatch):
    assert sys.flags.isolated==1
    site=Path(sys.prefix)/'lib/python3.14/site-packages'
    assert Path(sys.modules[TMLEEstimator.__module__].__file__).is_relative_to(site)
    fixture=_fixture()
    recorded=[]
    native_dispatch=MethodDispatcher.dispatch

    def observe(self,*args,**kwargs):
        result=native_dispatch(self,*args,**kwargs)
        signature=kwargs.get('signature')
        if signature is not None and signature.fqn==TMLEEstimator.signature.fqn:
            recorded.append(result)
        return result

    with monkeypatch.context() as capture:
        capture.setattr(MethodDispatcher,'dispatch',observe)
        fixture.test_real_configured_method_job_projects_exact_native_eif_and_cas_reader(tmp_path/'native',capture)
    assert len(recorded)==1
    result=recorded[0]
    native=result.slot_outputs['report']
    assert isinstance(native,CausalEffectReport)
    assert native.status is EstimationStatus.SUCCESS
    assert native.confidence_interval is not None
    assert native.method.value=='tmle'
    assert native.to_uncertainty_envelope().gate_eligible is False
    cases=[]
    for basis in ('missing','present_fake','swapped_real_cas'):
        directory=tmp_path/basis
        writer=FileSystemCAS(directory)
        native_ref=persist_causal_effect_report(writer,native)
        graph_ref=persist_causal_graph_model(writer,CausalGraphModel(graph_type=GraphType.DAG,nodes=['A','Y'],edges=[]))
        payload=native.model_dump(mode='json')
        payload['graph_ref']=str(graph_ref.artifact_id)
        metadata={**payload['metadata'],'gate_eligible':True,'causal_identification_verified':True}
        if basis=='present_fake':
            metadata['identification_admission']={
                'proof_status':'identified','predicate_provenance':'recomputed',
                'verifier_role':'system_verifier','proof_ref':'sha256:'+'f'*64,
                'source_report_ref':str(native_ref.artifact_id),'graph_ref':payload['graph_ref']}
        elif basis=='swapped_real_cas':
            other_graph=persist_causal_graph_model(writer,CausalGraphModel(graph_type=GraphType.DAG,nodes=['unrelated','Z'],edges=[]))
            other_query=put_json_artifact(writer,{'estimand':'E[Z|do(unrelated=1)]','target':'other-population'},
                kind='test.causal_query',schema_name='test.causal_query',schema_version='1.0')
            proof=ProofBundle(proof_status='identified',proof_stratum='A0_trusted',
                theorem_family='backdoor',completeness_regime='complete',implementation_coverage='declared',
                graph_ref=str(other_graph.artifact_id),query_ref=str(other_query['artifact_id']),
                metadata={'predicate_provenance':'recomputed','verifier_role':'system_verifier'})
            proof_ref=persist_proof_bundle(writer,proof)
            fresh_proof=load_proof_bundle(FileSystemCAS(directory),proof_ref)
            assert fresh_proof.graph_ref!=payload['graph_ref']
            metadata['identification_admission']={
                'proof_status':'identified','predicate_provenance':'recomputed','verifier_role':'system_verifier',
                'proof_ref':str(proof_ref.artifact_id),'source_report_ref':str(native_ref.artifact_id),
                'graph_ref':payload['graph_ref']}
        payload['metadata']=metadata
        report_ref=persist_causal_effect_report(writer,CausalEffectReport.model_validate(payload))
        report=load_causal_effect_report(FileSystemCAS(directory),report_ref)
        assert report.model_dump(mode='json')==payload
        assert report.status is EstimationStatus.SUCCESS
        assert report.confidence_interval==native.confidence_interval
        assert report.metadata['gate_eligible'] is True
        envelope=report.to_uncertainty_envelope()
        assert envelope.gate_eligible is False
        # Retained gate marker/relabelled source is also refused by real confidence intake.
        offered=envelope.model_copy(update={'gate_eligible':True,'source':UncertaintySource.ENSEMBLE,
            'metadata':{**envelope.metadata,'identification_verified':True,'verifier_role':'system_verifier'}})
        envelope_ref=persist_uncertainty_envelope(writer,offered)
        issues=ConfidencePass().validate(_context(FileSystemCAS(directory),{'causal_envelope_ref':envelope_ref}))
        blockers=[i for i in issues if i.severity is IssueSeverity.BLOCKER and i.code=='CONFIDENCE_GATE_ELIGIBILITY_LOW'
            and i.path==['artifacts_index','causal_envelope_ref']]
        assert len(blockers)==1
        estimand=EstimandSpec(query_id='installed-native-tmle-value',estimand_id=report.estimand,
            outcome='Y',treatment_or_exposure='A',population='synthetic600',unit='Y',target_role='causal')
        offered_result=replace(result,output={'report':report},slot_outputs={'report':report})
        refusal=project_method_value_evidence(method_signature=TMLEEstimator.signature,
            method_result=offered_result,estimand=estimand,selected_output_slot='report')
        assert isinstance(refusal,MethodValueRefusal)
        assert refusal.reason_code=='method_output_contract_unresolved'
        cases.append(dict(basis=basis,report_ref=str(report_ref.artifact_id),envelope_ref=str(envelope_ref.artifact_id),
            numerical_status=report.status.value,retained_gate_marker=True,actual_projection_gate=False,
            actual_confidence_blocker=blockers[0].code,value_refusal=refusal.reason_code,value_guard_312_reached=False))
    print(json.dumps(dict(native_method=TMLEEstimator.signature.fqn,actual_method_jobs=len(recorded),
        maintained_six_fold_consumer='executed once through real MethodJob, CAS and fresh reader',
        boundaries=cases,authority='synthetic candidate only; production Node/admission/B56 common budget UNRUN'),sort_keys=True))
