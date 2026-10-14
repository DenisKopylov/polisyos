---
title: Documentation clarity and sustainable verification
status: active
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: evolving
---

# Documentation clarity and sustainable verification

## Authorized scope

The principal authorized a third documentation pass on 2026-10-14, including
documentation tools and their tests. Tutorials are deferred until E02 is
finished. Production implementation and E02's source-bound records remain
read-only. This pass uses the existing directory and branch
`codex/docs-refresh-e02-20261014`; its slice entry is
`47e1e59b569a5b922611f71a7f53fb6320abea4c`. Production explanations retain
their stated source pins, principally `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
Concurrent E02 progress is not imported or certified.

No new worktrees, checkouts, environments, dependency installations, copied
source trees, browser installations or data exports are allowed. At entry,
`df -h .` reported 9.2 GiB available on the workspace filesystem. Existing
Python, Node and documentation dependencies will be reused. New deciding logs
and small fixtures should remain below 32 MiB in aggregate; no large per-file
body or duplicate inventory dumps are needed. Mandatory plan/report/index
companions are outside this mechanism-output budget (P39). The existing site
output may be rebuilt in place once after review.

## Design

Extend existing reader entrypoints and canonical owners. Preserve the existing
publication boundary, directory layout, primary decisions, archived evidence,
ten held source records and tutorial bytes. Do not infer lifecycle from age or
delete duplicate records whose roles and consumers have not been reconciled.

Reader changes clarify purpose, owner routing, source pin, observed flow,
authority boundary, missing bridge and suitable verification. Source changes,
rather than a new date marker, trigger re-review of affected consequential
claims. A desk-based reading walkthrough is not a human usability study.

Two small direct-call instruments address repeatability:

- `tools/quality/validation/check_docs_rendered_links.py` checks the complete
  specified emitted-site file set, local target files and HTML fragments.
  Missing targets fail; unreadable or unsupported deciding inputs retain an
  incomplete verdict. External availability, JavaScript navigation and browser
  rendering stay outside its property. It replaces the need to copy the
  earlier local crawl script into every audit.
- `tools/quality/validation/check_docs_source_bindings.py` checks explicitly
  selected pinned pages' declared source paths against a comparison Git ref.
  Expand declared globs against both trees and compare actual source bytes;
  additions, deletions and changed bytes require review. Missing or ambiguous
  bindings cannot return a clean verdict. Equal bytes establish only equality
  of declared owners, not complete claim coverage or prose truth. No second
  source registry is introduced.

Neither instrument changes production gates, baselines, compatibility policy,
CI workflows, deployment or the existing lifecycle check's unresolved scope.
Use real public callers, negative fixtures and marker-preserving property
removal probes. Mirror tests under `tests/repo_quality/tools/`.

The existing docs gate also needs a bounded dependency correction: changes to
any `architecture/tooling/mkdocs/**` publication fragment must plan its existing
accuracy/freshness and strict-build commands, as `mkdocs.yml` already does.
Preserve early-failure behavior and do not relabel planned children as run.
The canonical vocabulary generator may refresh the single stale bound-source
digest only after complete expected/actual comparison establishes unchanged
terms, IDs, rulings and authority restrictions. Its checker and a corrupted
artifact probe must verify the revision; no production vocabulary is changed.

## Direct ownership

All twenty lanes are direct and reuse this directory. Root serializes Git,
shared generated outputs and the final build. Writers own disjoint paths;
read-only reviews and source inspection may overlap.

| Lane | Owned surface or read-only task |
| --- | --- |
| architecture | Architecture explanation; source-binding instrument and mirrored test after design review |
| data_flows | Existing end-to-end data-flow explanation |
| data_forge | Data Forge index and current-data-paths reference |
| decisions | ADR/accepted-plan routing; existing docs-gate dispatch correction and mirrored tests |
| developer_guides | Contributor Start Here; desk-based reader walkthrough |
| docs_census | Read-only organization, coverage and final preservation reconciliation |
| fabric | Fabric index/explanation and source-qualified lineage gap alignment |
| foundry | Foundry index and causal-engine architecture reference |
| frontend | Current frontend surface map |
| governance | Style guide and ownership reference; independent predicate review |
| ir_core | IR design explanation and existing IR index |
| lex | Lex pipeline procedure and NormPack source README |
| links_audit | Rendered-link instrument and mirrored tests after design review |
| operations | CI/CD and generated-artifact procedures; portable evidence guidance |
| plans_archive | Backlog root routing; primary backlogs remain unchanged |
| quality_contract | Documentation verification contract |
| research_e02 | Read-only crosswalk binding and post-freeze source reconciliation |
| runtime_api | Current request lifecycle reference |
| scientist | Scientist index and current workflow reference |
| sota_research | Advisory documentation-practice research using primary sources |

Root owns landing pages, documentation inventory, this plan, the closeout
report and any necessary publication-source integration. New broad structural
or publication changes need a concrete proposal; routine authorized in-place
clarifications and direct-call tooling proceed within this scope.

## Execution and acceptance

- [ ] Complete the bounded source and reader-path review; reconcile concrete
  omissions and terminology across owners without claiming a whole research
  corpus semantic audit.
- [ ] Reproduce instrument gaps with failing tests, implement the bounded
  mechanisms, and exercise added/removed/changed members, malformed input,
  unavailable reads and property-removal probes through real callers.
- [ ] Review all changed sources before freezing; batch material corrections.
  Record cosmetic debt without restarting the expensive wave.
- [ ] Run changed instrument tests, Ruff, the complete changed authored
  Markdown selection, applicable canonical drift checks and accuracy.
- [ ] Rebuild in place and run the durable emitted-site check against its
  complete output; bind the actual configuration/input and execution results.
- [ ] Run applicable path-aware/lifecycle checks, retaining their exact
  failed/UNRUN outcomes. The second-pass global debts are not silently waived
  or labeled inherited without this slice's P41 proof.
- [ ] Re-read committed branch blobs, source/tutorial/E02/held-record
  preservation and disk consumption; close the bounded plan with a small
  report and explicit unresolved owners.

## Pattern pass

P01/P02/P03/P05/P15 keep partial runtime paths and projections honest.
P07/P08 preserve source pins and distinct revision/verification/evidence times.
P13/P27 avoid another taxonomy, metadata registry or competing source owner.
P29/P31/P32/P35/P37/P38 require actual inputs, complete declared sets and real
property checks; string markers and equality cannot prove semantic freshness.
P40 buckets repeated parser/coverage findings before widening a mechanism or
declaring a measured residual. P41 keeps check provenance separate from the
documentation closeout. Acceptance is clearer routing, reproducible bounded
checks and truthful limitations, never an E02 or publication readiness claim.
