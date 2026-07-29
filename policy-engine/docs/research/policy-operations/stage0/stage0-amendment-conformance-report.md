---
title: "Stage-0 Research Amendment Conformance Report"
status: delivered_with_declared_blockers
kind: research-conformance
result_type: conforms_with_declared_research_blockers
repository: "https://github.com/DenisKopylov/polisyos"
repository_branch: research/stage0-anchor-amendments
repository_base_branch: research/stage0-anchor-consolidation
repository_base_commit: a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19
repository_main_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
inspection_date: 2026-07-29
authoritative_for:
  - conformance of this documentation amendment to the Stage-0 consolidation record
  - source-integrity, disposition-accounting, and structural-validation results stated here
  - declared research blockers and handoff boundaries for the three revised anchors
may_not_use_for:
  - acceptance of S0-GAP-01 or S0-GAP-02
  - production implementation authorization
  - runtime capability claim
  - benchmark passage
  - legal, administrative, or institutional authority
  - resolution of inherited repository defects
research_only: true
---

# Stage-0 Research Amendment Conformance Report

## Executive Result

**Result: `conforms_with_declared_research_blockers`.**

This amendment produces the requested compressed revisions of PAO-R0, PAO-R1,
and OPS-R15, preserves the exact supplied source artifacts, accounts for all
60 consolidated disposition actions, and keeps the revised conclusions within
the consensus kernel ratified by the audit/consolidation branch.

The result is documentation conformance, not implementation acceptance:

- PAO-R0 remains `research_supported_with_open_owner`;
- PAO-R1 is `accepted_narrower_scope`;
- OPS-R15 is `blocked_pending_oracle_independence`;
- S0-GAP-01 and S0-GAP-02 remain open;
- no H2 runtime, common institutional envelope, production PolicyMatter
  contract, or executable independent benchmark is claimed.

The amendment is stacked on the Stage-0 consolidation commit
`a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19`, which in turn audits repository
main commit `4813b49f6ce14e8debf3aaea096f0967d38d9768`.

# 1. Deliverable Inventory

The amendment contains exactly nine Markdown artifacts under this directory.

| Deliverable | Purpose | Result |
| --- | --- | --- |
| [pao-r0-policy-matter-identity-and-episode-graph.md](pao-r0-policy-matter-identity-and-episode-graph.md) | Compressed PAO-R0 revision | `research_supported_with_open_owner` |
| [pao-r1-operational-boundary-method-and-evidence-interface-census.md](pao-r1-operational-boundary-method-and-evidence-interface-census.md) | Compressed PAO-R1 revision | `accepted_narrower_scope` |
| [ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md](ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md) | Compressed OPS-R15 revision | `blocked_pending_oracle_independence` |
| [stage0-source-manifest.md](stage0-source-manifest.md) | Source provenance, hashes, byte counts, and lineage | Delivered |
| [stage0-amendment-disposition-ledger.md](stage0-amendment-disposition-ledger.md) | One-to-one accounting for 60 consolidation actions | Delivered |
| `stage0-amendment-conformance-report.md` | This verification and blocker record | Delivered |
| [sources/pao-r0-original.md](sources/pao-r0-original.md) | Frozen PAO-R0 source | Byte-identical |
| [sources/pao-r1-original.md](sources/pao-r1-original.md) | Frozen PAO-R1 source | Byte-identical |
| [sources/ops-r15-original.md](sources/ops-r15-original.md) | Frozen OPS-R15 source | Byte-identical |

No code, schema, runtime, benchmark runner, generated API, or production
configuration is part of the amendment.

# 2. Source Integrity

## 2.1 Frozen-source verification

| Source | Lines | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| PAO-R0 | 1,948 | 121,049 | `f7d100465e869dc75165bd6c1b7e7029bcd5ffbe5514a47df1f5343aecd2b840` |
| PAO-R1 | 2,091 | 145,532 | `ea19d89c5fdfde6b64f1509c3c19a19bdca89149901dde7b82e3ed21276e1355` |
| OPS-R15 | 2,672 | 208,289 | `0c3baf41df8ae02bd9f9ae88cc9f1a350d7f4e33021a94327c3e578044690d15` |

The hashes were computed over raw bytes both before and after placement in
`sources/`. No normalization, line-ending conversion, citation cleanup, or
frontmatter rewrite was applied to the frozen copies.

## 2.2 Source-use boundary

The frozen sources preserve the full research record, including claims later
narrowed or rejected. Their presence does not reactivate those claims. The
three revised reports are the current research interpretation; the
disposition ledger records how source sections were retained, narrowed,
converted to questions, deferred, or rejected.

# 3. Compression And Disposition Accounting

## 3.1 Compression

