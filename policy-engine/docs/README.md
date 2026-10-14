# PolicyOS Docs

[The handbook](index.md) is the reader entrypoint. This repository index also
routes execution plans, research and historical evidence that are deliberately
separate from the published handbook.

## Read the system

- [Architecture](explanation/architecture.md) and
  [end-to-end data flow](explanation/end-to-end-data-flow.md).
- [Current subsystem references](reference/index.md) and
  [contributor task map](reference/contributor-start-here.md).
- [System-design decisions](system-design-decisions/README.md), including the
  identity/custody boundary, north star and Stage 0 ratification.
- [ADR status index](adr/index.md) and [ADRs by topic](adr/by-topic.md).

The implementation maps were inspected at source commit
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14. The
[E02 snapshot](reference/e02-documentation-snapshot.md) explains why ongoing
integration and a historical receipt cannot be treated as current closure.
The system is not functional end to end; tutorial smoke examples and blueprints
retain that limit even when an individual component or documentation check passes.

## Find the right document

| Need | Location |
| --- | --- |
| Learn a flow | [Tutorials](tutorials/index.md) |
| Perform a task | [How-to](how-to/index.md) |
| Look up a contract or owner | [Reference](reference/index.md) |
| Understand responsibilities and tradeoffs | [Explanation](explanation/index.md) |
| Operate or recover | [Runbooks](runbooks/index.md) |
| Read accepted decisions and proposals | [ADRs](adr/README.md), [system-design decisions](system-design-decisions/README.md) |
| Locate current execution or a historical plan | [Plans lifecycle](plans/README.md), [active index](plans/active/README.md), [archive disposition](plans/documentation-refresh-disposition-20261014.md) |
| Find research and E02 evidence owners | [Research map](research/README.md) |
| Read frozen evidence | [Archive lifecycle and entrypoints](archive/README.md) |
| Work on visual identity or compliance records | [Brand](brand/README.md), [accessibility records](compliance/README.md) |

## Maintain the documentation

Follow the [style guide](style-guide.md) and
[verification contract](reference/documentation-verification.md). The
[inventory](reference/documentation-inventory.md) records the measured scope;
the [failure/repair register](reference/policy-design-case-failure-patterns.md)
defines the capability and authority vocabulary.

The [comprehensive maintenance audit](archive/reports/2026-10-14-documentation-maintenance-audit.md)
records the second slice's source audits and verification-tool repairs; its
verdict table distinguishes passing checks, incomplete global gates and the
narrowly reproduced snapshot failure. The earlier
[refresh closeout](archive/reports/2026-10-14-documentation-refresh-e02.md)
records a separate publication boundary and verification wave. Runtime and
E02 closure remain outside both reports.

Stable behavior belongs in authored explanation/reference/procedure pages;
plans and receipts retain their historical authority and explicit scope.
Generated references link to their canonical owners and regeneration commands.
Do not copy their inventories into a second manual source of truth.
