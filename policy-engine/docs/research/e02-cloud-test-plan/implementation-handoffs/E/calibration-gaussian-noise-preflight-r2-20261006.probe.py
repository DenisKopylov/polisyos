import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


start = time.monotonic()
rows = []
original = IncomeTax.emit_patches
for label, value in [
    ("bool_true", True),
    ("numpy_bool_true", np.bool_(True)),
    ("float_positive", 2.0),
    ("zero", 0.0),
    ("nan", float("nan")),
    ("inf", float("inf")),
]:
    counts = {"loader": 0, "emitter": 0}

    def loader(_: object, *, counts: object = counts) -> dict[str, object]:
        counts["loader"] += 1
        return {"params": {"rate": 0.25}, "schedule": {"start_step": 0, "end_step": 0}}

    def observed_emitter(
        self: object, *args: object, counts: object = counts, **kwargs: object
    ) -> object:
        counts["emitter"] += 1
        return original(self, *args, **kwargs)

    IncomeTax.emit_patches = observed_emitter
    artifact = ArtifactID.from_sha256_hex("0" * 64)
    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        outputs=["agents.income", "government.balance"],
    )
    graph = ProgramGraph(
        ir_ref=ArtifactRef(
            artifact_id=artifact, kind="ir.trinity_bundle", media_type="application/json"
        ),
        nodes=[node],
        edges=[],
        entrypoints=[],
    )
    plan = ExecPlan(program_ref=ProgramGraphRef(artifact_id=artifact), order=["tax"])
    state = GlobalState.empty(n_agents=1, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.array([100.0], dtype=jnp.float32),
            reported_income=jnp.array([100.0], dtype=jnp.float32),
        ),
        government_balance=jnp.array(0.0, dtype=jnp.float32),
    )
    cfg = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="balance",
                model_metric_path="government_balance",
                loss={"relative": False},
            )
        ],
        steps=1,
        max_steps=1,
        seed=19,
        learning_rate=1e-9,
        hessian={"enabled": False},
    )
    inputs = CalibratorInputs(
        config=cfg,
        program_graph=graph,
        exec_plan=plan,
        base_state=state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"balance": [25.0]},
        gaussian_observation_std={"balance": value},
    )
    try:
        report = Calibrator(inputs).run()
        status = "returned_report"
        detail = {
            "total_loss": report.total_loss,
            "noise_scale": float(
                report.execution_context["objective_profile"]["observation_std"]["balance"]
            ),
            "gate_eligible": report.execution_context["objective_profile"]["gate_eligible"],
        }
    except Exception as exc:
        status = type(exc).__name__
        detail = {"message": str(exc)}
    finally:
        IncomeTax.emit_patches = original
    row = {
        "case": label,
        "input_type": type(value).__name__,
        "status": status,
        "counts": counts,
        "detail": detail,
    }
    rows.append(row)
    _write_stdout(json.dumps(row, sort_keys=True), flush=True)
modules = {
    name: str(Path(module.__file__).resolve())
    for name, module in sys.modules.items()
    if name.startswith("polisyos") and getattr(module, "__file__", None)
}
root = Path(os.environ["CAL_EXPECT_SOURCE_ROOT"]).resolve()
if not (all(Path(path).is_relative_to(root) for path in modules.values())):
    raise AssertionError("mixed product source origins")
_write_stdout(
    json.dumps(
        {
            "source_sha": os.environ["CAL_EXPECT_SOURCE_SHA"],
            "source_root": str(root),
            "module_count": len(modules),
            "module_origins_within_pinned_source": True,
            "calibrator_source_sha256": hashlib.sha256(
                Path(modules["polisyos.foundry.calibration.calibrator"]).read_bytes()
            ).hexdigest(),
            "environment": {
                "python": sys.version,
                "executable": sys.executable,
                "platform": platform.platform(),
                "jax": jax.__version__,
                "numpy": np.__version__,
                "jax_enable_x64": bool(jax.config.jax_enable_x64),
                "devices": [str(x) for x in jax.devices()],
                "thread_env": {
                    k: v
                    for k, v in os.environ.items()
                    if k.endswith("_NUM_THREADS") or k == "XLA_FLAGS"
                },
            },
            "wall_s": time.monotonic() - start,
        },
        sort_keys=True,
    ),
    flush=True,
)
