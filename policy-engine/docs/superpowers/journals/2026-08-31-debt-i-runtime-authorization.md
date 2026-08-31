# Debt I Runtime Authorization Journal

## Session identity

- Worktree: `.worktrees/debt-i-runtime-authorization`.
- Branch: `codex/debt-i-runtime-authorization`.
- Base: `3be0797749a3a4dab0e16e7769ed8a2d02646134`.
- Starting state: attached, clean, and exactly at the base.
- Ownership boundaries preserved: no Task A, D, or J path was changed; no architect-owned
  register, ledger, plan, or denominator pin was edited; no generated schema or client was
  regenerated.

## Pattern pass

### Runtime authorization denominator reconciliation

- Relevant register patterns: `P29`, `P31`, `P35`, and `P37`.
- Existing anti-pattern: Router and OpenAPI each had an exact comparison with the same
  hand-authored mirror, but the two live projections had no direct equality witness. The mirror
  was also stale by two DS15 acquisition operations. Capability state before this row:
  `semantic_test_missing` for the Router/OpenAPI denominator invariant.
- Correct pattern: recompute Router set `R` from every live `APIRoute` dependency graph, recompute
  OpenAPI set `O` from every emitted operation extension, assert `R == O`, and only then compare
  both to the separately reviewed literal mirror. `R` and `O` are `recomputed`; the literal
  mirror is `institutionally_supplied` as a deliberate review pin and mismatch fails the test.
- Acceptance signal: the exact live test
  `tests/unit/runtime/http/test_runtime_step_up_authz.py::test_router_and_openapi_high_stakes_denominators_agree`
  executes the real app and exits 0; the complete two-file authz wave also exits 0.

### DS17 OpenAPI source admission

- Relevant register patterns: `P29` and `P32`.
- Investigated risk: a repository-root guess could make a valid owner artifact appear absent, or
  file presence could be mistaken for owner admission.
- Correct pattern: execute `ConfidenceLedgerRiskSpendProjectionService.get()` and the actual
  `_confidence_ledger_risk_spend_example()` in both configured-root and unset-root environments;
  require the owner service to return `AvailableConfidenceLedgerRiskSpendPacket`.
- Acceptance signal: both real executions returned `available`, projection id
  `confidence-ledger-risk-spend`, status `not_promoted`, and exited 0. No capability label remains
  missing and no source, schema, or client change is warranted.

### Core observability truthfulness shim residual

- Relevant register patterns: `P06`, `P28`, and `P35`.
- Existing anti-pattern: a deprecated Core compatibility owner remained reachable after the IR
  analytics facade became canonical. The pre-change complete Python census over `src/`, `tools/`,
  and `tests/` walked 5,520 `.py` files and found eight import statements / 22 aliases / six files.
- Correct pattern: point every remaining consumer at `polisyos.ir.analytics` and delete the
  predecessor in the same change.
- Acceptance signal: the post-change complete Python census walks 5,519 `.py` files and finds zero
  statements / zero aliases / zero files; the normalized exact grep returns `0`; 78 focused
  consumers pass.

## Measured authorization denominators before repair

The successful census used one live app and did not consult `_HIGH_STAKES_OPERATIONS` while
deriving either side. `R` came from `app.routes` plus recursive `_dependency_calls(route.dependant)`;
`O` came from `app.openapi()` operation extensions. It exited 0 with `R_count=10`, `O_count=10`,
`R_equals_O=true`, empty directional differences, no class mismatches, and no Router operation with
other than exactly one step-up dependency.

`R` and `O` were identical before any edit:

| Method and path | Step-up class |
| --- | --- |
| `POST /api/v1/control/data/ingest` | `acquisition_approval` |
| `POST /api/v1/control/data/promotion/{promotion_id}/approve` | `promotion` |
| `POST /api/v1/control/data/promotion/{promotion_id}/reject` | `promotion` |
| `POST /api/v1/control/decision-validity/epoch-batches` | `publication` |
| `POST /api/v1/control/decision-validity/events` | `publication` |
| `POST /api/v1/control/runs/{run_id}/reissue` | `revocation` |
| `POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request` | `acquisition_approval` |
| `POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute` | `acquisition_approval` |
| `POST /api/v1/runs/{run_id}/human-decisions` | `human_decision` |
| `POST /api/v1/runs/{run_id}/production-approval` | `production_approval` |

