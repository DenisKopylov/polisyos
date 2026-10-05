"""Frozen-source discriminator for actual candidate content binding.

Run outside repository conftest with PYTHONPATH pinned to an immutable source
archive. The control variant changes only the production binding method's body
in a second isolated copy. All CAS references, original declarations, and model
compatibility markers remain present in both executions.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

from botorch.models import SingleTaskGP

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.scientist.methods.autotune import bayesian_generator, warm_start
from polisyos.scientist.methods.autotune.models import persist_benchmark_evaluation
from polisyos.scientist.methods.search.strategies import bayesian, transfer
from polisyos.scientist.methods.search.strategies._deps import require_torch


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


fixture_path = Path(os.environ["TRANSFER_REVIEW_FIXTURE"])
fixture_spec = importlib.util.spec_from_file_location("transfer_review_fixture", fixture_path)
fixture = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)

with tempfile.TemporaryDirectory(prefix="transfer-content-review-input.") as folder:
    store, index, space, source, observations, originals = fixture._measured_history(Path(folder))
    actual_candidate = store.put_json(
        {"params": {"x": 0.95}},
        PutOptions(kind="search.candidate", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    original = originals[0].model_copy(update={"candidate_ref": actual_candidate}, deep=True)
    original_ref = persist_benchmark_evaluation(store, original)
    observations[0].candidate_id = str(actual_candidate.artifact_id)
    observations[0].provenance_ref = str(original_ref.artifact_id)
    source.history_ref = transfer.TransferLearningManager(store, index).register_run(
        source, observations
    )
    history = from_canonical_bytes(store.get_bytes(source.history_ref.artifact_id))
    _expect(
        history["evaluations"][0]["params"] == original.metadata["params"] == {"x": 0.1},
        "All original/history physical declarations must remain unchanged",
    )
    _expect(
        original.metadata["warm_start_compatibility"]
        == observations[0].metadata["warm_start_compatibility"],
        "All model/context markers must remain unchanged",
    )
    _expect(
        from_canonical_bytes(store.get_bytes(actual_candidate.artifact_id))["params"]
        == {"x": 0.95},
        "Actual candidate content must differ",
    )
    reader = transfer.TransferLearningManager(store, index)
    target = source.model_copy(update={"run_id": "target", "history_ref": None})
    generator = bayesian_generator.BayesianCandidateGenerator(
        space,
        n_initial=3,
        seed=47,
        warm_start_bridge=warm_start.WarmStartBridge(reader, max_evals=4),
        warm_start_fingerprint=target,
    )
    _expect(generator.botorch_available, "Real receiving backend is required")
    generator._optimizer._config.num_restarts = 3
    generator._optimizer._config.raw_samples = 32
    generator._optimizer._config.fallback_on_failure = False
    proposal = generator.generate([], None, {})
    model = generator._optimizer._model
    _expect(isinstance(model, SingleTaskGP), "Control must use the actual receiving GP")
    actual_x = model._original_train_inputs
    if actual_x is None:
        actual_x = model.train_inputs[0]
    raw_y, _ = model.outcome_transform.untransform(model.train_targets.unsqueeze(-1))
    sys.stdout.write(
        json.dumps(
            {
                "variant": os.environ["TRANSFER_REVIEW_VARIANT"],
                "actual_import_origins": {
                    owner.__name__: owner.__file__
                    for owner in (transfer, warm_start, bayesian_generator, bayesian)
                },
                "actual_candidate_ref": str(actual_candidate.artifact_id),
                "original_evaluation_ref": str(original_ref.artifact_id),
                "history_ref": str(source.history_ref.artifact_id),
                "actual_candidate_params": {"x": 0.95},
                "original_and_history_params": {"x": 0.1},
                "actual_GP_train_inputs": actual_x.reshape(-1, 1).tolist(),
                "actual_GP_unstandardized_targets": raw_y.reshape(-1, 1).tolist(),
                "accepted": reader.last_restore_report.accepted_rows,
                "rejected": reader.last_restore_report.rejected_rows,
                "proposal_source": proposal["_strategy_metadata"]["source"],
                "rejection_reasons": [issue.reason for issue in reader.last_restore_rejections],
            },
            sort_keys=True,
        )
        + "\n"
    )
    sys.stdout.flush()
    torch = require_torch()
    expected_x = torch.tensor([[0.4], [0.7], [0.9]], dtype=torch.float64)
    torch.testing.assert_close(actual_x.reshape(-1, 1), expected_x)
    _expect(
        reader.last_restore_report.accepted_rows == 3, "Exactly three observations are admissible"
    )
    _expect(reader.last_restore_report.rejected_rows == 1, "Exactly one input conflict is rejected")
    _expect(
        reader.last_restore_rejections[0].candidate_id == str(actual_candidate.artifact_id),
        "Rejected actual candidate identity must remain visible",
    )
    _expect(
        reader.last_restore_rejections[0].reason
        == "actual candidate parameters differ from the transferred observation",
        "The actual input conflict must be the deciding reason",
    )
