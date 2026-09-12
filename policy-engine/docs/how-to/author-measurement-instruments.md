# Authoring repository measurement instruments

Owners: team-architecture and team-devx; each instrument retains its existing semantic owner.

An absence verdict is any result a reader can use as “missing”, “no owner”,
“uninvoked”, “not exercised”, “zero findings”, or equivalent. This rule applies
by behavior, including new instruments; the measurement-plane census is an
inventory, not an exemption list.

## Required output contract

Every instrument that can report absence must print the inputs it actually read
alongside the verdict, in every supported output format. Record successful reads,
failed attempts, selectors, exclusions and the enumerated denominator. Bind
content when the claim depends on its identity. A declared path or import is not
a read receipt. A parser reading bytes does not establish that it interpreted
every section in those bytes.

Emit every relevant unread boundary as a named `unresolved_by_construction`
class, with the property left undecided. Keep measured absence distinct from
unreadable input, unresolved runtime dispatch, unsupported syntax and unselected
authority documents. An unreadable member is ambiguous, never an empty member.
A complete verdict over admitted inputs may coexist with incomplete selection;
report both. If the deciding run is incomplete, report `UNRUN` and label any
findings partial coverage. Preserve the instrument's original failure predicate.

For Python tools, compose `tools.lib.fs.measure_file_reads` with the measured
read functions where appropriate. Its receipt covers those explicit operations
only; imports, Git, subprocess reads and services need their own receipts or a
named limitation. The collector is consumed by the registered debt-ledger check
and the existing architecture-owned standalone command
`python architecture/atlas_surfaces/check_atlas_enforcement.py --check`.
Atlas retains that existing entrypoint; duplicating its dispatch is outside this
repair. The collector is internal to these callers and has no independent command. The reference
for static/runtime boundaries is
`src/polisyos/runtime/quality/production_invocation.py`.

## Acceptance and review

Before implementation name the non-test caller and registered command, or explain
why the mechanism is internal. Use ASTs for definitions, calls and duplicates.
Enumerate the complete source set and reconcile it independently. State the
counterexample before each search; run its case-insensitive form too. Read a
cited authority through its operational boundary and honor `may_not_use_for`.

Exercise the actual caller with evidence inside its selector, evidence only
outside it, an unreadable member, and a changed or absent input. The receipt
must change with the actual read set and retain the named undecided class when
outside evidence is present. Remove the original guarded property while keeping
receipt fields and markers: the original failure must still occur. An assertion
that merely checks receipt field names cannot admit the instrument.

These semantic tests and author review enforce the rule on additions and touched
verdicts. No source-string linter can prove arbitrary programs disclose every
input. Historical outputs awaiting migration remain bounded research backlog
MP-B1 in the measurement-plane completion journal; do not certify them by
inventory membership. The census distinguishes input disclosure in one output
mode from this all-format contract.

## Register table consumers

Never split a register row on a literal pipe and then trust column indexes.
Tokenize first with `polisyos.common.markdown.split_markdown_table_row` or its
browser counterpart `features/trust/domain/markdown.ts`, preserving code spans,
escapes, empty cells and source text. Column roles and authority checks remain
with their existing owners. Both implementations replay the same adversarial
vectors; sibling consumer tests exercise real admission and rejection.

The deliberate pipe-containing register row stays intact. The ledger's existing
status recovery continues to report `register_status_column_shifted`; preserving
that recovery is not permission for another consumer to use raw split indexes.
Regenerate derived artifacts through their owner only. A correct parse causing
generated drift is a real failure, never an exception to the drift check.
