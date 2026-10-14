---
title: Documentation refresh against the E02 source snapshot
status: active
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: draft
---

# Documentation refresh — 2026-10-14

## Scope and source boundary

Refresh authored documentation against source commit
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, the observed tip of
`codex/e02-unified-local-20261009` at commissioning. Work happens on
`codex/docs-refresh-e02-20261014` in a separate existing checkout. E02 integration
continues independently; this refresh cannot close E02 or certify deployment.

The authorized scope is documentation, including its MkDocs navigation fragments
and their generated documentation configuration. Runtime code, tests, schemas,
dependencies, CI workflows and the E02 research/implementation receipt corpus are
read-only. Large structural changes require the user's approval after a concrete
proposal. Ordinary corrections, navigation repairs and evidenced plan archival
are within the requested cleanup.

## Execution and review

Direct agents cover the documentation census, plan disposition, decision
indexes, architecture, data flows, IR/core, Scientist, Foundry, Fabric, Data Forge,
Lex, runtime/API, governance/observation, frontend, operations, developer guides,
verification contracts, E02/research navigation, external documentation practices
and link QA. Each writer owns disjoint named paths. Root owns the handbook and
reference landing pages, publication configuration, integration and commits.
Finished research/writing lanes move to independent review and fresh validation.

Serialized resources: Git index/commits, generated MkDocs configuration, baseline
snapshot creation and documentation build. No shared server, browser, DuckDB or
E02 scratch is used. Source inspection and read-only censuses run in parallel.

## Pattern pass

| Pattern | Existing risk | Correct pattern and acceptance signal |
| --- | --- | --- |
| P01/P02/P03 | Old overview can describe a contract as a working capability or hide consumer boundaries. | Trace actual producer, artifact, bridge and surface; name missing chain labels. |
| P04/P05/P15 | Candidate output or a historical passing receipt can appear authoritative. | Describe exact status/authority constraints; distinguish source inspection from execution. |
| P07/P08 | Current prose can silently inherit old rules or conflate legal, observation and persistence time. | Bind claims to the source pin and owning versions/time roles. |
| P13/P27 | A new documentation system could duplicate existing taxonomy and owners. | Reuse existing tutorial/how-to/reference/explanation, decision and archive trees. |
| P35/P36 | Counts and completion claims can rely on samples or adjacent prose. | Complete-set scripted censuses with denominators; cite primary closeout/finding IDs. |
| P37/P38/P41 | A green checker or a moving-tree observation can masquerade as factual accuracy or baseline evidence. | State each check's actual property, replay baseline from pinned content, retain complete deciding output. |

Source: [failure/repair register](../../reference/policy-design-case-failure-patterns.md).
The refresh claims documentation improvements only. Unverified runtime capability
remains `verification_missing`; discovered incomplete chains retain the owner's
specific `producer_missing`, `bridge_missing`, `surface_missing` or other
registered label. The task does not convert research questions into contracts.

## Acceptance

- Current architecture and subsystem entrypoints explain observed behavior,
  boundaries and unresolved integration, with concrete source/test references.
- Navigation distinguishes ratified decisions, current source maps, procedures,
  active plans and historical evidence.
- Archive moves carry primary completion/supersession evidence and reconciled
  inbound references; unresolved or E02-driving plans stay active.
- Fresh docs checks, style, local links and strict build are recorded with their
  scope and limitations. A passing syntax/link check does not certify prose truth.
- All delivered changes are committed on the documentation branch and read back
  from that branch; the source-code delta is empty.

## Closeout

Pending source freeze, independent review, archive disposition, verification and
branch readback. The closeout receipt will record actual commands, verdicts and
remaining limitations without claiming completion of the parallel E02 work.
