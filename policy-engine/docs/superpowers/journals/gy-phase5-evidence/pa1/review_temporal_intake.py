"""Independent post-compilation evidence-intake witness; no source edits."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.control import generation_cycle as bridge
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from tests.unit.runtime.http.test_control_service_di import (
    _signed_generation_evidence,
    test_process_nl_job_enters_persisted_tenant_scope,
)

capture = {}
original_process = ControlPlaneService._process_control_job
original_close = ControlPlaneService.close


def observe(self, job):
    capture.update(service=self, job_id=job.job_id)
    return original_process(self, job)


root = Path.cwd() / ".tmp" / "gyphase5-pa1-independent-review"
root.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(dir=root) as work:
    with pytest.MonkeyPatch.context() as patches:
        patches.setattr(ControlPlaneService, "_process_control_job", observe)
        patches.setattr(ControlPlaneService, "close", lambda self: None)
        asyncio.run(
            test_process_nl_job_enters_persisted_tenant_scope(patches, Path(work), "missing")
        )
    service, job_id = capture["service"], capture["job_id"]
    try:
        before = service.get_job_status(job_id)
        compiled_ref = before.progress["compiled_recursive_generation_cycle_ref"]
        compiled = bridge.CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(
                service._artifact_store.get_bytes(artifacts.ArtifactID.model_validate(compiled_ref))
            )
        )
        evidence = bridge.NormativeRunEvidenceRefs.model_validate(
            _signed_generation_evidence(service, compiled, fault="authorized")
        )
        direct = service.resolve_generation_value_choices(
            compiled_run_ref=compiled_ref, evidence=evidence, evaluated_at=datetime.now(UTC)
        )
        after = service.get_job_status(job_id)
        latest = service.get_latest_job_for_run(before.run_id)
        result = {
            "scope": "Actual worker and actual current readers; explicit signed fixture permission created AFTER source exists; upstream compiler is the existing injected canonical fixture port, not a production governed-design claim",
            "job_id": job_id,
            "compiled_run_ref": compiled_ref,
            "before_status": before.progress["normative_disposition"]["authorization_status"],
            "before_sidecar_ref": before.progress["normative_disposition_ref"],
            "post_source_owner_status": direct.authorization_status,
            "post_source_owner_rankings": direct.ranked_recommendations,
            "post_source_owner_sidecar_ref": direct.disposition_ref,
            "after_status": after.progress["normative_disposition"]["authorization_status"],
            "after_sidecar_ref": after.progress["normative_disposition_ref"],
            "latest_status": latest.progress["normative_disposition"]["authorization_status"],
            "latest_sidecar_ref": latest.progress["normative_disposition_ref"],
            "new_sidecar_consumed_by_current_job": after.progress["normative_disposition_ref"] == direct.disposition_ref,
        }
        print(json.dumps(result, indent=2))
        assert direct.authorization_status == "authorized"
        assert after.progress["normative_disposition"]["authorization_status"] == "blocked"
        assert after.progress["normative_disposition_ref"] == before.progress["normative_disposition_ref"]
        assert latest.progress["normative_disposition_ref"] == before.progress["normative_disposition_ref"]
    finally:
        original_close(service)
