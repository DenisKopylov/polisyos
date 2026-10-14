# Plan lifecycle

This directory holds current execution plans, approved work programs, and
historical plans. A plan is not the final source of truth for architecture,
stable behavior, procedures, or machine-checkable contracts. Those belong in
ADRs, `docs/reference/`, `docs/how-to/` or `docs/runbooks/`, and
`architecture/` or `schemas/` respectively.

Start with the [active-plan index](active/README.md) for owner entrypoints, the
[accepted-plan index](accepted/README.md) for approved program routing, and the
[production backlog index](../backlog/README.md) for current diagnostic queues.
Use the [2026-10-14 disposition](documentation-refresh-disposition-20261014.md)
for the dated inventory and its move proposals. The disposition is a snapshot;
the tracked tree and each owner's current evidence remain authoritative.

## English migration boundary

Repository documentation is authored and maintained in English under the
[documentation language policy](../reference/documentation-language.md). This
2026-10-14 migration defers plans for work that is still executing, including
all E02 and E02-R2 work packages. Revisit their language with the owning team
after closeout or re-baselining; directory placement alone does not establish
whether work is still active.

Historical plans in `archive/` remain unchanged as primary evidence during this
migration. If readers need an English rendering later, label it as a
translation, link it to the preserved source, and record the source revision.
A translation does not create fresh implementation or verification evidence.

## Lifecycle locations

| Location | Use |
| --- | --- |
| `active/` | Execution plans, owner packages, slice plans, and current closeout records. Read each file's status and evidence; folder membership alone does not establish that work is open. |
| `accepted/` | Approved work programs whose execution, verification, or residual work remains current. |
| `archive/` | Historical plans retained for provenance, including bounded completions and plans superseded by a named successor. |
| `docs/archive/reports/` | Final evidence reports, reviews, incidents, and postmortems rather than execution plans. |

Status, closure scope, and runtime readiness are separate facts. A bounded
implementation or cutover may be complete while a downstream capability stays
blocked or unallocated. Preserve that boundary in the closure record and route
remaining work to its current owner. A completion label does not prove a
current runtime gate, and an archive path does not prove production readiness.

When a historical plan still has useful inbound links, an active-path pointer
can retain the canonical archive link and name the current owner or successor.
Keep the original bytes in the archive when source history or a pinned receipt
depends on them. Do not rewrite an immutable receipt merely to update a path.
An old-path pointer preserves navigation and path-existence checks; it does not
replace a consumer that parses the original plan bytes or assigns those bytes
runtime meaning. Keep the compatibility window and removal rationale in the
existing redirect metadata, and distinguish those consumer types in any
move-specific disposition. The review method for one move does not become a
repository-wide archive admission rule.
The repository's [redirect-stub lifecycle contract](../../architecture/policies/directory_contracts.toml)
defines metadata and sunset expectations for redirect README files.

## Front matter and ownership

New execution plans should start from [`TEMPLATE.md`](TEMPLATE.md) and name an
owner, status, creation date, verification date, and stability. When a plan is
closed or superseded, record the bounded scope, the evidence available, any
remaining obligations, and where a successor owns them. Use the vocabulary
already present in the plan's domain rather than inventing a status just to
match its directory.

## Repository placement

1. Active plans link to required ADRs and identify the current owner.
2. Accepted plans link to machine-readable contracts when work changes
   repository topology, imports, schemas, generated artifacts, release policy,
   secrets, observability, or public APIs.
3. Move stable facts and procedures to their canonical documentation surfaces
   as work closes; plans should not become permanent second sources of truth.
4. Keep historical plans in `docs/plans/archive/`; use `docs/archive/` for
   reviewed evidence, reports, frozen specifications, incidents, and
   postmortems.

## Method used for the 2026-10-14 disposition

The linked disposition uses a complete pinned-tree census, then checks the
primary closure evidence and the current state for the bounded candidates it
reviews. Its inbound-reference scan is specific to that dated review. These
steps document how that snapshot was produced; they do not create a new
universal archive-admission gate. A missing finding ID alone is not a reason to
reject a move when a primary record explicitly closes a bounded scope. The
record should still be cited by its actual file, section, and revision, and its
meaning should not be extended to claims it did not test.