| Report | Source lines | Revised lines | Reduction |
| --- | ---: | ---: | ---: |
| PAO-R0 | 1,948 | 506 | 74.0% |
| PAO-R1 | 2,091 | 570 | 72.7% |
| OPS-R15 | 2,672 | 594 | 77.8% |
| **Total** | **6,711** | **1,670** | **75.1%** |

Compression removed duplication and over-specific candidate contracts while
retaining:

- the research question and project fit;
- the repository baseline and capability labels;
- accepted narrow findings;
- counterexamples and semantic failure modes;
- benchmark/fixture proposals;
- candidate artifact questions;
- integration handoff;
- promotion and kill rules;
- unresolved owner and oracle blockers.

## 3.2 Action closure

| Report | Expected actions | Ledger actions | Accounting |
| --- | ---: | ---: | --- |
| PAO-R0 | 20 | `R0-A01`–`R0-A20` | Complete |
| PAO-R1 | 18 | `R1-A01`–`R1-A18` | Complete |
| OPS-R15 | 22 | `O15-A01`–`O15-A22` | Complete |
| **Total** | **60** | **60 unique IDs** | **Complete** |

The ledger is the amendment's traceability artifact. Report prose is not used
as a substitute for action accounting.

# 4. Consensus-Kernel Conformance

| Kernel item | Amendment treatment |
| --- | --- |
| S0-K01 | Preserves PolicyOS as custodian of claims it signs, not of external administration. |
| S0-K02 | Separates external acts, evidence, admission, claim reaction, and projection. |
| S0-K03 | Treats missing evidence as unknown rather than proof of non-occurrence. |
| S0-K04 | Keeps PDC authority grammar canonical and rejects a parallel status lattice. |
| S0-K05 | Keeps Atlas projection-only and prohibits surface-minted authority. |
| S0-K06 | Separates technical integrity from semantic and authority validity. |
| S0-K07 | Requires append-only correction, supersession, withdrawal, and historical replay. |
| S0-K08 | Preserves tenant and jurisdiction scope; rejects implicit cross-scope equality. |
| S0-K09 | Keeps external execution outside PolicyOS while retaining claim-reaction responsibility. |
| S0-K10 | Treats owner proposals as hypotheses until a canonical owner is ratified. |
| S0-K11 | Rejects common envelopes, clocks, states, and gates without owner ratification. |
| S0-K12 | Keeps family-native evidence semantics and purpose-specific admission. |
| S0-K13 | Keeps PolicyMatter above-case identity as a hypothesis with an open owner. |
| S0-K14 | Keeps matter continuity separate from evidence applicability and legal continuity. |
| S0-K15 | Retains OPS-R15 semantic predicates while blocking benchmark passage claims. |
| S0-K16 | Requires an independent oracle/evaluator and anti-leakage architecture before benchmark promotion. |

# 5. Overclaim And Boundary Checks

The revised reports contain no claim that:

1. a canonical `PolicyMatter` contract or owner exists;
2. PDC, runtime quality, H2, or Atlas has been assigned new ownership by this
   amendment;
3. PAO-R1's 213-row census is an adjudicated production register;
4. EC-01..21 is a frozen universal evidence interface;
5. a universal institutional envelope, evidence-status lattice, owner-state
   lattice, clock bundle, or challenge workflow is ratified;
6. OPS-R15 is executable, independent, sealed, or passed;
7. the scenario author can act as an independent oracle;
8. proposed runtime states, gates, graphs, RPO/RTO values, or efficiency
   thresholds are Stage-0 contracts;
9. PolicyOS performed an external administrative, legal, payment, notification,
   delivery, procurement, records, audit, or oversight act;
10. a signature alone establishes competence, scope, legal effect, identity, or
    evidence applicability.

Conversation-only `filecite` markers are absent from amendment-authored
artifacts. Any such markers in a frozen source remain inert historical bytes.

# 6. Mechanical Verification

## 6.1 Completed checks

| Check | Result |
| --- | --- |
| Exact final file inventory | Pass: nine expected artifacts |
| YAML/frontmatter parsing | Pass |
| `research_only: true` on every artifact | Pass |
| Markdown table column consistency | Pass |
| Relative-link resolution | Pass |
| Forbidden marker scan in amendment-authored files | Pass |
| Disposition-ID count and uniqueness | Pass: 20 + 18 + 22 |
| Frozen-source SHA-256 verification | Pass |
| `git diff --check` on amendment-authored files | Pass |
| Full staged `git diff --check` | One expected warning: the byte-identical frozen OPS-R15 source contains its original terminal blank line |
| Targeted PDC/reissue/core-audit/Fabric tests | Pass: 32/32 |
| Docs gate/lifecycle tests | 31 passed / 2 inherited baseline failures |

The checks were repeated after this report was added.

## 6.2 Repository lifecycle baseline

Direct execution of:

```text
PYTHONPATH=src:. python3 tools/quality/validation/check_docs_lifecycle.py --repo-root .
```

