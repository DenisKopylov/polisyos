# Historical Plans

`docs/plans/archive/` contains completed, superseded, or historical planning
documents retained as evidence.

Plans move here only after durable behavior has a current home:

- decisions in `docs/adr/`;
- stable facts in `docs/reference/`;
- procedures in `docs/how-to/` or `docs/runbooks/`;
- machine-readable contracts in `architecture/**` or `schemas/**`.

New archive entries should preserve the original filename when moving a legacy
plan. New closeout archives should use `YYYY-MM-DD-<slug>.md`, include status
and owner, and link the ADR/reference/runbook surface that supersedes the plan.

For a bounded closeout, preserve the plan's historical status and name the
scope and remaining owner obligations. A compatibility pointer keeps old-path
navigation working, but it cannot stand in for a reader that depends on the
original bytes. Keep source-bound receipts unchanged and use the existing
redirect metadata and sunset contract for any temporary pointer.

## 2026-10-14 disposition

- [Documentation refresh against E02](2026-10-14-documentation-refresh-e02.md):
  this session's completed execution plan, with a separate
  [verification closeout](../../archive/reports/2026-10-14-documentation-refresh-e02.md).
  The three legacy moves below preserve their baseline source bytes.

- [Documentation SOTA](DOCUMENTATION_SOTA_PLAN.md): historical D0–D6 program;
  current source maps and verification scope are in the documentation handbook.
- [Data Forge Phase 0](DATA_FORGE_CUTOVER_READINESS.md): bounded cutover sign-off,
  with its named advisory benchmark failures retained.
- [G5 conversion](G5-first-proving-ground-conversion.md): bounded plumbing
  closeout with the recorded `unchanged_blocker` / `unsupported` result.

The three legacy copies preserve their source bytes, including historical front matter.
Their old paths are compatibility pointers; archive placement grants no current
runtime authority. See the [disposition](../documentation-refresh-disposition-20261014.md).
