# BERL method identity

BERL preserves the identifier requested by a caller and separately reports the implementation profile selected by the service. The selected adapter determines `effective_method_id`; an adapter result payload cannot replace that binding after execution. Existing persisted bundles retain their historical method IDs and are not rewritten.

## Built-in profiles

| Requested identifier | Effective profile | Result posture |
| --- | --- | --- |
| `kernel_shap`, `kernel_shap_marginal` | `kernel_shap` | Exact empirical Shapley over the supplied background. Identical request identities reuse one computation. |
| `tree_shap` | `kernel_shap` | Explicit empirical fallback. The result records the fallback reason and does not claim TreeSHAP exactness. |
| `gradient`, `finite_difference_gradient` | `finite_difference_gradient` | One finite-difference implementation profile. |
| `kernel_shap_conditional` | unavailable | Diagnostic only, with no attribution, unless a verified conditional-law implementation is added. |

`disagreement.methods_compared` contains distinct effective profile IDs, not the number of request names. Distinct adapter configurations remain separate executions even when they declare the same effective profile; they do not become independent methods by configuration alone. Each request still receives its requested ID and its own result presentation. A cached tree fallback is presented as a fallback only for `tree_shap`; it cannot make a later kernel result inherit tree assumptions, and a kernel result cannot erase fallback metadata from a later tree request.

The reuse key includes the selected implementation and complete configuration, model object and declared model identity, input row, feature set, background, adapter parameters, constraints, feature-dependence and output context, random seed, perturbation/evaluation settings, and validation settings. Automatic reuse is limited to the exact source-owned built-in adapter types registered in `default_adapters`; their dataclass fields are read from those exact classes and encoded with type-tagged snapshots. The allowlist is pinned to the registered built-in type set. Subclasses and custom adapters, including frozen dataclasses with enumerable fields, remain supported but execute each selected route independently until the protocol has a source-owned cache-configuration contract. This is a performance limitation only and does not change capability or authority. Opaque request values disable reuse, and no object IDs, type names, or `repr` strings stand in for unknown state. A changed model, background, or built-in adapter configuration therefore does not reuse an earlier result.

## Confidence and limits

Alias calculation reuse does not change the confidence-budget law. The current union adjustment continues to count requested methods, including aliases, because computation reuse and the number of protected claims are separate decisions. No explanation-bundle schema change is required.

This consolidation does not add a conditional feature law or a native path-dependent TreeSHAP backend, and it does not change the empirical attribution algorithm or its assumptions. Conditional requests remain diagnostic-only.

Behavioral coverage is in [`test_ber_01.py`](../../tests/unit/remediation/test_ber_01.py), including request-order permutations, duplicate aliases, fallback presentation, unsupported conditional routes, false result self-labels, adapter-configuration changes, model/background sensitivity, and confidence posture.
