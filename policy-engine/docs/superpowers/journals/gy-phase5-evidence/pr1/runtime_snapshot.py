"""Execute current PR1 contract/composition/scope owners without minting a receipt."""

import ast
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import get_args

from polisyos.pdc import EvaluationMode
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality import promotion_sequence as ps


controller = gc.GenerationCycleController(repo_root=Path.cwd())
classes = {name: value for name, value in vars(ps).items() if isinstance(value, type) and "Projection" in name}
mode_tree = ast.parse(Path("src/polisyos/pdc/_impl/evaluation_safety.py").read_text())
mode_definition = next(node.value for node in mode_tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "EvaluationMode" for target in node.targets))
ast_modes = tuple(ast.literal_eval(mode_definition.slice))
live_modes = get_args(EvaluationMode)
assert set(ast_modes) == set(live_modes)
report = {
    "input_schema": ps.CanonicalPromotionInput.model_fields["schema_version"].default,
    "input_fields": sorted(ps.CanonicalPromotionInput.model_fields),
    "input_has_caller_predicate": {name: name in ps.CanonicalPromotionInput.model_fields for name in ("admissibility", "effective_independence")},
    "default_controller_promotion_port": type(controller._promotion_port).__name__,
    "default_controller_context_provider": repr(controller._promotion_port._context_provider),
    "default_controller_value_port": type(controller._value_port).__name__,
    "evaluation_mode_denominator": {"path": "src/polisyos/pdc/_impl/evaluation_safety.py:EvaluationMode", "runtime_modes": live_modes, "ast_modes": ast_modes, "identity_sets_equal": True},
    "eval_safety_by_mode": {
        mode: ps._eval_safety_obligation(SimpleNamespace(evaluation_mode=mode)).model_dump(mode="json")
        for mode in live_modes
    },
    "source_owners": {
        name: inspect.getsource(getattr(ps, name))
        for name in ("_coupling_obligation", "_effect_obligation", "_measurement_obligation", "_effective_independence_obligation", "_bind_production_promotion_evidence")
    },
}
path = "src/polisyos/runtime/quality/evaluation_safety.py"
current = Path(path).read_bytes()
base = subprocess.check_output(["git", "show", f"3d572c146:policy-engine/{path}"])
report["safety_source_integrity"] = {"path": path, "base": "3d572c146", "base_sha256": hashlib.sha256(base).hexdigest(), "current_sha256": hashlib.sha256(current).hexdigest(), "byte_identical": current == base}
plan = Path("docs/plans/active/layer3-slices/GY-engine-subordination.md").read_text()
start = plan.index("- **GY-PR1 — Promotion-obligation repair")
end = plan.index("- **GY-AQ1", start)
report["plan_task_full_text"] = plan[start:end]
print(json.dumps(report, indent=2))
