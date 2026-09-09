"""Actual native falsifiers with one property removed in memory; no source writes."""
from __future__ import annotations
import argparse
import copy
import inspect
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
import pytest
from polisyos.runtime.quality.workspace import loop
from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner
from tests.unit.runtime.quality.workspace.test_production_case_admission import actual_pinned_intake_payload

BASE=Path(__file__).resolve().parent
PREFIX='tests/unit/runtime/quality/workspace/test_production_case_admission.py::'
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('s1-execution','original-source','gx-result-consumption','workspace-union'));args=parser.parse_args()
if args.mode=='s1-execution':
    # Generate the complete original claim population through the actual source
    # owner/S1 once before the mutation. Those real snapshots keep every output
    # marker while the actual run no longer invokes S1.
    with tempfile.TemporaryDirectory(dir=BASE,prefix='s1-removal-') as tmp:
        with build_recorded_file_fetch_owner(Path(tmp)/'source') as owner:
            prior=loop._compose_production_case_admission(
                intake=loop.ProductionCaseIntake.model_validate(actual_pinned_intake_payload()),
                request_ref='sha256:'+'0'*64,catalog=owner.graph,checked_at=datetime.now(UTC),
            )
    snapshots={decision.claim_id:decision.model_dump(mode='json') for decision in prior.graded_decisions}
    expected=[row['construct_ref'] for row in actual_pinned_intake_payload()['pinned_request']['requested_constructs']]
    assert set(snapshots)==set(expected) and len(snapshots)==len(expected)
    def without_actual_s1(evidence):
        return loop.GradedOutcomeDecision.model_validate(copy.deepcopy(snapshots[evidence.claim_id]))
    source=inspect.getsource(loop._compose_production_case_admission)
    needle='decision = compose_graded_outcome(evidence)'
    assert source.count(needle)==1
    changed=source.replace(needle,'decision = _j_removed_actual_s1(evidence)',1)
    scope=dict(loop.__dict__);scope['_j_removed_actual_s1']=without_actual_s1
    exec(compile('from __future__ import annotations\n'+changed,inspect.getsourcefile(loop._compose_production_case_admission),'exec'),scope)
    loop._compose_production_case_admission=scope['_compose_production_case_admission']
    print(json.dumps({'removed_property':'actual_s1_before_terminal','whole_original_claim_identities':expected,'source_and_schema_markers_retained':True,'snapshots_built_by_real_owner_before_removal':True},sort_keys=True),flush=True)
    node=PREFIX+'test_production_attempts_original_requirements_through_s1_before_terminal'
elif args.mode=='workspace-union':
    from pydantic import create_model
    original=loop.WorkspaceSearchExitContract
    loop.WorkspaceSearchExitContract=create_model(
        'WorkspaceSearchExitContractWithoutRefusalUnion',__base__=original,
        workspace_contract=(loop.WorkspaceContract,...),
    )
    print(json.dumps({'removed_property':'preserve_refusal_workspace_at_actual_result_serialization','markers_and_component_nulls_remain':True}),flush=True)
    node=PREFIX+'test_actual_production_workspace_custody_survives_annotated_reader'
elif args.mode=='gx-result-consumption':
    from tools.quality.validation import check_layer3_gy_loop_artifacts as proof_owner
    source=inspect.getsource(proof_owner._compare_j_current_outputs)
    needle='expected = old_packet["verification"]'
    assert source.count(needle)==1
    changed=source.replace(needle,'expected = committed[OUTCOME_RUN_PATH]["gx_validation"]',1)
    scope=dict(proof_owner.__dict__)
    exec(compile('from __future__ import annotations\n'+changed,inspect.getsourcefile(proof_owner._compare_j_current_outputs),'exec'),scope)
    proof_owner._compare_j_current_outputs=scope['_compare_j_current_outputs']
    print(json.dumps({'removed_property':'consume_actual_recorded_gx_result','gx_still_runs_and_all_markers_remain':True}),flush=True)
    node='tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py::test_full_recorded_gx_is_replayed_and_failed_marker_cannot_disappear'
else:
    loop._verify_production_case_intake=lambda *_args,**_kwargs:None
    print(json.dumps({'removed_property':'actual_original_source_readback','source_hash_and_schema_markers_retained':True},sort_keys=True),flush=True)
    node=PREFIX+'test_original_source_markers_do_not_admit_changed_demand'
raise SystemExit(pytest.main(['-q','-rA','--show-capture=no','--tb=short',node]))