returns three existing findings:

1. `architecture/atlas_surfaces/atlas-v15-adoption-ledger.json` contains the
   retired pre-`apps/` runtime-dashboard path;
2. `architecture/atlas_surfaces/atlas-v15-archive-map.json` contains the same
   retired path;
3. `docs/reference/frontend/atlas-v15-adjudication.md` contains the same
   retired path.

All three require the canonical `apps/runtime-dashboard` path. The amendment
neither edits those files nor repeats the retired literal. A follow-up audit
caught and removed that literal from this report itself: before the correction,
the lifecycle validator reported a fourth amendment-introduced finding; after
the correction, the amendment overlay and clean base both report exactly the
same three findings above.

The path-aware docs gate selected the docs-freshness baseline for the nine
changed paths. Initial execution of its `uv run` wrapper could not start because
the environment exposed `/root/.local/share/uv/python` as read-only. A follow-up
run on the exact amendment plus the draft CI-repair tree
`a5acf91c3444ecd8bcf317fa7475d206c0e1379e`, with audit-only uv caches under
`/tmp`, completed dependency synchronization and ran the wrapper. It reported:

1. the docs-freshness exception baseline has expired;
2. expected violation count `0`, observed `6`;
3. expected hash
   `a3030ecf013ab9e3e7dac6f2892361fad35f63774f7e4fe7a2`, observed
   `b5a0970a3b9817321e6dbfc2554dc1491a9717b363af52ed81c722fab406ec37`.

The same three freshness findings, including the exact observed count and
hash, were reproduced in a detached clean worktree at the amendment base
commit. They are therefore inherited from the stacked base rather than
introduced by these nine files.

## 6.3 Targeted test evidence and remaining limitation

The initial amendment environment lacked `pytest`. The follow-up CI-repair
overlay resolved that bootstrap limitation and ran only the review-relevant
test set:

- 32/32 targeted PDC waist, partial-reissue, core-audit, and Fabric
  `SourceContract` tests passed;
- the docs gate/lifecycle suite returned 31 passed and the same two base
  failures: the three retired-path findings above are asserted by one test, and
  the expired/drifted freshness baseline is asserted by the other.

No repository-wide test pass is claimed. These local tests establish narrow
contract and documentation-integration evidence only; they do not implement or
validate PolicyMatter, a production boundary register, H2 custody, partner
evidence, or an independent OPS-R15 oracle.

# 7. Open Research Blockers

## 7.1 S0-GAP-01

The minimum Policy Subject Reference and semantic-owner decision remains open.
Before PAO-R0 can move beyond research guidance, team-architecture and the
relevant canonical owners must decide:

- the minimum subject-reference ABI;
- semantic ownership and package placement;
- cardinality and namespace rules;
- unresolved/contested subject closure;
- correction and replay semantics;
- the boundary between technical custody identity, legal identity, and
  evidence applicability.

## 7.2 S0-GAP-02

The independent Custody-Benchmark Oracle and Evaluator Architecture remains
open. Before OPS-R15 can be executable or passable, benchmark engineering must
define:

- a machine-readable corpus;
- an evaluator independent of the implementation under test;
- sealed or appropriately hidden expected outcomes;
- anti-leakage access and rotation procedures;
- mutation and metamorphic adequacy tests;
- provenance and versioning for scenarios and oracle judgments;
- a rule for independent adjudication of genuinely unresolved cases.

## 7.3 External and pilot facts

Jurisdiction-specific competence, legal effect, institutional operators,
partner systems, signatures, correction channels, privacy/records controls,
and degraded-mode responsibilities remain pilot- or jurisdiction-dependent.
The census can open those questions; it cannot answer them by repository
declaration.

# 8. Separate Repository Defects

The consolidation record identifies five implementation defects that remain
separate from this research amendment:

1. tenant-blind decision-validity paths;
2. incomplete checkpoint/control binding;
3. unknown-jurisdiction fallback to UA;
4. a public-export redaction test failure;
5. Atlas local-readiness authority minting.

This documentation-only change does not repair, waive, or reclassify them.

# 9. Promotion Decision

The amendment is suitable for a stacked draft review over the Stage-0
consolidation branch. It is not a production candidate.

Promotion beyond research documentation requires:

1. team-architecture acceptance of the consensus kernel;
2. disposition of all 60 ledger actions;
3. S0-GAP-01 closure before a canonical PolicyMatter contract;
4. S0-GAP-02 closure before an executable OPS-R15 benchmark claim;
5. canonical-owner review for each affected contract family;
6. target-jurisdiction and partner validation where external authority is
   load-bearing;
7. repository implementation and semantic tests in separate authorized work.

Until those conditions hold, the revised reports are authoritative only for
their stated research findings, guardrails, and open questions.
