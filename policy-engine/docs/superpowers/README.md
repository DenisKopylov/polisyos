# Implementation decisions and evidence

These records help teams plan and review repository work. Read each record at the source cut it
names. Directory placement and a committed plan do not certify implementation, acceptance, or
closure.

## Choose the record by its role

- [Specifications](specs/README.md) define a proposed design, owners, protected boundaries, and
  falsifiers before source changes. They are decision inputs; use the named owner decision to learn
  whether the proposal was admitted.
- [Execution plans](plans/README.md) sequence work against a design. They are not execution
  receipts, and the `plans` directory does not mean that every plan is still active.
- [Journals](journals/README.md) record measured outcomes, deciding commands, source identity, and
  limitations. A journal is evidence only for its cited source, inputs, environment, and scope.
- [Research notes](research) hold analysis and open questions, not runtime authority.
- [Timing evidence](timing-evidence/README.md) is a salvaged historical record. It is not a live
  timing stream, and its README names source data that did not survive.

For the E02 research evidence route, use the [research index](../research/README.md) and the
[E02 documentation snapshot](../reference/e02-documentation-snapshot.md). They distinguish owner
proposals from source-bound receipts and historical G decisions. E02 and E02-R2 have separate
assignments and status records.

## Status and evidence boundaries

Read the owner’s latest source-bound handoff and its associated journal or receipt before treating
an older plan statement as current. Preserve append-only corrections. Do not derive a status from a
directory name, a plan's presence, a selected test pass, an exit code, or a candidate label. The
claim must remain limited to what the owner, source identity, complete input denominator, and
deciding output establish.

Large outputs that a reader cannot recompute belong in ignored raw storage and are cited by path
and hash. Tracked source should be cited by `path@sha`; do not copy derived inventories or use a
hash-only locator as if it contained absent source bytes.

Owning entrypoint: `CONTRIBUTING.md`.
