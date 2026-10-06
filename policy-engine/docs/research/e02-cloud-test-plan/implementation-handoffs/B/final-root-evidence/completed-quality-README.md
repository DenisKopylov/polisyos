# Completed quality gates on the final B root

The E02 root orchestrator calls `run_completed_quality.py` after freezing an exact
clean, attached `/workspace/e02-B-current-coordination` SHA. This research
instrument is internal; it adds no production CLI or native test selector.

```sh
/workspace/polisyos/policy-engine/.venv/bin/python \
  /workspace/e02-B-current-coordination/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/final-root-evidence/run_completed_quality.py \
  --sha ACTUAL_FINAL_40_HEX_SHA --gate ruff \
  --scratch /tmp/e02-B-completed-quality-ACTUAL_FINAL_SHA-ruff
```

Use one unused absolute scratch directory for each gate. The eight gate choices
are `ruff`, `format`, `mypy`, `architecture`, `runtime-api`,
`production-invocation`, `verify-uncapped`, and `parity-uncapped`. Profiles and
stock wait4 stdout/wrappers use exclusive
`.polisyos/e02-B-current/raw/review/completed-final-GATE-SHA12*` paths. Reusing a
profile, capture destination, or scratch is refused. Preserve incomplete and
failed attempts; use a new frozen candidate for a new deciding namespace.

Ruff and format receive every present changed `.py` and `.pyi` in the full
repository diff from published `198076863e143dea9f89f02734b13d50dae3eed5`.
Research, test and source files are included. The complete tracked diff and the
deleted Python filenames are disclosed separately. An absent candidate file
cannot be passed to Ruff. The launcher binds every selected file's actual bytes
to its candidate Git blob and refuses a vacuous Python denominator.

Mypy checks all twelve declared canonical targets: ledger/middleware,
core response/settlement/traced client, upper gateway/cache/enforcer,
method artifacts parts/chain, component composer, and synchronous engine
executor. It uses the repository configuration, actual stubs/plugins,
`--follow-imports=silent` and a fresh scratch cache. The complete tracked stub
inventory is byte-bound; this inventory does not claim an observed import graph.
No skipped-import or Any waiver is added.

Architecture, runtime API and production-invocation keep stock gate argv.
Production-invocation uses the published base and an unused full JSON receipt
in scratch; its grade is static diagnosis. Uncapped verify/parity reuse the
existing complete canonical-constituent projection and stock seven-field
installed-wheel/private-PostgreSQL input admission. Supply the final wheel
profile in `E02_LA057_COHORT_INPUT_FILE`, the private owner-only DSN path in
`E02_B38_POSTGRES_DSN_FILE`, and the actual driver directory in
`E02_B38_POSTGRES_DRIVER_ROOT`. Public profiles omit credential values. Verify
and parity share last-mile artifacts and the pnpm lock, so serialize those two
actual conflicting fixtures. Other ready gates have no artificial quotas.

All six ambient numeric thread caps are removed. The only coverage projection
omits the existing numeric Vitest worker cap and preserves its successful
coverage ratchet. No assertions, selectors or doctor/docs constituents are
removed. Canonical factory drift is refused by the existing projection.

The profile is written before execution with state `UNRUN`. Only the actual
stock capture wrapper provides execution/setup/exit status and complete stdout.
The launcher reconciles source/tree/argv/status and final cleanliness after
capture. It does not classify native cases, certify external authority, or close
findings from process exit. Gate-owned import, service and authority boundaries
remain named limitations. The supplied dependency environment is retained;
public profiles expose declared environment values and inherited key names,
while secret values stay private.

Preparation and source review establish no future gate result. Final-root gates
remain `UNRUN` until the caller supplies the settled SHA and fresh inputs.