The finding was therefore not a Router/OpenAPI conflict. It was one missing cross-projection
witness plus a literal mirror whose denominator was eight while both live denominators were ten.

## Authorization mirror review receipt

- Proposal producer: the complete live `R`/`O` census above. Its exact proposal was
  `R - mirror == O - mirror` containing the two DS15 acquisition-route operations below.
- Reviewer: the Task I architect, through the 2026-08-31 execution brief that identifies these two
  operations as correctly protected live routes and requires a deliberate reviewed mirror change.
- Mover: Codex Task I lane on `codex/debt-i-runtime-authorization`, commit `05da4ea9e`.
- Review constraint honored: no expectation was generated from the Router or OpenAPI.

The eight pre-review literals were retained unchanged:

1. `POST /api/v1/control/data/ingest` -> `acquisition_approval`
2. `POST /api/v1/control/data/promotion/{promotion_id}/approve` -> `promotion`
3. `POST /api/v1/control/data/promotion/{promotion_id}/reject` -> `promotion`
4. `POST /api/v1/control/decision-validity/events` -> `publication`
5. `POST /api/v1/control/decision-validity/epoch-batches` -> `publication`
6. `POST /api/v1/control/runs/{run_id}/reissue` -> `revocation`
7. `POST /api/v1/runs/{run_id}/production-approval` -> `production_approval`
8. `POST /api/v1/runs/{run_id}/human-decisions` -> `human_decision`

The reviewed proposal added:

9. `POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request` ->
   `acquisition_approval`
10. `POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute` ->
    `acquisition_approval`

The post-review mirror therefore has ten entries. Reporting it as eight after adding the two
required operations would preserve the stale denominator rather than close it.

## DS17 environment measurement

Both commands invoked `ConfidenceLedgerRiskSpendProjectionService(repository_root).get()` and then
`_confidence_ledger_risk_spend_example()` in this linked worktree.

- Explicit root:
  `POLISYOS_GOVERNED_ARTIFACT_ROOT="$PWD" uv run python -c '<exact projection and example>'`
  — exit 0. Configured root and resolved root were both the linked worktree's product root;
  availability was `available`, projection id was `confidence-ledger-risk-spend`, and status was
  `not_promoted`.
- Unset root:
  `env -u POLISYOS_GOVERNED_ARTIFACT_ROOT uv run python -c '<exact projection and example>'`
  — exit 0. Module-derived root resolved to the same linked worktree product root; availability,
  projection id, and status were identical.

The defect was not reproduced: DS17 is owner-admitted in both environments. The conditional repair
for an environment-dependent bare `ValueError` was therefore not activated, and
`src/polisyos/runtime/http/openapi_contract.py` remains unchanged.

## Final verification and inherited red

- Exact Router/OpenAPI equality node: exit 0.
- Complete two-file authz handoff wave: exit 0.
- Four truthfulness consumer files: exit 0, 78 passed; normalized exact shim grep: exit 0,
  output `0`.
- Ruff over the changed Python paths: exit 0.
- Bound debt-ledger reconciliation:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check`
  — exit 1 with exactly 18 blocking `closure_signal_identity_unresolvable` findings and exactly 18
  count/exit disagreements. Input-unresolvable, selects-nothing, collection-failed,
  collection-host-unknown, and AST-collection-disagreement counts are all zero. This is the supplied
  inherited state; the blocker set did not grow.
- Bound docs-lifecycle reconciliation:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py`
  — exit 1 with exactly six inherited findings: two active-plan metadata findings and four
  stale-path findings outside this lane. This journal authors no seventh finding.

## Register closure dossier

Arithmetic: **3 rows = 3 closed + 0 blocked + 0 open**.

### `runtime-authorization-denominator-reconciliation` — closed

