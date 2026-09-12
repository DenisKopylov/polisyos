# Measurement plane completion journal

Status: Stage 1 research in progress; no mechanism changed.

Lane: `codex/measurement-plane`, base `307dabcb4`. Local ordinary git; no push,
prune, guardrails sync, register or ledger edits. Root serializes git and the
four shared instruments. Row 1 surveys alone; then rows 2+3 and 4+5 may overlap.

Name admission: `git worktree list | grep measurement-plane` exited 1 with no
output; `git rev-parse --verify codex/measurement-plane` exited 128 (`fatal:
Needed a single revision`). Target path did not exist. The requested
`git worktree add /Users/deniskopylov/polisyos/.worktrees/measurement-plane -b
codex/measurement-plane 307dabcb4` completed; `git status -sb` read back
`## codex/measurement-plane` with a clean tree.

Evidence policy: complete deciding output and removal probes retained; large
outputs in gitignored `**/raw/`, cited by path and SHA-256. Tracked inputs are
cited as path@commit. Search predicates must expose their counterexample and
run case-insensitively. ASTs establish definitions and calls. Every set-level
count names its full path/file-type denominator and independent cross-check.
Unreadable members remain ambiguous.

## Baseline receipts

The first guardrail invocation failed because root wrote the Row 1 decision while
its output-footprint probe was active. This is root's scheduling error, not
inherited product debt. The frozen rerun passed with zero findings (420.41 s).
Serialize the repository filesystem snapshot for later guardrails: no tracked
writes during its run. Both invocations preserved their complete output.

The ledger generated-artifact check passed with `register_ids=260`, no blocking
findings, and exactly two `register_status_column_shifted` informational findings:
`extraction-ask-offers-six-of-ten-evidence-classes` and the retained pipe-regression
row. Its full run took 1029.57 s. This receipt is a check result, not evidence
about the source tree from the register or ledger prose.

The invocation baseline passed through `uv run python -m pytest -q
tests/unit/runtime/quality/test_production_invocation.py` (19 collected items,
10.02 s). Bare `uv run pytest` had used `/opt/homebrew/bin/pytest` because the
cloned installed packages lacked the console script; that distinct environment
failed the CLI import test. Use the isolation-local module launcher.
Atlas scope baseline: `uv run python -m pytest -q
architecture/atlas_surfaces/test_atlas_enforcement.py -k scope_obligations`,
5 selected items passed (3.63 s).

Environment: `corepack pnpm install --frozen-lockfile` completed. Offline uv cache
missed compiled wheels, so installed packages were copied by APFS clone from the
local root environment, then the worktree was reconciled with
`uv sync --offline --frozen --no-build-isolation --extra lint --extra test
--extra runtime`. Missing build tools were installed in the isolated environment
only; no manifest/lock changed. `tools` and `polisyos` resolve inside this lane.

Complete outputs (SHA-256; raw paths are intentionally gitignored):

- `docs/superpowers/journals/measurement-plane/baseline/raw/atlas-scope-tests.log@813f2fe8a693a17133d234e599e457872dfc6e8b16e6b4f1c60232fd53b34773`
- `docs/superpowers/journals/measurement-plane/baseline/raw/debt-ledger.log@653c081aa81153812a2faa4e5aead674f4c36be701a63f60c33bb622b6f650e3`
- `docs/superpowers/journals/measurement-plane/baseline/raw/guardrails-frozen.log@04f48c422c506201260004cd8f2267975ae5593baac6ff22e2c832e561e57fec`
- `docs/superpowers/journals/measurement-plane/baseline/raw/guardrails.log@bfad605a96c50a7439e3271dedaf306acb4975b14c0b3cc715be46309e2df178`
- `docs/superpowers/journals/measurement-plane/baseline/raw/production-invocation-module-tests.log@cbf54da1fbbd65626318b61caad2a79d7f05fc019a52f2a4bfb72a9d206ae497`
- `docs/superpowers/journals/measurement-plane/baseline/raw/production-invocation-tests.log@d144c9df99e563f586fb30b8f2a3cace1ac68b3b1765a1ffe1b969eb9dde27be`
