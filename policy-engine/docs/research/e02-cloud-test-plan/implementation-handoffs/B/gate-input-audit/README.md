# B gate input audit

This packet audits gate configuration and resource conflicts. It does not run
the gates, accept the combined product, or replace a finding discriminator.
The canonical factory source is pinned in `uncapped_constituents.py`; every
factory and the shared resolver must still have those exact bytes in the target
checkout. The runner observes the actual canonical `main` functions with their
`run_command` callbacks intercepted. It suppresses success prose during planning.

`workspace verify` forces six numerical thread variables to `1` for backend
pytest. Its parser has no option to omit that overlay. `ci-parity` launches a
new verify child, so changing only a parent module or ambient thread environment
does not remove it. The cloud HANDOFF instruction forbids artificial numerical
caps. The canonical capped CLI profile therefore remains unrun/incompatible in
this cloud task; any future uncapped execution is recorded separately.

The runner expands that nested verify into all its constituents, preserves every
argv, cwd, assertion, selector and non-numerical environment value, and removes
only `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` and `BLIS_NUM_THREADS` from each
child environment. It imposes no worker or CPU quota. `--execute` is opt-in and
requires the actual current HEAD to equal `--expected-source`; execution retains
the canonical fail-fast ordering. Planning has no gate outcome.

Use the shared venv executable without resolving its symlink to the base Python.
Put the admitted uv 0.9.21 binary first in PATH. The runner verifies that this
binary is the canonical resolver's first matching candidate. From any cwd:

```bash
PATH="/workspace/e02-B-current-coordination/.polisyos/e02-B-current/tools/uv-0.9.21/bin:$PATH" \
/workspace/polisyos/policy-engine/.venv/bin/python \
  /workspace/e02-B-current-cas-generation/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/gate-input-audit/uncapped_constituents.py \
  --product-root /workspace/e02-B-current-coordination/policy-engine \
  --uv /workspace/e02-B-current-coordination/.polisyos/e02-B-current/tools/uv-0.9.21/bin/uv \
  --suite verify -- --backend-only
```

For the complete parity profile, use `--suite ci-parity -- --skip-browser`.
The parser also retains the legitimate existing `--pytest-workers auto` option
or `POLISYOS_PYTEST_WORKERS=auto` environment choice. That choice splits fast
non-benchmark and benchmark pytest commands and must be bound as its own actual
profile; it does not remove the six numerical caps from the canonical CLI.

The runner does not provision dependencies, inject `UV_NO_SYNC`, choose extra
skip flags, rewrite canonical code, or isolate output paths. Before executing,
the root must freeze governed writers and bind an admitted dependency profile.
Default `uv run` may reconcile the shared symlinked `.venv`; any no-sync/private
environment choice is a separately recorded provisioning decision. Isolating
pytest caches, basetemp or frontend outputs is likewise an explicit input change.
Only identical output files, mutable fixtures/DBs, ports or environment writers
require serialization; a shared parent directory alone does not.

`snapshot.py --root /workspace/e02-B-current-coordination` walks the complete
tracked Git tree and canonical manifest's declared selector set, and observes named local
locators and native Trash availability. It neither collects pytest nor discovers
the complete dynamic gate read set. P41 inherited-red attribution still requires
the exact literal slice-base replay and zero intersection with the actual full
gate input closure. Changed source/tests/docs cannot be declared disjoint on the
basis of a baseline summary or historical selector map.

The illustrative final named-suite command in verification-and-closeout reads
`coverage.json` bundle `test_paths`, but the current coverage schema carries
criterion-card references instead. That exact illustrative command cannot
collect tests. The census reads the canonical `bundle_manifest.json` selectors
and records the schema mismatch; repairing or admitting a new final command is
the shared document/verification owner's decision, not a B source edit.
