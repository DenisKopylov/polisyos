# BERL method identity

**Owner:** `@scientist-owners`

**Source of truth:** `src/polisyos/berl/service.py`,
`src/polisyos/berl/adapters/{shap_kernel.py,shap_tree.py,gradients.py}`,
`src/polisyos/berl/metrics/disagreement.py`, and the test locations below.

**Source snapshot reviewed:** `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` (2026-10-14).

**Evidence caveat:** source and test locations were inspected at this snapshot;
this documentation update did not run those tests. This page describes the
in-memory BERL explanation path, not deployment, policy admissibility, or
publication authority.

In brief, this page explains how the in-memory BERL service records both the
requested explanation method and the adapter profile that actually runs. The
adapter determines `effective_method_id`; its returned payload cannot replace
that binding after execution. This page also describes when a built-in result
may be reused, when a request uses an explicit fallback, and when the service
returns a diagnostic without an attribution. This service path adds no
migration or rewrite of persisted bundles.

## Built-in profiles

| Requested identifier | Effective profile | Result posture |
| --- | --- | --- |
| `kernel_shap`, `kernel_shap_marginal` | `kernel_shap` | Exact Shapley enumeration over the supplied empirical replacement background for `marginal` or `marginal_interventional` profiles. Compatible aliases may reuse one result within the same `explain()` call. |
| `tree_shap` | `kernel_shap` | Explicit empirical fallback. The result records the fallback reason and does not claim TreeSHAP exactness. |
| `gradient`, `finite_difference_gradient` | `finite_difference_gradient` | One finite-difference implementation profile. |
| `kernel_shap_conditional` | `kernel_shap_conditional` (diagnostic route) | No attribution; the default route reports that a verified conditional law is unavailable. |

KernelSHAP requests under any other feature-dependence profile, including the
default `conditional_observational`, also return a diagnostic without
attribution.

`disagreement.methods_compared` contains distinct effective profile IDs, not
the number of request names. Distinct adapter configurations remain separate
executions even when they declare the same effective profile; they do not
become independent methods by configuration alone. Each request still
receives its requested ID and its own result presentation. A reused tree
computation is presented as a fallback only for `tree_shap`; it cannot make a
kernel result inherit tree assumptions, and a kernel result cannot erase
fallback metadata from a later tree request.

Reuse is scoped to one `ExplanationOrchestrator.explain()` call. The cache key
binds the exact registered built-in adapter type and its supported frozen
configuration, model object identity and declared model IDs, hashes, and
calibration refs, input row, feature set, background, adapter parameters,
constraints, feature-dependence and output-scale context, random seed,
perturbation/evaluation settings, infidelity settings, and whether redundancy
is enabled. Only exact built-in
types in `default_adapters` are cache-eligible; their declared dataclass fields
are encoded from those types. Custom adapters and subclasses remain executable
but run independently because the adapter protocol has no admitted
cache-configuration contract. Unsupported or opaque request/configuration
values disable reuse instead of being approximated; `id(model)` is used
specifically as the per-call model-object identity. Changed model, background,
or built-in adapter configuration therefore cannot reuse an earlier result.

## Confidence and limits

The union adjustment counts requested method identifiers, including aliases;
computational reuse does not reduce that claim count. This keeps the
confidence adjustment separate from whether two requests can share an
adapter computation.

The inspected built-in adapters do not provide a verified conditional feature
law or a native path-dependent TreeSHAP backend. `kernel_shap_conditional`
remains diagnostic-only, and `tree_shap` is an explicitly labelled empirical
fallback; neither label establishes causal effect semantics.

Behavioral coverage is in `tests/unit/remediation/test_ber_01.py`, including
request-order permutations, duplicate aliases, fallback presentation,
unsupported conditional routes, false result self-labels, adapter-configuration
changes, model/background sensitivity, and confidence posture. These test
cases are evidence locations, not fresh execution receipts.
