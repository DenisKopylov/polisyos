"""Recorded real-run closure controls; no new durable execution or copied body."""
import json
from pathlib import Path
import pytest
from tests.repo_quality.architecture import test_layer3_gy_artifact_lifecycle as target
from tools.quality.validation import check_layer3_workflow_failure_authority as owner

@pytest.mark.parametrize('field,key,value', [
 ('failure','message','forged failure content'),
 ('authority_boundary','known_limits',['forged limit']),
 ('authority_surface_packet','authority_result','grounded_admissible'),
 ('production_loop_run_proof','artifacts_index_refs',[]),
])
def test_detached_record(field,key,value):
 payload={owner.PROOF_PATH:json.loads(Path(owner.PROOF_PATH).read_text())}
 target.test_layer3_workflow_failure_authority_refuses_detached_progress_record(payload,field,key,value)

def test_unclaimed_output():
 payload={owner.PROOF_PATH:json.loads(Path(owner.PROOF_PATH).read_text())}
 target.test_layer3_workflow_failure_authority_refuses_unclaimed_progress_output(payload)
