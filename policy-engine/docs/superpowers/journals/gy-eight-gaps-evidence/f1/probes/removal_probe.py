"""Run the unmodified current F1 gate after removing actual workflow execution."""
from unittest.mock import patch
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from tools.quality.validation import check_layer3_workflow_failure_authority as owner

with patch.object(ControlPlaneService, "_run_legacy_scientist_workflow", lambda *args: None):
    raise SystemExit(owner.main(["--check", "--output-format", "json"]))
