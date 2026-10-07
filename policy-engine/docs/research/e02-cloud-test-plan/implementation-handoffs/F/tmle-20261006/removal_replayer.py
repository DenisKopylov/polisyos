"""Run in-memory semantic removals against the unchanged native regression gates."""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from polisyos.foundry.methods.catalog.causal import tmle_core as core

mode = sys.argv[1]
test = "tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py"
function = {
    "cache": core._shared_nuisance_cache_key,
    "arrays": core._readonly_array,
    "logit": core.fit_tmle_ate,
    "eif": core.fit_tmle_ate,
    "eligibility": core.fit_tmle_ate,
    "serial": core._fit_crossfit_nuisance_bundle_uncached,
}[mode]
source = inspect.getsource(function)
before = source
if mode == "cache":
    anchor = '    explicit = None if params is None else params.get("__shared_nuisance_key")\n'
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '    if explicit is not None:\n        return repr((explicit, _contract_fingerprint(contract)))\n')
    selector = test + "::test_same_caller_label_does_not_bypass_fit_identity"
elif mode == "arrays":
    source = 'def _readonly_array(value):\n    array = np.array(value, copy=True)\n    array.setflags(write=False)\n    return array\n'
    selector = test + "::test_native_cold_warm_rebind_and_reader_isolation"
elif mode == "logit":
    assert source.count("q1_star = _expit(logits1)") == 1
    source = source.replace("q1_star = _expit(logits1)", "q1_star = q1_star + step / e")
    source = source.replace("q0_star = _expit(logits0)", "q0_star = q0_star - step / (1.0 - e)")
    selector = test + "::test_poor_bounded_initial_predictions_use_logit_not_clipped_identity"
elif mode == "eif":
    anchor = "se = float(np.std(eif_values, ddof=1) / np.sqrt(eif_values.size))"
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + " * np.sqrt(contract.crossfit_folds / (contract.crossfit_folds - 1))")
    selector = test + "::test_native_binary_target_score_ate_and_eif_oracle"
elif mode == "eligibility":
    assert source.count("if not limitations:") == 1
    source = source.replace("if not limitations:", "if True:")
    selector = test + "::test_observed_positivity_failure_is_limited_at_actual_method_consumer"
elif mode == "serial":
    tree = ast.parse(source)
    assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign) and
                      any(isinstance(t, ast.Name) and t.id == "fold_results" for t in n.targets))
    call = ast.unparse(assignment.value.elt)
    lines = source.splitlines()
    lines[assignment.lineno - 1:assignment.end_lineno] = [
        "    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:",
        f"        fold_results = list(executor.map(lambda task: {call}, tasks))",
    ]
    source = "\n".join(lines) + "\n"
    core.ThreadPoolExecutor = ThreadPoolExecutor
    selector = test + "::test_native_studies_wait_in_actual_worker_pool_without_nested_fold_fanout[1]"
print(json.dumps({"mode": mode, "module": core.__file__, "function": function.__name__,
                  "original_function_sha256": hashlib.sha256(before.encode()).hexdigest(),
                  "mutated_function_sha256": hashlib.sha256(source.encode()).hexdigest(),
                  "selector": selector, "mutation_scope": "memory-only; markers and test unchanged"}))
exec(compile(source, core.__file__, "exec"), core.__dict__)
if function.__name__ == "fit_tmle_ate":
    from polisyos.foundry.methods.catalog.causal import treatment_effects
    treatment_effects.fit_tmle_ate = core.fit_tmle_ate
raise SystemExit(pytest.main([selector, "-v", "-s"]))
