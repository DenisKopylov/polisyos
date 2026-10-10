# Policy runtime support decomposition

State: implementation ready for independent review; no commit made.

## Pattern pass

- `P27` and `P31`: retain `policy_runtime_support.py` as the single canonical facade and keep the production backend and promotion producer in place. The two helpers are implementation modules; source and test callers still import through the existing support path.
- `P29`: preserve behavior with executed policy-runtime, CAS work-packet, module-reload, and hierarchical safety tests. The evidence is behavioral, not a source-marker check.
- `P13`: split the 1,536-nonblank-line support module into bounded units while keeping every source module below 1,000 nonblank lines.
- Existing issue: support implementation mixed typed contracts and backend ownership with metric projection, artifact/CAS workflows, latent-bundle resolution, and evidence-binding checks. Target pattern: typed contracts and owner entry points remain canonical; adjacent helpers hold the implementation for artifacts/evidence and metric projections.
- Capability status: this is a behavior-preserving decomposition, not a new capability. Existing draw execution remains `not_instrumented`, and no new artifact schema or authority claim is introduced.

## Footprint

- Canonical facade: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py` — 946 nonblank lines. Public contract classes, production and synthetic backend classes, `run_promotion_with_evidence`, `__all__`, and compatibility wrapper signatures remain here.
- Artifact/evidence helper: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_artifacts.py` — 701 nonblank lines. It owns artifact builders/loaders, CAS writes, latent-bundle resolution internals, and the pure evaluation evidence-binding implementation.
- Metric helper: `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_metrics.py` — 400 nonblank lines. It owns pure score/projection functions, parsing helpers, and shared runtime validation/load error tuples.
- Characterization tests: `tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support_decomposition.py` pins canonical runtime type and producer-entry FQNs/signatures and exercises the public projection, including the existing uninstrumented draw state.
- Release fragment: `release-fragments/unreleased/2026-10-09-e02-policy-runtime-support-decomposition.toml`.
- The shared `src/polisyos/scientist/nodes/README.md` was not edited. Suggested paragraph was sent to its owner.

The support wrappers pass existing owner globals into helper implementations where runtime lookup is observable: metric parser/projection seams, selection scoring, policy-evaluation loaders and persistence, latent-resolution type construction, and evidence-binding blocker/hash/verifier collaborators. This keeps the original support names monkeypatchable and preserves the `ProductionPolicyEvaluationBackend` and `run_promotion_with_evidence` module identity.

## Verification

Final focused command passed 20 tests with no failures or skips in 17.057 seconds. It covered the support behavior suite, the new facade characterization, CAS work-packet tests, the cross-module policy-vector reload consumer, and the hierarchical fail-closed evaluator consumer. Complete stdout, stderr, JUnit XML, command, timing, source hashes, and output hashes are recorded under `LOCAL/raw/policy-support-native-decomposition/focused-final.*`; JUnit SHA-256 is `fb74a19d5a3b0ddb672b80e8b41c5e8716c6696ba2e18832327d099468b8a84d`.

Ruff, formatting, Python compilation, and C901 with the agreed complexity ceiling of 12 all passed. Full command/output receipts are `ruff-final.*`, `c901-cap12-final.*`, `format-final.*`, and `compile-final.*` in the same raw directory. The proxy-boundary merge helper’s remaining C901 complexity is 11; it is within the approved ceiling, and no cosmetic threshold-10 refactor was added.

The pre-edit support suite passed 12 tests; its receipt is `baseline-support.*`. An earlier in-progress import-order error (`_runtime_metrics` referenced before the helper import) was captured as `after-first-support.*`, corrected, and is absent in the final run. A separate pre-edit module-reload/hierarchical collection attempt captured an import error in another current shared-tree module; after the independent owner repaired that import, both consumer tests passed and are included in `focused-final`. This earlier red is retained but not classified as inherited because its relationship to the pinned pre-work base was not established.

The pre-edit canonical import census is `LOCAL/raw/policy-support-native-decomposition/api-census.json` (5,602 Python files: 2,731 source and 2,871 tests; 14 referencing files; no parse errors). The tracked canonical source hash in that baseline census is `0890dfbf8553504a094813d4d6e54248e82cca8628d1f04ca759db4bdd2d7d6d`.

No native GP/TMLE fit or broad suite was run. This decomposition does not change the pending B157/B108 scientific or fiscal limitations.
