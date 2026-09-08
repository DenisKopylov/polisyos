"""Remove N5 refusal behavior in memory, retaining the function and all markers."""

import json
import runpy

from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
from tools.quality.validation import check_layer3_gy_joint_simulation_horizon_contract as owner


checks = runpy.run_path("tests/unit/runtime/quality/test_generation_cycle.py")
gate = checks["test_real_unsupported_n5_result_is_serialized_as_simulation_blocked"]
gate()
good_result = JointSimulationHorizonController().run(owner._request())
baseline = gc._joint_simulation_port_outcome(good_result)
original = gc._joint_simulation_port_outcome


def removed(result):
    return "joint_simulated", tuple(result.promotion_ready_value_packet.get("authority_blockers", ()))


original.__code__ = removed.__code__
after = gc._joint_simulation_port_outcome(good_result)
print(json.dumps({"baseline_refusal_gate": "pass", "supported_before": baseline, "supported_after": after, "supported_unchanged": baseline == after, "marker_retained": original.__name__}, indent=2), flush=True)
assert baseline == after, "positive_control_must_stay_valid"
gate()
