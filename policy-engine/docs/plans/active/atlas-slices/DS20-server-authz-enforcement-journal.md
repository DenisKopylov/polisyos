# Atlas DS20 Server Authorization Enforcement Journal

## 2026-07-18 — Isolation and baseline

### Worktree and base

- Worktree: `/Users/deniskopylov/polisyos/.worktrees/atlas-ds20`
- Branch: `codex/atlas-ds20-server-authz`
- Base/main at creation: `d5f83a26b1815ddc8f3156aafc87d8d89ba97157`
- Initial `git log main --oneline -3`:
  - `d5f83a26b chore: ignore pnpm store and apps build outputs`
  - `71f438ad5 docs: Atlas plan — DS3 closed & merged; debt table extended`
  - `e451cec56 merge: land Atlas DS3`
- Main checkout was clean. `.worktrees/` is ignored.

### Required reading completed in order

1. Revision-3 preamble and doctrine in `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`.
2. DS20 section.
3. DS5 section and its downstream vocabulary/audience obligations.
4. Phase-A synthesis DS4/DS5 authorization lines PI-07 through PI-10.
5. Surface constitution Law 9 and Law 11 enforcement halves.
6. DS1 authorization hotspot and seeded negatives N009 through N013.
7. Policy Design Case failure/repair register before design.

### Parallel-lane collision check

The active GY-N13b branch/worktree was compared with current `main`. Its current committed and uncommitted changes are in fabric/runtime-quality/test areas and do not touch `src/polisyos/runtime/http/**`. DS3 is already in the base. There is no genuine HTTP overlap at plan time. This check must be repeated before implementation commits and closeout; any later real overlap is a stop condition.

`git merge-tree "$(git merge-base HEAD main)" HEAD main` produced no conflict output at the pre-plan-commit checkpoint.

### Live unsafe-operation denominator

Introspection of `create_runtime_api_app()` produced exactly 29 unsafe routes:

- POST: 29
- PUT: 0
- PATCH: 0
- DELETE: 0

The full ordered denominator, permission mapping, step-up mapping, and exact parameterized deny-test IDs are recorded in the implementation plan. DS3's newly merged governed-projection/channel-contract/export-replay routes are GET-only.

### Toolchain baseline

Bootstrap invocation:

```bash
python3 -m tools.cli workspace bootstrap \
  --profile runtime \
  --skip-frontend \
  --skip-playwright \
  --skip-hooks \
  --no-install-uv
```

It created the local `.venv`, then the bootstrap's direct-file doctor subprocess failed with inherited `ModuleNotFoundError: No module named 'tools'`. The supported module invocation passed:

```bash
python3 -m tools.cli workspace doctor --skip-playwright
```

Pinned pnpm dependencies were installed with:

```bash
corepack pnpm install --frozen-lockfile --ignore-scripts
```

The two generation/canonicalization tests that initially lacked Prettier then passed.

Canonical runtime contract baseline:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml \
  polisyos-tools runtime check-runtime-api-contract