- Verdict: `closed`.
- Deciding command and exit code:
  `POLISYOS_GOVERNED_ARTIFACT_ROOT="$PWD" uv run pytest tests/unit/runtime/http/test_runtime_step_up_authz.py::test_router_and_openapi_high_stakes_denominators_agree -q`
  — exit 0. The handoff command
  `POLISYOS_GOVERNED_ARTIFACT_ROOT="$PWD" uv run pytest tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_step_up_authz.py -q`
  also exits 0.
- Delivery: commit `05da4ea9e` writes the exact invariant, keeps the reviewed mirror independent,
  adds the two reviewed DS15 entries, updates the three-input production-approval fixtures, and
  replaces contradictory/scalar-pinned expectations with actual status and property assertions.
- Task B handoff: `decision-validity-fixed-temp-concurrency` may re-point its third conjunct to the
  two-file handoff command above; this row is the concrete landing it was blocked on.
- Exact append-only prose:
  “2026-08-31 Task I — **closed**. A complete live census derives ten Router step-up operations and
  ten OpenAPI step-up operations, with equal method/path/class mappings before repair. The new exact
  semantic test directly asserts that equality before either projection is compared with the
  deliberately hand-authored review mirror. The mirror retains its eight reviewed literals and adds
  the two DS15 acquisition-route operations identified by the architect's brief, so its final
  denominator is ten and is not generated from either live projection. The production-approval
  fixtures now supply the gate's three bound inputs, stale scorecard-path outcomes assert the
  current fail-closed producer diagnostic, and the complete two-file authz wave exits 0. Task B's
  `decision-validity-fixed-temp-concurrency` third conjunct is unblocked by commit `05da4ea9e`.”

### `ds17-openapi-example-source-admission` — closed

- Verdict: `closed`.
- Deciding commands and exit codes: the explicit-root projection/example command exits 0; the same
  projection/example command with `POLISYOS_GOVERNED_ARTIFACT_ROOT` unset exits 0. Both return an
  `AvailableConfidenceLedgerRiskSpendPacket` and the same `available` / `not_promoted` projection.
- Delivery: measurement-only closure; no runtime contract, generated schema, client, or
  `openapi_contract.py` edit.
- Exact append-only prose:
  “2026-08-31 Task I — **closed by executed admission measurement**. In the linked worktree, both an
  explicit governed-artifact root and the unset module-derived root resolve to the product root.
  `ConfidenceLedgerRiskSpendProjectionService.get()` returns an available owner-admitted packet in
  both cases, and the real DS17 OpenAPI example builds with projection id
  `confidence-ledger-risk-spend` and status `not_promoted`; both commands exit 0. The source is not
  environment-dependent and is not missing owner admission, so no diagnostic, schema, client, or
  runtime source change is warranted.”

### `core-observability-truthfulness-shim-residual` — closed

- Verdict: `closed`.
- Deciding command and exit code:
  `git grep -c 'core.observability.truthfulness' -- src/ tools/ tests/ | awk -F: '{total += $NF} END {print total + 0}'`
  — exit 0, output `0`. The native unnormalized `git grep -c` has no output and exits 1, which is
  Git's zero-match status rather than a failed closure. The four focused consumer files run 78 tests
  and exit 0; the value-gate projector refusal helper returns three `value_refused` proofs and exits
  0.
- Delivery: commit `1bee71f93` redirects the one same-package production consumer, one validation
  tool, and four test consumers to `polisyos.ir.analytics`, then deletes the compatibility module.
- Exact append-only prose:
  “2026-08-31 Task I — **closed**. The complete pre-change Python census over `src/`, `tools/`, and
  `tests/` found eight compatibility import statements / 22 aliases / six files across 5,520 `.py`
  files. All six consumers now import the canonical `polisyos.ir.analytics` facade and the deprecated
  Core truthfulness module is deleted. The complete post-change census walks 5,519 `.py` files and
  finds zero statements / zero aliases / zero files; normalized exact grep outputs zero, 78 focused
  consumer tests pass, and the repository validation helper executes through the canonical facade.
  The compatibility residual is fully strangled by commit `1bee71f93`.”
