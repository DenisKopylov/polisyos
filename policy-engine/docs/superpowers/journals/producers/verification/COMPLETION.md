# Producers verification completion journal

Lane base: `a534024ee28dfd9ac4fd21be1ff769b253722d8e`.
Attached branch: `codex/producers-verification`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/producers-verification`.

## Execution contract

The exact requested names were checked before work; neither appeared in the worktree
list and the branch ref did not exist. Ordinary `git worktree add` succeeded at the
requested base. Root serializes commits and shared-file edits. No changes are permitted
to DEBT-REGISTER.md or LEDGER.md; they supply row requirements only and are never evidence
for tree claims. At most three workstreams run concurrently; Foundry research follows
the initial Claim Ledger, global-index and Atlas research. No push or history rewrite.

Stage 1 records one decision per row under docs/superpowers/specs and commits/readbacks
those decisions before source/test changes. Stage 2 verifies existing mechanisms before
repair, with exact named test nodes, production-path negatives and unchanged-negative
removal probes. No directory-wide, backend-wide or CI-parity suites. The shared browser
ports 8017/5177 and browser fixture root are serialized. Individual temporary CAS roots
are isolated. Complete gate output is retained under verification/raw, ignored by the
producers/.gitignore included in the first lane commit. Gate statuses and content hashes
are recorded below after execution; no successful historical handback is a fresh receipt.

## Research measurements

Independent AST census at the lane base: 2,654 tracked src/**/*.py files, identical Git
index and pinned-tree path sets, 2,654 parses, no parse errors. It counts 37,014 function
definitions including 879 AsyncFunctionDef nodes, and 367,214 Call nodes. Path-list SHA-256:
`b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.
Output: `raw/independent-census.log` (hash recorded at closeout). Delivered vocabulary
was discovered by tracing actual persistence readers and callers before querying the
complete set. The source-derived production_invocation module at the base supplies the
separate complete caller audit. Static callback/receiver limitations will be reconciled
against real HTTP/lifecycle execution, never equated with runtime authority.

## Environment

Offline `uv sync --offline --frozen --extra lint --extra test --extra runtime` returned 1:
the pinned jaxlib wheel was absent from the cache. The online frozen invocation then
returned 0 and provisioned this worktree's own Python 3.14.3 environment; no dependency
or lockfile was changed. `corepack pnpm install --frozen-lockfile` returned 0 before any
TypeScript scanner/test. These are setup outcomes, not product gate verdicts. Complete
outputs remain in raw/environment-sync.log, raw/environment-online-sync.log and
raw/pnpm-install.log. The ordinary test command will be `uv run pytest` with named nodes.

## Row dispositions

Pending fresh Stage 2 verification; the decision documents distinguish existing mechanisms
from missing appointments, coverage limits and missing authority capabilities. Completion
will be recorded per row only after reading branch artifacts and actual gate results.