```

Result: green, `Runtime API contract check passed.`

Broad HTTP Ruff baseline:

```bash
.venv/bin/ruff check src/polisyos/runtime/http tests/unit/runtime/http
```

Result: 57 inherited diagnostics. DS20 will use changed-file Ruff and verify that it introduces zero new diagnostics.

Scoped HTTP pytest baseline has six inherited failures:

1. `tests/unit/runtime/http/test_architecture_boundaries.py::test_runtime_never_imports_concrete_cas_write_implementation`
2. `tests/unit/runtime/http/test_debug_api.py::test_feedback_endpoint_returns_feedback_loop`
3. `tests/unit/runtime/http/test_debug_api.py::test_equilibria_endpoint_returns_multiplicity_report`
4. `tests/unit/runtime/http/test_runs_api.py::test_evaluate_feedback_endpoint_persists_monitoring_report`
5. `tests/unit/runtime/http/test_runs_api.py::test_reissue_endpoint_fails_closed_without_durable_control_plane`
6. `tests/unit/runtime/http/test_runtime_api_write_path_hardening.py::test_feedback_evaluate_mutation_is_audited`

The first is an out-of-fence `runtime/quality` architecture debt. The remaining five are manifestations of the registered control-plane fixture-drift baseline. A focused rerun reproduced all six failures before any tracked edit. DS20 must not fix, hide, or expand them.

### Vocabulary finding

The old server `_ROLE_PERMISSIONS` contains 12 values; the read-only dashboard `PERMISSION_KEYS` contains 15. Its unmatched literals are:

- `collaboration.comment`
- `collaboration.share`
- `collaboration.view`

DS20 makes the server vocabulary authoritative but does not launder these client-only literals into server authority. They remain a DS5 lint/strangle finding; DS20 does not edit `apps/**`. The generated package carries the server enum for DS4/DS5 to consume.

### Fence/register finding

The authoritative DS19 disposition register is `architecture/atlas_surfaces/frontend-disposition-register.json`, outside the explicit DS20 writable fence. DS20 will record proposed N009-N013/auth-row lifecycle changes in its closure artifact and hand them to the DS19 owner rather than violating the fence. The 29 frontend operation dispositions themselves remain owned by their existing destination slices; DS20 changes their orthogonal server-authz state and therefore does not rewrite their wire/rebind/retire disposition.

### Initial capability classification

- Action-permission contract: `producer_missing`
- Route-to-policy resource binding: `bridge_missing`
- Mutating route enforcement: `consumer_missing`
- Per-operation deny proof: `verification_missing`, `semantic_test_missing`
- OpenAPI/client vocabulary: `surface_missing`
- DS9 approval UX/mandate/dissent work: explicitly downstream and not part of the DS20 completion claim

## 2026-07-18 — Pre-commit specification review

A read-only review caught and corrected the following before the first commit:

- Restored the canonical DS1 mapping: N009 generic action authorization, N010 fail-open UI identity, N011 production fixture identity, N012 production approval integrity, N013 step-up.
- Kept the three collaboration literals as DS5 findings rather than promoting deleted client vocabulary into server authority.
- Added explicit per-permission role grants, typed body/batch resource binding with ownership lookup and body replay, external IdP step-up producer/transport/config, concurrent replay proof, review-WebSocket fixture coverage, and a typed audit-event handoff.
- Added HTTP-layer production-approval principal/scorecard/signature negatives while retaining honest DS9 `artifact_missing`/`consumer_missing` labels for exposure receipts and final server signing.
- Corrected the DS19 register location and limited the handoff to N009-N013/auth rows rather than rewriting orthogonal operation dispositions.
- Corrected Python support to 3.14.x; added the Runtime HTTP README obligation and an out-of-fence release/public-surface handoff.

## 2026-07-18 — Post-plan live ownership API correction

Task-4 read-only exploration found that the committed plan overclaimed generic tenant ownership for identifiers that today's container cannot verify. Trustworthy ownership resolution currently exists for runs and content-backed/run-linked CAS artifacts. Promotion candidates are globally stored without a tenant field; basin/continuation IDs are logical target strings; lineage ownership is resolvable only for supported artifact/run/scenario forms; fabric child selectors and several analytical IDs are not ownership facts.

The plan is corrected before source implementation under P32:

- Binding source and binding authority are separate typed values.
- Only server-resolved run/artifact facts may say `ownership_verified`.
- Resolved-but-unscoped selectors retain `content_resolved_unscoped`; caller tenant is never substituted as owner.
- New logical targets are candidate slots, not existing/conflict-checked objects.
- Request composites are exact body/selector bindings, not authority claims.
- Unknown owned IDs and unsupported lineage forms deny; supported limited bindings remain visibly limited to OPA, the action dependency, and audit.

This preserves the required pre-OPA resource binding without manufacturing evidence or making legitimate create/optional request modes impossible.
