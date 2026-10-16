# BERL method identity

**Owner:** `@scientist-owners`

**Source of truth:** `src/polisyos/berl/service.py`,
`src/polisyos/berl/adapters/{shap_kernel.py,shap_tree.py,gradients.py}`,
`src/polisyos/berl/metrics/disagreement.py`, and the test locations below.

**Candidate base:** `514fc9ca4a9bdadd7c617cdb5cc0b8c10e592a76`; the R4 service postimage is pinned at `src/polisyos/berl/service.py@sha256:d090bf2617430ccaf808ac3bd4c8912638a91400d31428a291c8b97b7a0c9611`.

**Candidate verification:** the strict generated Mypy profile reported no issues for the service shadow; the focused service/integration run passed 20 tests, the identity compatibility controls passed 8, and the exact built-in cache controls passed 8. The selected root Ruff check and format check passed for all three candidate Python files. Receipts are preserved under `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/la036-berl-nonexecution-identity-r4-typing-release-20261017/verification/`: strict Mypy command `r4-official-core-runtime-mypy-shadow-leaf-final2-20261017-command.json@sha256:d32cb82360aa87b68a8c567ac14201f5be3a91d8f930523cff94822a0fe20e1f`; focused tests `r4-focused-leaf-final-20261017-command.json@sha256:5e7a7558b90b1d03892221620b26effa1a123eabaf3b97915aa319823eeb9fae`; identity controls `r4-identity-controls-leaf-final-20261017-command.json@sha256:c2802319635a6efffdb87577980b975f9412eb1133ab9d3318a13d330c37e17c`; cache controls `r4-cache-controls-leaf-final-20261017-command.json@sha256:a08411ca8116b33576bb631ddf5af1e4dd18c285c755ecdd453356f628af4d57`; root Ruff and format `r4-root-ruff-format-leaf-final-20261017-command.json@sha256:487ba50ffe98bcfa8931dd5d02ba5c4e5b9e3affd452e1ef499465a0bf30b085`.

These receipts cover the local in-memory explanation path and the named candidate bytes. They do not establish deployment, policy admissibility, or publication authority.

**Public-surface review:** `polisyos.berl` is `public_experimental` and owned by `team-scientist`. The independent scoped review `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/la036-berl-nonexecution-identity-r4-independent-review-20261017/review.json` @ `sha256:edbe5375f7afe49d80d697141d70f0fcd4ccd7bd5e60897b18c117b5d1366640` covers the single changed compatibility row: `ExplanationBundle.methods[].effective_method_id` and its `params["effective_method_id"]` mirror. It confirms `python-public-api` as the change class and that the existing nullable field, exports, and schema remain unchanged. The release metadata marks only this row reviewed; its aggregate `public_surface_inventory_reviewed` remains false. The review does not attest package-wide export completeness, owner authentication, G acceptance, or formal closure.

In brief, this page explains how the in-memory BERL service records both the
requested explanation method and the adapter profile that actually runs. The
adapter determines `effective_method_id`; its returned payload cannot replace
that binding after execution. This page also describes when a built-in result
may be reused, when a request uses an explicit fallback, and when the service
returns a diagnostic without an attribution. This service path adds no
migration or rewrite of persisted bundles. A diagnostic keeps the requested method ID and reason,
but leaves `effective_method_id` unset because selecting an adapter does not establish that it
produced an accepted result.

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

Reuse is scoped to one `ExplanationOrchestrator.explain()` call. A cache hit re-identifies an entry as an executed result only when it carries the accepted attribution vector. A cached pre-result or post-result diagnostic keeps its reason and receives the new requested ID, while `effective_method_id` remains unset.

The cache key
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
