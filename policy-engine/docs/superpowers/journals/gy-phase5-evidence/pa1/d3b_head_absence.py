"""Read-only production-source challenge: lost event must not promote copied progress."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.control import generation_cycle as bridge
from tests.unit.runtime.http.test_control_service_di import _signed_generation_evidence
from tests.unit.runtime.http.test_normative_evidence_intake import completed_worker

scratch = Path('.tmp/gyphase5-pa1-head-absence')
scratch.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(dir=scratch) as directory:
    fixture = completed_worker.__wrapped__(SimpleNamespace(mktemp=lambda name: Path(directory)))
    service, before, compiled = next(fixture)
    try:
        evidence = _signed_generation_evidence(service, compiled, fault='authorized')
        admitted = service.submit_normative_evidence(
            run_id=before.run_id,
            submission=bridge.NormativeEvidenceSubmissionRequest(
                job_id=before.job_id, expected_prior_head_ref=None, evidence=evidence,
            ),
        )
        assert admitted.status == 'admitted'
        service._control_store.upsert_progress(job_id=before.job_id, progress=admitted.job.progress)
        with pytest.MonkeyPatch.context() as patches:
            patches.setattr(service._control_store, 'get_normative_evidence_head', lambda job_id: None)
            current = service.get_job_status(before.job_id)
        output = {
            'scope': 'Actual worker, admitted signed fixture S8 evidence, real persisted progress copy; event owner omission injected only in process, no production source edits',
            'job_id': before.job_id,
            'initial_disposition_ref': before.progress['normative_disposition_ref'],
            'initial_status': before.progress['normative_disposition']['authorization_status'],
            'admitted_head_ref': admitted.head_ref,
            'copied_disposition_ref': admitted.job.progress['normative_disposition_ref'],
            'current_status_without_event': current.progress['normative_disposition']['authorization_status'],
            'current_rankings_without_event': current.progress['normative_disposition']['ranked_recommendations'],
            'current_head_ref_without_event': current.progress.get('normative_head_ref'),
        }
        print(json.dumps(output, indent=2), flush=True)
        assert output['initial_status'] == 'blocked'
        assert output['current_status_without_event'] == 'blocked', 'copied progress bypasses absent admitted head'
    finally:
        try:
            next(fixture)
        except StopIteration:
            pass
