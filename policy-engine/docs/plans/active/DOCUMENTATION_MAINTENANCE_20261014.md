---
title: Comprehensive documentation audit and honest verification tools
status: active
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: draft
---

# Comprehensive documentation audit and honest verification tools

## Agreed change contract

The user approved continued documentation work and repairs to documentation
tools and their tests on 2026-10-14. Production code remains read-only. The
system is **not functional end to end**; tutorials may be explicit blueprints
or bounded smoke examples, but cannot imply a completed policy-analysis,
governance or publication chain.

The slice begins at documentation commit
`c35222b3dcf103338175cf300c5fe9487e6416f3` on
`codex/docs-refresh-e02-20261014`, in
`/Users/deniskopylov/.codex/worktrees/fe13/polisyos`. Production source remains
qualified by `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; concurrent E02 work is
not incorporated or certified. Root owns commits on this existing branch;
same-branch root commits are expected, while unexpected branch/directory
changes require stopping and reporting.

Authorized writes: authored documentation, existing documentation-checking and
rendering tools, their mirrored tests, and canonical generated documentation
outputs. No Python/TS/JS production implementation, runtime schema, dependency
lock, CI workflow, E02 receipt or source-bound research package is changed.
Source package READMEs outside `docs/` receive read-only audit first; root
allocates any subsequent documentation correction after checking its bindings.
Large taxonomy changes and contentious removals require concrete owner review.

After source and binding review, root explicitly assigned documentation-only
corrections to the Fabric, Data Forge and IR package READMEs. Repairs also extend
the existing ADR index and Fabric documentation-inventory generators and their
mirrored tests; canonical outputs are regenerated through their owners.

## Design and execution

Reuse existing Diataxis, decision, research and archive structures. Census the
complete tracked documentation tree and sibling Markdown, then reconcile its
paths with the lanes below; a filename bucket is not a semantic classification.
Group byte-identical blobs only to expose duplication, never to infer shared
authority or lifecycle. Frozen E02/evidence records are audited as documentary
inputs and their navigation may improve; their contents stay unchanged.

Tool fixes extend current callers. Lifecycle reference checks classify actual
inputs before decoding and disclose unread/unresolved boundaries; unsupported
deciding inputs retain a partial/non-green verdict. The Markdown archive-column
consumer uses the existing canonical tokenizer. Accuracy/link checks resolve
actual destinations and the actual MkDocs inclusion set instead of segment-name
proxies. The public-surface renderer may expose existing source-candidate scope,
but its effect-aware resolver and unknown native-export verdicts remain intact.

Tool writers first reproduce the defect, add a failing regression through the
real caller, make the smallest repair, and run positive/adversarial/removal
probes. No synthetic gate or date marker substitutes for substantive evidence.
Documentation writers inspect source/test contracts and explicitly distinguish
that from execution. No live service, provider, database or simulation runs are
needed to claim a documentation correction.

## Direct lane ownership

All lanes are direct; no further delegation. Each lane records its complete
assigned read set, unread boundaries and concrete findings in ignored
`_build/docs-maintenance/raw/`. Root resolves the census's unallocated paths
before claiming comprehensive coverage. Generated pages and primary signed or
source-bound records retain their canonical owner.

The 8dd9336 census exposed 93 further docs Markdown paths and 502 outside-doc
Markdown paths beyond the three explicitly assigned package READMEs. Root
allocated 92 docs paths to their existing lanes and retained the measurement
authoring contract; all 502 outside-doc paths receive read-only review in 14
deterministic batches. The exact allocation is ignored
`_build/docs-maintenance/raw/supplemental-audit-allocation.json`, SHA-256
`10ac3420e81af3249deebe26d2f977b358b5dfaa3f36aafad8fc3fb97ef46dda`.
It assigns work, not semantic coverage; per-path reader receipts establish
the actual methods and unread boundaries. Newly authored routing pages are
included in the final census rather than inferred from this snapshot.

- `docs_census`: complete docs/sibling-Markdown census, coverage reconciliation;
  ignored receipts only.
- `quality_contract`: lifecycle checker, documentary-reference helper and
  mirrored tests; no other writer uses these files.
- `links_audit`: docs accuracy checker and mirrored tests; later whole-source
  and emitted-site link QA. Root owns publication configuration.
- `data_flows`: public-surface renderer in architecture guardrails and its
  public-surface tests; canonical public-surface outputs only.
- `architecture`: explanation Markdown except causal-engine, data-fabric,
  governance-model, observation-contracts and lex-pipeline; historical nested
  runtime-redesign primary records are read-only.
- `ir_core`: `docs/reference/ir/` and `docs/contracts/` authored Markdown.
- `scientist`: `docs/reference/scientist/` authored Markdown.
- `foundry`: `docs/reference/foundry/` and causal-engine explanation.
- `fabric`: Fabric reference, connector Markdown, data-fabric explanation and
  add-data-source how-to.
- `data_forge`: Data Forge reference and data-capability-requirements reference.
- `lex`: Lex reference, lex-pipeline explanation and Lex production runbook.
- `runtime_api`: runtime/API reference and add-runtime-route how-to.
- `governance`: policy-design-case reference family except the root-owned
  failure register; governance/observation explanations.
- `frontend`: frontend reference, brand Markdown and dashboard-client how-to;
  historical audits keep their dated primary findings.
- `operations`: runbooks except Lex, operations reference, local-runtime-state,
  deploy/debug/control-plane/CI/release/rollout how-tos.
- `developer_guides`: tutorials, role onboarding, install and how-to index.
- `decisions`: decision/ADR routing indexes; primary ADRs and ratified decisions
  receive read-only semantic review.
- `plans_archive`: plan/backlog inventory and lifecycle indexes; evidenced moves
  require root reconciliation; this execution plan is root-owned.
- `research_e02`: research/superpowers coverage and routing; E02, journals,
  primary research/specs and bound evidence stay read-only.
- `sota_research`: independent organization, duplication and missing-explanation
  review; ignored findings/proposals only.

Root owns handbook/repository/reference landing pages, style and verification
contracts, current summary/inventory pointers, failure register, canonical
MkDocs navigation, this plan and the consolidated closeout report. Unassigned
root references/how-tos, sibling READMEs and other trees are allocated after the
complete census; an initial bucket proposal does not establish review coverage.

Serialized resources: Git index/commits, generated publication configuration,
same governed output, dependency-environment writes and strict documentation
build. Pure source inspections, independent tool fixtures and disjoint authored
page edits run concurrently. Preserve the provisioned environment with
`UV_NO_SYNC=1`; root coordinates any missing test dependency offline.

## Pattern pass and acceptance

- P01/P02/P03: capability completeness and consumer visibility are documented,
  not manufactured by prose, schemas or a successful import.
- P04/P05/P09/P15: status composition and candidate/authority boundaries remain
  explicit; drafts and historical receipts cannot become live authority.
- P06/P07/P08/P27: canonical owners, rule/source pins and time roles survive
  consolidation; no sibling documentation system or fake new epoch.
- P29/P31/P32: real-caller behavioral tests and structural repairs; no keyword,
  shape or self-attestation proof. Unsupported predicates remain undecided.
- P35/P36/P37/P38: complete denominators, primary finding citations, actual-read
  receipts and explicit proxy/property divergence. Absence is scoped.
- P39/P40/P41: mandatory companions are outside mechanism budgets; findings
  are bucketed by class; baseline replay and input overlap govern red attribution.

Acceptance: complete coverage/disposition with explicit frozen and unread sets;
corrected high-impact semantic drift; honest draft/smoke tutorials; positive and
negative evidence for tool repairs; fresh targeted tests/lint, canonical drift,
architecture guardrails, Markdown/link QA and strict build; source-code/E02
preservation proof; committed branch readback. A partial checker or unresolved
runtime capability is recorded honestly, not forced green for closeout.

## Progress and closeout

The complete census, twenty lane audits and fourteen supplemental per-path
reviews are recorded under ignored raw receipts. Root subsequently authorized
ordinary README corrections after binding/source review; the read partition
does not imply exclusive authorship. Primary E02/verbatim/source-committed
evidence stays immutable. Source and document reviews found and corrected
namespace mutation, count-to-identity promotion, ADR relation/status parsing,
table serialization and explicit-input receipt defects.

The user approved the exact ten-source-record exclusion and BERL readmission
in `documentation-publication-adjustment-20261014.md`. Canonical configuration
and inventories have been regenerated. Authored formatting uses the existing
pinned tools; generated references retain canonical ownership. The scoped
MD051 TOC exception follows verified MkDocs `attr_list` IDs, which the linter
does not understand; actual rendered fragment QA remains required.

The source was frozen at `c2346b78ff812f0cabad5a48f456ae46de0fcb1c` for the
targeted test, lint, canonical drift, architecture, accuracy, lifecycle,
source/emitted-link and strict-build wave. Its emitted crawl exposed one
historical-owner anchor mismatch. The path-aware gate also exposed stale tools
reference entries and a checkout-dependent absolute footer. The blocking batch
repairs the anchor, regenerates the reference and changes only
`tools.registry.render_reference_docs()` plus its real CLI regression tests;
command metadata, statuses and execution dispatch stay unchanged. The renderer
also qualifies the expired Phase 1D mapping prose as declared historical input.

The public-surface Phase 3A snapshot test reproduced identically at the slice
base with zero selected-input overlap; that narrow failure is inherited/disjoint.
The full architecture and lifecycle gates retain separate incomplete verdicts.
The blocking batch requires a new content freeze, delta checks and emitted-site
verification; completed inputs are reused only after byte-equality proof.

The closeout is `docs/archive/reports/2026-10-14-documentation-maintenance-audit.md`;
its verification section remains pending until those outputs are captured.
Whole lifecycle coverage remains bounded/UNRUN rather than being forced green.
