---
plan_id: atlas-ds11-trust-docs-posture
title: "DS11 - Trust / Docs Posture"
type: slice-plan
status: proposed_approval_gated
created: 2026-08-26
last_verified: 2026-08-26
stability: measured_planning_handback
slice: DS11
baseline_commit: f935e0c2e9359bc1202ce5d36ea706de58f7aaab
branch: codex/ds11-trust-docs-posture-plan
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
debt_register: ../DEBT-REGISTER.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
audiences: [PUBLIC, REVIEWER, EXPERT, MACHINE]
artifact_owner: team-architecture
producer_lane: scientist/evidence/claims
surface_owner: team-design
feature_flags: none
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ./DS9-human-decision-integrity.md
  - ./DS6-evidence-workflow.md
---

# DS11 - Trust / Docs Posture

## For agentic workers

This is an approval-gated implementation plan, not authorization to implement.
The planning branch `codex/ds11-trust-docs-posture-plan` was attached and clean
at immutable `main` base `f935e0c2e9359bc1202ce5d36ea706de58f7aaab`
before this file became its sole change. The repository coordinate must be
measured before every path claim with `git rev-parse --show-prefix`: from the
product root it is `policy-engine/`, and from the repository root it is empty.
Root alone writes. Before every commit, re-read `git status -sb`,
`git symbolic-ref -q HEAD`, the prefix, and the cluster path fence. Before
approval: no production code, source metadata, writer, generated artifact,
register lock, visual lane, merge, push, rebase, reset, stash storage, or
master-plan edit.

After approval, C00 begins from an attached execution branch containing this
plan. Use `corepack pnpm`, never bare `pnpm`; install the frozen workspace before
trusting a TypeScript scanner. Do not run `guardrails sync`. Run only the
targeted commands named here. Generated posture bytes are written only while
holding the generated-artifact token; Atlas disposition bytes only while
holding the register-family lock; debt/ledger records use that same lock; visual
snapshots only while holding the visual lane. No two serialized resources
co-hold.

**Execution amendment (2026-08-26):** the execution instruction approves a
hard slice-wide mechanism ceiling of **34** paths. Execution has consumed
**30** mechanism paths, leaving **4** paths of headroom, and all **9** widening
rounds. The observed total includes the three C04 scanner/checker/schema paths
required to close CC21 over its complete denominator and the C05 debt-ledger
checker path required to close CC24; tests and generated records remain P39
companions. This accounting correction authorizes no additional mechanism or
widening.

Ceilings are charged in completed `user + sys`, never wall time. Every command
records `uptime` immediately before and after, selected-test count, exit code,
`user`, `sys`, ceiling, and whether it wrote. A sleeping laptop, a killed run,
or a missing tool sets no ceiling.

## Mission and boundary

DS11 makes Surface Laws 5 and 6 executable before any performance claim exists.
It compiles existing authority declarations into one strict, owned, persisted
claim-posture artifact; computes `supported`, `planned`, or `blocked` without
letting projection mint authority; exposes methodology, declared evidence envelope,
limitations, and dated accessibility evidence at a public `/trust` route; and
serves the exact artifact bytes as the MACHINE twin.

The register is a projection over producers, not a second author. Its source
inventory includes every raw `authoritative_for` candidate in tracked `src/`,
classifies exact declarations, carriers, consumers, known declaration+consumer
files, genuine ambiguities, and substring collisions, and never turns an
unresolved declaration into a silent zero. A new producer declaration grows the
generated register without editing the register artifact, a subject list, a
dashboard switch, or a translation catalog.

DS11 does **not** make a grounded-performance claim; perform the first governed
promotion; publish a decision or signature; upgrade `candidate` or `planned` to
`supported`; invent a claim absent from a producer; promise that signatures are
watched when the watcher is not orchestrated; create a scope-adjudication
runtime; build a general documentation portal, procurement trust center,
security/compliance programme, public telemetry service, CRM, or case system;
or modify DS12's other gate. The correct opening register is mostly negative.

The opening DS11 end-to-end capability is `absent/unallocated`: no admitted
DS11 contract or appointed complete chain exists yet. Relative to the proposed
chain, the concrete gaps are `producer_missing + artifact_missing +
bridge_missing + consumer_missing + surface_missing + semantic_test_missing`.
Existing claim, lifecycle, provenance, Trust View, and generated-artifact
primitives reduce the work but do not create a DS11 contract by themselves.

## Canonical Closure Contract

DS11 closes only when every checkbox has its named behavioral receipt. No
cluster may define a second closure contract.

- [x] **CC01** The approved plan, exact execution base, attached branch, prefix,
  DS9/DS6 ancestry, green release guardrail, and the inherited frontend-checker
  red are recorded before any implementation edit.
- [x] **CC02** Two independent complete-source derivations agree file-for-file.
  The immutable entry census is 2,579 Python files / 104 raw candidates / 103
  exact-field files: 66 `declares_only`, 5 `carries_only`, 5 `consumes_only`, 27
  `declares_and_consumes`, 1 `substring_collision`, and 0 `ambiguous`, with 93
  declaring and 32 consuming files. The final live census is 2,580 / 105 / 104:
  66 / 5 / 5 / 28 / 1 / 0, with 94 declaring and 33 consuming files. Any
  disagreement is emitted as `ambiguous` with file and line, never guessed.
- [x] **CC03** One strict Pydantic contract (`extra="forbid"`) owns claim ID,
  subject/family, source symbol and digest, jurisdiction, accountable owner and
  owner basis, review dates, `authoritative_for`, `may_not_use_for`, evidence and
  limitation refs, effective state, blocker codes, rule/schema version,
  source-as-of time, audience, supersession fields, the exact identity
  statement and anti-role derivation receipts, and a frozen P37 establishment
  class for every support predicate.
- [x] **CC04** The canonical producer walks the complete tracked source set,
  distinguishes entry's 103 and final live's 104 exact-field files from the one
  `authoritative_for_runtime` collision, resolves every static literal/default
  it can prove, and retains every dynamic/unresolved site as a blocked
  `runtime_bound` or `ambiguous` row. Entry/final `may_not_use_for` raw counts
  remain separately 116/117.
- [x] **CC05** Effective-state composition is fail-closed: `blocked` vetoes;
  `planned` is a named commitment whose every producer arm has its own
  established owner and executable closure signal, not support; `supported`
  requires content-bound source, purpose permission,
  accountable owner, applicable jurisdiction, current review, verifier-proven
  evidence, and no blocker. Only `recomputed` or `independently_reconciled`
  gate predicates may support; `consumer_asserted`, `institutionally_supplied`,
  and `not_established` block. No status is treated as an ordinal.
- [x] **CC06** The free-growth e2e adds one correctly formed producer in a
  scratch source tree and obtains exactly one new register subject with zero
  register-artifact, source-policy, dashboard-production, or locale edit; the
  same test proves missing metadata keeps the new row non-supported.
- [x] **CC07** Direct literals reproduce 35 sites / 13 files / 21 non-empty
  subjects by both AST and `tokenize`; wrapper literals reproduce 59 sites / 24
  files / 28 subjects and cannot disappear merely because the narrow census is
  smaller.
- [x] **CC08** No central file enumerates open-ended claim subjects. Source-root
  policy may enumerate closed source families and rendering templates, but not
  claim IDs, producer symbols, or subject slugs.
- [x] **CC09** The existing per-run `RuntimeClaimRegistry` remains the owner of
  producer-evidence bindings for final runtime claims. DS11 neither renames nor
  overloads it; the posture artifact has a distinct schema, authority purpose,
  producer, persistence lifecycle, and consumer.
- [x] **CC10** The deterministic JSON is committed under the dashboard's static
  public tree, registered as a `generated_committed` family, and regenerated in
  scratch by the default architecture guardrail. A corrupt field, missing row,
  stale review, reordered source binding, or generator escape fails CI.
- [x] **CC11** `/trust` renders a register-driven methodology section explaining
  the claim/evidence/status calculus and producer-declared method subjects
  without claiming accuracy, effectiveness, speed, or causal performance.
- [x] **CC12** `/trust` renders the declared evidence envelope and limitations first:
  unknown jurisdiction, stale/unreviewed source, runtime-bound declaration,
  missing evidence, contested state, and forbidden purposes remain visible in
  PUBLIC, REVIEWER/EXPERT, and MACHINE projections.
- [x] **CC13** Accessibility renders two different truths: the dated internal
  2026-Q2 pre-audit evidence is historical and bounded; external certification
  and countersign remain blocked, and
  [DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4) remains visible.
  Neither `WCAG certified` nor a current unbounded-conformance claim can be
  emitted.
- [x] **CC14** The custody commitment is a first-class `planned` claim sourced to
  the ratified identity; its prerequisite refs bind the autonomous watcher to
  `team-runtime`, the lifecycle bridge to `team-scientist`, and the public
  signature population to DS12 / `team-design`, each with its capability label
  and executable closure signal. No generic implementation-lane owner may
  satisfy that three-owner obligation or imply universal coverage.
- [x] **CC15** The four-way `own` / `integrate` / `observe` / `out_of_scope` test
  stays owned by the ratified decision document. Claim rows carry a strict
  identity-boundary source ref, not a duplicated per-claim scope enum. Any
  declared scope assumption is frozen `not_established`, rendered as a
  limitation, and forbidden from supporting a claim; the absent typed
  `ScopeAdjudicationRecord` remains explicit non-closure.
- [x] **CC16** The identity parser derives all seven binding anti-roles from the
  ratified paragraph, including CRM. Both derivation receipts are recomputed
  from the emitted roles, every role binds the admitted identity bytes, and
  `/trust` renders the exact content-bound identity statement plus all seven
  roles. The posture surface admits no free-form capability assertion: inserting
  `manages your cases` as unbound copy fails the identity/copy check without a
  keyword blacklist.
- [x] **CC17** A producer whose source state is `planned` or `candidate` cannot be
  rendered, downloaded, translated, or restyled as `supported`; mutations of
  each bridge independently fail the register check.
- [x] **CC18** A grounded-performance-family row cannot be `supported` without a
  content-bound governed-performance producer and prerequisite ref. At the DS11
  base those inputs do not exist, so the named negative stays red-to-green by
  rejection, not by minting a fixture.
- [x] **CC19** The public loader captures the exact static response bytes, parses
  them through a strict frontend validator, and renders only the validated
  artifact. Parse failure, schema novelty, or missing bytes produces a visible
  unavailable/blocked surface, never cached support.
- [x] **CC20** MACHINE downloads those captured bytes without reserialization;
  a DOM decoder reconstructs every ordered public row, source, status,
  limitation, blocker, and review field. Omission, reorder, state mutation, and
  hidden limitation fail independently.
- [x] **CC21** DS11's two inherited Trust View authority roots are rebound through
  a private exhaustive presentation issuer over the canonical runtime
  `VerificationMetadata` input; raw dispute/tone strings and structural
  lookalikes cannot issue trusted clothing, while runtime novelty is explicit
  `unrecognized`.
- [x] **CC22** `trustRoute` in `features/trust/routes.public.tsx` is the declared
  supported dashboard entrypoint: `APP_ROUTES` consumes that exact export, the
  landing surface links it, and the complete browser-a11y inventory derives it.
  Its static MACHINE artifact has the registered generated lifecycle. No Python
  public facade, unauthenticated HTTP exception, OpenAPI path, or client ABI is
  added; those consequences are explicitly `surface_out_of_scope`.
- [x] **CC23** Targeted model, compiler, generator, route, twin, Trust View,
  DS11 route-a11y, and visual tests pass. The complete page-a11y suite produces
  **25 tests / 22 pass / 3 current failures** in two completed exact no-writer
  executions. All three are members of
  [DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4): color-blind
  distinguishability, run-report axe `dlitem`, and run-report missing `Export
  JSON`. The base missing-`Open run` identity does not reproduce. Independent
  `--list` and TypeScript-source enumeration prove the 25-test set, exactly one
  larger than base; `/trust passes axe` is the added passing member and no novel
  DS11 failure identity exists. The committed historical 20/24 four-failure
  receipt remains visible and cannot be reissued by this slice; current
  conformance stays blocked. The global frontend disposition check likewise
  produces exactly its pinned base C13 error and no new error; release guardrails
  remain green with zero creep.
- [x] **CC24** The committed attached branch is read back after writing and proves
  closure-item receipts, actual path/round totals, generated byte identity,
  serialized-resource uptime pairs, exact non-closures, and no production path
  beyond the approved fence.

## The four hard problems and their rulings

### 1. The register is compiled, not authored

The raw grep population is an input census, not the claim set. The generated
artifact has two related projections:

1. `source_inventory` contains all 104 raw candidate files and their role,
   coordinates, source digest, derivation receipts, known combined role, and
   ambiguity/collision state.
2. `claims` contains every statically resolved subject plus explicit blocked
   rows for runtime-bound or unresolved declarations. Multiple producers for one
   subject remain separate source bindings under one stable subject row; their
   authority bounds intersect and conflicts block support.

The compiler uses Python AST; an independent `tokenize` source walk recomputes
the denominator, statement targets, literal subjects, and roles. Neither reads
the generated artifact as an input. Agreement is checked file-for-file, not by
count alone. A disagreement produces a named blocked row with both coordinates.

Package contracts supply a candidate accountable-owner default. They do not
prove claim review or jurisdiction. Each support predicate is frozen at source
admission as `recomputed`, `independently_reconciled`, `consumer_asserted`,
`institutionally_supplied`, or `not_established`; only the first two may carry a
support gate. Missing review/jurisdiction remains typed unknown and blocks
support. Producer/document metadata may index those fields at the source but
cannot establish them by declaration alone; the generated register is never
edited to do so. The falsifier changes or removes the cited source fact while
leaving its metadata declaration intact, and support must disappear.

### 2. Projection can state a claim and cannot mint one

Public claim-bearing text is not arbitrary prose. The artifact contains source-
bound structured statements or source excerpts; the UI localizes only closed
labels and sentence frames around the immutable subject, state, limits, and
source. Claim-bearing translations cannot alter those fields. The sole claim
renderer accepts a validated row, not a string.

The effective-state rule is:

```text
blocked if source unresolved/ambiguous
        OR purpose not in authoritative_for
        OR purpose in may_not_use_for
        OR owner/jurisdiction/review/evidence not established
        OR evidence stale/invalid/contested
        OR identity boundary violated
        OR grounded-performance prerequisite absent

planned if a source-bound commitment has an accountable owner
        AND an executable closure signal
        AND no current-support assertion

supported only if every required predicate above is independently established
          AND no blocked/planned/candidate arm survives
```

For mixed producers, `blocked` vetoes `planned`, and either vetoes `supported`.
`planned` is not a lower support score. A UI label, translation key, artifact
field, or authored `supported` value cannot override the computed result.

### 3. Binding anti-roles are checked structurally, not by keywords

The compiler parses the ratified identity frontmatter and the complete binding
anti-role paragraph, normalizes the seven role records, and content-binds their
source span. The identity surface renders that derived set. A second paragraph
normalizer test must reproduce the same seven.

The copy check proves a bounded property: **inside the DS11 posture feature and
its landing entry, every capability assertion is emitted by the sole validated
claim renderer from a content-bound source row**. Direct JSX capability prose,
an unbound translation key, or an artifact statement without a resolvable source
span fails. Therefore `manages your cases` fails because no admitted source can
emit it, not because the checker searches for `manage` or `case`.

This does not claim general natural-language understanding. An oblique anti-role
implication in a different website feature, or a future ratified source that
itself changes the boundary, is outside this structural check. That bounded
residual is explicit below; a keyword blacklist would agree often and fail at
exactly that boundary (P38).

### 4. Reuse the real seams without collapsing their meanings

Two independent searches find zero exact `claims_register` / `ClaimsRegister`
files, but 33 tracked source/test files use the existing
`RuntimeClaimRegistry` vocabulary. That registry is schema
`policyos.runtime.claim_registry.v1`, is built in the natural-language runtime
pipeline, and binds per-run producer evidence to final claims. It is not a
system-wide public posture owner.

DS11 reuses `ClaimSupportStatus`, `ClaimPublishability`, `ClaimLifecycleEvent`,
append-only claim ledgers, `ArtifactRef`, producer/provenance primitives, and
audience projection patterns. Its distinct artifact lives under the canonical
Scientist claims owner and is consumed as generated static data. There is no new
runtime endpoint, auth exception, OpenAPI operation, or generated API client.

The four-way scope test is document-authoritative but has no typed runtime
owner across 2,579 tracked source Python files and 2,419 tracked test Python
files, each independently counted by pinned `git ls-tree` and `git ls-files`.
It classifies an institutional function one plane at a time; copying its enum
onto every claim would both misclassify the object and create a hidden contract-
only owner. Rows therefore carry the document ref and any declared scope
assumption, never a fabricated adjudication. A scope assumption is frozen
`not_established`, is visible only as a limitation, and cannot contribute to
`supported`; the falsifier changes the assumed scope while keeping every other
row field intact and the row must remain non-supported.

## Measured entry receipts

### Base, gates, coordinate, and timings

<a id="ds11-a11y-base-failure-set-4"></a>

#### DS11-A11Y-BASE-FAILURE-SET-4

The canonical short identity binding is the complete four-member inherited
failure set from committed raw run 1:

1. color-blind distinguishability —
   `../src/test/a11y/color-blind-simulation.spec.ts::keeps signal pairs distinguishable for deuteranope, protanope, and tritanope viewers`;
2. run-report axe `dlitem` — `a11y/routes.a11y.spec.ts::run-report passes axe`;
3. runs-list screenreader missing `Open run` —
   `../src/test/a11y/screen-reader-snapshots.spec.ts::runs list exposes named landmarks and actions`; and
4. run-report screenreader missing `Export JSON` —
   `../src/test/a11y/screen-reader-snapshots.spec.ts::run report exposes named export actions and timeline content`.

Every later reference to the inherited page-a11y failure set resolves to this
binding, not to an unqualified count.

| item | pinned receipt |
| --- | --- |
| base | attached `codex/ds11-trust-docs-posture-plan`; `HEAD == main == f935e0c2e9359bc1202ce5d36ea706de58f7aaab` before the plan edit |
| dependency gates | `git merge-base --is-ancestor fd243d1ad HEAD` = 0 (DS9); `git merge-base --is-ancestor 176276ef0 HEAD` = 0 (DS6) |
| coordinate | repository-root `git rev-parse --show-prefix` = empty; product-root result = `policy-engine/`; top level `/Users/deniskopylov/polisyos` |
| release guardrail | `uv run polisyos-tools architecture guardrails check` = 0 with required generated freshness green; `user 40.04 + sys 40.61 = 80.65s`; uptime `16:17 up 2 days, 6:30` -> `16:19 up 2 days, 6:32` |
| focused Trust View baseline | Vitest reports **4 files / 6 tests green**; independent exact-path `rg` counts `1 + 1 + 3 + 1` test identities in `DisputeBadge.a11y`, `VerificationStatus.a11y`, `TrustViewAuthority`, and `trustViewArchitecture`; `user 7.55 + sys 1.49 = 9.04s`; uptime `16:24 up 2 days, 6:37` before/after |
| package-import exact-base replay | at exact slice base `f935e0c2e`, exit `1` with JSON `finding_count=143`; `user 83.89 + sys 4.49 = 88.38s`; uptime `22:40` -> `22:42`. The earlier 142 is invalidated as a shared-source-root reading; no current-branch count is claimed. |
| frontend disposition baseline | exact `--check` completes red only on `c13_print_receipt_invalid:.../RunDetailLayout.tsx`; `user 195.14 + sys 27.53 = 222.67s`; uptime `18:33` -> `18:37` |
| complete page-a11y baseline | the committed raw JSON receipt independently establishes **20/24 pass** and [DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4). A second measured `20/24` execution is recorded only as `consumer_asserted` agreement because no second raw artifact is committed; it cannot support a semantic product gate or posture row. Replay A `user 212.21 + sys 29.76 = 241.97s`, replay B `user 287.42 + sys 40.22 = 327.64s` |
| planning debt-ledger admission | read-only `check_debt_ledger.py --check --report-only` reports exactly 10 DS11 `explicit_nonclosure_missing` rows plus `ledger_render_drift`; the checker's parsed IDs and an independent count of the 10 bullets under `## Explicit non-closure` agree; `user 0.40 + sys 0.30 = 0.70s`; uptime `17:08 up 2 days, 7:21` before/after. These are the expected planning-handback reds until C00 uses the sole register writer and regenerates the ledger. |

The release guardrail and frontend disposition checker are different gates. The
first is green. The second has an inherited DS6 C13 evidence-currentness red at
the exact DS11 base. C00 freezes its stderr and complete input set; C06 must show
the same single base error and zero DS11 additions, or stop. DS11 does not
reissue another slice's print evidence.

The complete targeted page-a11y suite is also red at the exact base. Its dated
Q2 pre-audit is valid only as a historical receipt, not evidence of current
conformance. C00 freezes
[DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4) and the complete
page-suite denominator; C06 requires zero DS11 additions and records the
inherited current-conformance limitation rather than repairing the run paper.

### Requested starting-state census

Every set-level count has two independent complete-set derivations. Counts with
different denominators remain different.

| fact | derivation A | derivation B | ground truth and known member |
| --- | --- | --- | --- |
| tracked Python denominators | pinned `git ls-tree -r --name-only` suffix count | pinned `git ls-files` suffix count on the same roots | **2,579 `src/` + 2,419 `tests/`**; known source `core/contracts/runtime.py`, test `tests/unit/core/contracts/test_capability_discovery.py` |
| raw `authoritative_for` files under tracked `src/` | `rg -l` over the working tree | raw-substring scan over `git archive f935e0c2e` | **104 Python files**; known `participation_requirement/__init__.py`; 0 non-Python |
| exact `authoritative_for` field files | exact-word token scan | AST field/argument/keyword/attribute/string-key walk over all 2,579 Python files | **103**; the 104th is `best_snapshot.py` using distinct `authoritative_for_runtime` |
| `may_not_use_for` files | `rg -l -w` | pinned `git grep -l` | **116 Python files**, 0 non-Python; known `foundry/welfare/frontier_emitter.py` |
| direct literal declarations | AST direct tuple/list/set assignments | independent `tokenize` balanced-literal walk excluding parameters, `Field`, factories, expressions | **35 sites / 13 files / 21 non-empty subjects**; 5 sites are explicitly empty; known `pareto_frontier_fact` |
| wrapper-inclusive literals | AST including `Field(default=<literal>)` and literal lambda factories | source/token replay of the same bounded wrappers | **59 sites / 24 files / 28 subjects**; known `conflict_materialization` |
| all-literal `may_not_use_for` subjects | AST exact-target walk over all 2,579 Python files; direct literals plus `Field(default=<literal>)` and literal lambda factories | pinned `git archive` raw source + `tokenize` balanced-literal scan over the same bounded forms | **34 sites / 22 files / 44 subjects**; known `foundry/welfare/frontier_emitter.py:144` |
| exact `claims_register` / `ClaimsRegister` spellings | `rg` across all tracked-visible paths | pinned `git grep` | **0 files** |
| existing runtime-registry vocabulary | `rg` for `RuntimeClaimRegistry|runtime_claim_registry` under `src` + `tests` | pinned `git grep` | **33 files**; known `src/polisyos/runtime/quality/claim_registry.py` |
| ratified identity bytes | `wc -c` + SHA-256 | pinned blob size + streamed SHA-256 | **13,273 bytes**, SHA-256 `774f6dfb9aa655a079d6c6a2f00ef6442bad9f0ea9b84f370a4e808c5616a332` |
| binding anti-roles | full-paragraph regex extraction | normalized paragraph delimiter split | **7**; known `CRM`; both methods cover one complete binding paragraph |
| immediate dashboard feature directories | `find -maxdepth 1 -type d` | pinned `git ls-tree -d` | **14**, not 16; known `evidence`; no `trust`, `docs`, or `posture` directory |
| immediate feature entries | `find -maxdepth 1` | pinned tree entries | **17** = 14 directories + 3 Markdown files; this does not rescue the supplied 16 |
| exact status-language files | exact-word `rg` in `*.ts,*.tsx,*.json` under `features` | `find` + `grep -Eil` on the same typed-file denominator | **26**, not 29; known `RunDetailLayout.tsx`; all-source and substring denominators produce 58 and 42 and are not substitutes |
| claims/posture CI checker | filename/content search in tools, architecture, workflows | pinned `git grep` for checker/claims-posture combinations | **0**; a Layer-3 artifact mentioning claim-registry consumer gates is not a DS11 checker |
| DS11 Trust View authority roots | exhaustive `frontend-disposition-register.json` filter for `owner_slice = DS11` and trust-view prop debt | independent checker descriptor-map enumeration | **2**: `authority-presentation-prop-dispute-status` and `authority-presentation-prop-verification-status-icon-tone` |

The supplied 104 and 116 loose-file counts reproduce. The supplied 35/13/21
also reproduces exactly once “literal” is defined as direct assignment. The
supplied 16 dashboard features and 29 status-language files do not reproduce
under any declared complete denominator and are not encoded as constants.

### Complete 104-file role partition

Method A is the AST walk over all 2,579 tracked Python files, classifying exact
field nodes plus enclosing semantic guards. Method B is a raw-source review of
the 104 pinned substring files: declaration witness, semantic condition/
rejection/invariant witness, mechanical transport only, or distinct-field
collision. Method B does not import AST results. They agree file-for-file:

| role | AST A | raw source B | only A | only B |
| --- | ---: | ---: | ---: | ---: |
| declares only | 66 | 66 | 0 | 0 |
| carries only | 5 | 5 | 0 | 0 |
| consumes only | 5 | 5 | 0 | 0 |
| declares and consumes | 27 | 27 | 0 | 0 |
| substring collision | 1 | 1 | 0 | 0 |
| ambiguous | 0 | 0 | 0 | 0 |
| total | **104** | **104** | **0** | **0** |

The inclusive role totals are **93 declaration files** (66 + 27) and **32
semantic-consumer files** (5 + 27). The rows below remain mutually exclusive.

`carries_only` (complete):

```text
policy_grammar/_impl/authority.py
policy_grammar/_impl/compiler.py
runtime/http/services/cycle_board_contracts.py
runtime/http/services/governed_projections.py
scientist/methods/research_dag/projections.py
```

`consumes_only` (complete):

```text
policy_grammar/_impl/consumer.py
runtime/quality/authority.py
runtime/quality/design_axes/projection_lowering.py
runtime/quality/required_reference_resolver.py
scientist/evals/challenge_factory.py
```

`declares_and_consumes` is a positively established combined role, not an
ambiguity. Complete declare/consume coordinates:

```text
core/contracts/capability_discovery.py:190 / :204
core/contracts/policy_design_case_projection.py:238 / :260
core/contracts/runtime.py:365 / :371
corpus/_impl/annotations.py:288 / :299
evidence/portfolio/conflict_records.py:60 / :72
pdc/_impl/compiler.py:70 / :83
pdc/_impl/layer2_design_search.py:1449 / :598
pdc/_impl/layer2_readiness.py:66 / :119
runtime/http/services/human_decision_contracts.py:758 / :789
runtime/quality/agent_action_authority.py:1869 / :212
runtime/quality/derived_observations.py:184 / :731
runtime/quality/design_axes/coupling_composition.py:396 / :1944
runtime/quality/design_axes/mandate_bounded_delegation.py:926 / :331
runtime/quality/design_axes/post_deploy_accountability.py:997 / :1005
runtime/quality/design_axes/universality_assurance.py:796 / :1143
runtime/quality/projection_semantics.py:433 / :553
runtime/quality/prompt_tool_ledger.py:105 / :124
runtime/quality/proving_ground/bounded_request_agent.py:317 / :322
runtime/quality/proving_ground/causal_forecast_search.py:365 / :4237
runtime/quality/proving_ground/governed_promotion_gate.py:786 / :4246
runtime/quality/proving_ground/legal_mandate_search.py:271 / :4754
runtime/quality/proving_ground/pre_adapter_grounding_inventory.py:276 / :1937
runtime/quality/proving_ground/proof_carrying_analytics_search.py:260 / :2863
runtime/quality/proving_ground/proving_ground_conversion.py:827 / :1671
runtime/quality/proving_ground/region_widening.py:566 / :3131
runtime/quality/proving_ground/substrate_grounding_search.py:275 / :2762
scientist/policy_design/formulator.py:75 / :87
```

The complete `declares_only` set is:

```text
core/contracts/rule_evolution.py
corpus/_impl/expert_adjudication.py
data_requirement/_impl/models.py
evidence/portfolio/effective_independence_graph.py
foundry/validation/method_quality.py
foundry/welfare/frontier_emitter.py
foundry/welfare/social_weight_provenance.py
legal_requirement/_impl/models.py
lex/normpack/legal_authority.py
method_requirement/_impl/models.py
obligation_graph/_impl/compiler.py
obligation_rules/catalog.py
participation_requirement/__init__.py
runtime/http/openapi_contract.py
runtime/http/services/control/workspace_loop_transition.py
runtime/http/services/cycle_board_projection.py
runtime/http/services/human_decisions.py
runtime/quality/acquisition_planner.py
runtime/quality/argument_graph.py
runtime/quality/calibration_ledger.py
runtime/quality/capability_authority.py
runtime/quality/capability_discovery.py
runtime/quality/capability_index.py
runtime/quality/capability_index_compiler.py
runtime/quality/case_lifecycle.py
runtime/quality/closeout_reader.py
runtime/quality/complexity_governance.py
runtime/quality/concept_spine.py
runtime/quality/construct_registry.py
runtime/quality/corpus_fixture_producer_reports.py
runtime/quality/cost_gate.py
runtime/quality/data_forge_binding.py
runtime/quality/design_axes/blind_spot_firewalls.py
runtime/quality/design_axes/epistemic_regime.py
runtime/quality/design_axes/outcome_prediction.py
runtime/quality/design_axes/predictive_knowledge.py
runtime/quality/design_axes/resource_economics.py
runtime/quality/design_axes/substrate_acquisition.py
runtime/quality/design_axes/value_choice_provenance.py
runtime/quality/generation_cycle.py
runtime/quality/graded_outcomes.py
runtime/quality/human_review.py
runtime/quality/hypothesis_ledger.py
runtime/quality/ir_analytics_bridge.py
runtime/quality/joint_simulation_horizon.py
runtime/quality/memory_influence.py
runtime/quality/nl_replay_orchestration.py
runtime/quality/producer_pipeline.py
runtime/quality/production_data_contract_index.py
runtime/quality/promotion_sequence.py
runtime/quality/proving_ground/health_metric_governance.py
runtime/quality/replay.py
runtime/quality/rule_replay_engine.py
runtime/quality/soft_gate_telemetry.py
runtime/quality/workspace/foundry_consumption.py
runtime/quality/workspace/loop.py
scholar/_impl/evidence.py
scholar_requirement/_impl/compiler.py
scientist/cross_graph/conflict_materializer.py
scientist/evidence/claims/models.py
scientist/governance/continuous/detectors/common.py
scientist/governance/continuous/lifecycle_bridge.py
scientist/governance/continuous/reissue.py
scientist/governance/human_review/effectiveness.py
scientist/orchestration/memory/balanced.py
scientist/validation/citation_faithfulness.py
```

The sole collision is
`data_forge/domains/academic/batch/best_snapshot.py:291` and sibling uses of
`authoritative_for_runtime`. All paths in these lists are relative to
`src/polisyos/`.

### Complete direct-literal claim-subject census

The narrow 21-subject set is complete for direct, non-empty
`authoritative_for` tuple/list/set assignments. Repeated coordinates remain
visible:

| subject | source coordinates relative to `src/polisyos/` |
| --- | --- |
| `candidate_hypothesis` | `runtime/quality/hypothesis_ledger.py:80`; `scientist/policy_design/formulator.py:102` |
| `closeout_input_promotion_state_refs` | `runtime/quality/proving_ground/governed_promotion_gate.py:786` |
| `compilation_facets` | `core/contracts/runtime.py:365` |
| `future_policy_calibration` | `runtime/http/services/human_decision_contracts.py:758` |
| `g5_first_proving_ground_promotion_state_input_refs` | `runtime/quality/proving_ground/governed_promotion_gate.py:815` |
| `g5_input_promotion_state_refs` | `runtime/quality/proving_ground/governed_promotion_gate.py:786` |
| `layer3_g6_agent_orchestration_audit` | `runtime/quality/proving_ground/bounded_request_agent.py:643,655,666,687,758` |
| `layer3_g6_candidate_handoff_audit` | `runtime/quality/proving_ground/bounded_request_agent.py:521,534` |
| `layer3_g6_demand_pull_vs_abstention_reading` | `runtime/quality/proving_ground/bounded_request_agent.py:701` |
| `layer3_g6_prompt_tool_lineage` | `runtime/quality/proving_ground/bounded_request_agent.py:421` |
| `layer3_g7_region_widening_audit` | `runtime/quality/proving_ground/region_widening.py:868,899,915,933,949,986` |
| `layer3_g8_metric_governance_audit` | `runtime/quality/proving_ground/health_metric_governance.py:2153,2180` |
| `pareto_frontier_fact` | `foundry/welfare/frontier_emitter.py:143` |
| `participation_requirement` | `participation_requirement/__init__.py:115` |
| `pdc_graph_assembly_promotion_state_input_refs` | `runtime/quality/proving_ground/governed_promotion_gate.py:801` |
| `review_effectiveness_measurement` | `runtime/http/services/human_decision_contracts.py:758` |
| `reviewer_load_observability` | `runtime/http/services/human_decision_contracts.py:758` |
| `simulation_numerical_uncertainty` | `runtime/quality/joint_simulation_horizon.py:429` |
| `social_weight_provenance` | `foundry/welfare/social_weight_provenance.py:197` |
| `value_choice_record` | `foundry/welfare/frontier_emitter.py:217` |
| `welfare_tradeoff_audit` | `foundry/welfare/frontier_emitter.py:265` |

The wrapper-inclusive census adds exactly seven subjects and must be emitted by
the real compiler:

```text
conflict_materialization
public_revision_state
partial_publication_state
g2_forecast_support_binding_audit
grounded_forecast_handoff
w12d_forecast_support_gate
w12d_g3_analytics_search_gate
```

`may_not_use_for` has a separate 44-subject all-literal population. It is an
authority-boundary set, not another list of positive claims; the generator
retains it per source binding and never subtracts it from the denominator.

### Identity and custody findings

The ratified identity's binding anti-role paragraph at pinned lines 88-91
yields, in order:

1. administrator;
2. executor;
3. case-management system;
4. court;
5. notification channel;
6. payment system;
7. CRM.

The master plan names only the first six. `CRM` is an omission in the derivative
plan, not an alternative ratified count. DS11 derives seven from the authority
source and does not edit a second list.

There is real decision-validity machinery: decision packet creation registers a
validity envelope, invalidation events can re-evaluate and persist state, and
claim lifecycle vocabulary supports stale, superseded, reissued, and withdrawn.
That does not establish the universal custody promise. Scheduled monitoring is
persisted only as pending; no due-job executor was found; the rich lifecycle
bridge has definitions but no production caller in the complete source scan;
and the public signature population/surface belongs to DS12. Current state is
`producer_missing + implemented_but_not_orchestrated + bridge_missing +
surface_missing + semantic_test_missing`. The public row is `planned`.

## Register artifact and public-surface contract

### Strict artifact

The canonical type is `ClaimPostureRegisterV1`; the persisted schema name is
`policyos.trust.claim_posture_register.v1`. It contains:

- deterministic schema/rule versions, immutable slice-base ref, canonical
  source-set membership, and a digest over the exact admitted source bytes;
- both source-derivation receipts and complete denominator counts;
- normalized identity source digest, seven anti-role records, and source span;
- ordered source inventory rows, including combined-role, collision, and
  ambiguity rows;
- ordered subject rows with every source binding and forbidden purpose;
- effective `supported | planned | blocked` state plus all issue codes;
- source-as-of, review-on/review-due, and supersession time roles kept separate;
- methodology/envelope/limitation/accessibility/custody projection groups;
- PUBLIC, REVIEWER/EXPERT, and MACHINE audience fields; and
- a self-digest over the canonical payload projection.

The generator emits no current wall-clock timestamp and does not embed the Git
commit that would contain itself. Determinism comes from canonical source bytes,
explicit review dates, rule version, and immutable slice-base ref. A second
write from the same tree is byte-identical; committed-branch readback recomputes
the source-set digest and rejects any membership or content drift.

### Source adapters

The producer has three bounded source-document adapters:

1. all tracked `src/**/*.py` raw candidates, with no package/subject allowlist;
2. the ratified identity document, parsed through its frontmatter and binding
   sections; and
3. the accessibility evidence document, whose existing facts receive strict
   projection frontmatter without changing the dated body.

The current page-suite result is a fourth, result-only adapter:
`docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/receipt.json`,
content-bound to `run-1/results.json`, `.last-run.json`, and the before/after
environment tuple. The checker normalizes the complete Playwright JSON result
into test identity, outcome, issue signature, source commit, command, and
content digest; it rejects hand-authored status, partial test denominators,
missing raw provenance, or a receipt whose declared result differs from the
parsed run. It can support only the bounded historical statement "this complete
suite produced this result at this commit". It cannot certify current or
external conformance.

The ratified identity document is read-only: its existing owner, review,
authority bounds, decision status, seven anti-roles, and custody promise are the
source. No new `jurisdiction_neutral` declaration is inserted. The accessibility
document may receive projection-index frontmatter only where every value is
independently content-bound to its pre-existing “internal pre-audit / external
countersign pending”, assessment-owner, product-scope, and completion-date
spans. A newly inserted owner/review/jurisdiction/authority value with no such
basis remains `consumer_asserted` and blocks support.

### Supported entrypoints and CI

The single committed output is:

```text
apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json
```

`architecture/generated_artifacts.toml` registers it with
`lifecycle = "generated_committed"`, `stale_output_behavior = "fail"`,
`default_freshness_check = true`, and an `output_probe_command` that writes only
under `{output_root}`. The ordinary CI and release jobs already execute
`uv run polisyos-tools architecture guardrails check`; therefore no workflow
edit is needed. The DS11 checker owns a narrow
`--write-generated-reference` operation that imports the guardrail renderer and
writes only `docs/reference/generated-artifacts.md` from the manifest; it never
runs `guardrails sync` or touches public-surface/deep-import inventories. A
scratch-render comparison proves the narrow writer is byte-identical to the
guardrail checker expectation.

The public route fetches `/atlas/trust-claim-posture.v1.json`. It captures bytes
before parsing, validates strictly, and uses those bytes for MACHINE. This is the
declared outward surface. A Python facade or runtime HTTP endpoint would expand
authority/auth/OpenAPI/client scope and is rejected.

The route declaration is dashboard-native and executable:
`features/trust/routes.public.tsx` exports `trustRoute`; `APP_ROUTES` imports that
exact symbol; landing links `/trust`; and the complete `DASHBOARD_ROUTE_SURFACES`
test denominator derives the route and readiness witness. A focused contract
test breaks if any of those four consumers drift. The workspace-prefetch
`routeManifest.ts` is not used as a proxy declaration because the static route
has no prefetch contract.

## Exact free-growth falsifier

The decisive test is
`test_new_authority_producer_grows_register_without_register_edit`:

1. Copy only the canonical source inputs and producer/checker into a temporary
   repository root; hash the baseline register artifact, all source-policy
   inputs, and the complete dashboard production-source denominator.
2. Add one new module under an existing owned package. Its producer returns a
   strict record whose direct fields are
   `authoritative_for = ("ds11_free_growth_probe",)` and
   `may_not_use_for = ("publication_authority",)`; do not edit any register,
   source-policy, dashboard, route, or locale file.
3. Run the canonical producer with `--repo-root "$DS11_SCRATCH_ROOT"` and
   `--output-root "$DS11_OUTPUT_ROOT"`; the test creates both with `mktemp -d`
   and validates their resolved locations before use.
4. Independently run the tokenizer derivation. Both derivations must report raw
   denominator +1, exact-field denominator +1, declares +1, and subject +1.
5. Decode the generated artifact and assert exactly one new source row and one
   new subject binding with the real path/symbol/digest and forbidden purpose.
   Because review/jurisdiction/evidence metadata is absent, effective state must
   be `blocked`, never `supported`.
6. Assert the original register bytes, source-policy bytes, and dashboard
   production bytes are unchanged. The only produced difference is the scratch
   output. A fixture-only row, handwritten subject map, or frontend switch
   cannot satisfy the test.

A paired test adds the required producer metadata at the producer declaration,
not the register, and proves the row may advance only as far as its independently
established evidence permits. No test is allowed to make the probe supported by
self-attesting that evidence exists.

## Red-first semantic tests

All names are pinned in C00 before implementation:

```text
tests/unit/scientist/evidence/claims/test_posture.py::test_blocked_vetoes_planned_and_supported
tests/unit/scientist/evidence/claims/test_posture.py::test_candidate_or_planned_never_composes_to_supported
tests/unit/scientist/evidence/claims/test_posture.py::test_grounded_performance_requires_governed_evidence_and_prerequisite
tests/unit/scientist/evidence/claims/test_posture.py::test_posture_artifact_cannot_enter_runtime_claim_registry
tests/repo_quality/tools/test_trust_claim_posture.py::test_source_partition_matches_ast_and_tokenize_file_for_file
tests/repo_quality/tools/test_trust_claim_posture.py::test_new_authority_producer_grows_register_without_register_edit
tests/repo_quality/tools/test_trust_claim_posture.py::test_identity_parser_derives_seven_anti_roles_including_crm
tests/repo_quality/tools/test_trust_claim_posture.py::test_unbound_manages_your_cases_copy_fails_identity_check
tests/repo_quality/tools/test_trust_claim_posture.py::test_internal_a11y_evidence_cannot_mint_external_certification
tests/repo_quality/tools/test_trust_claim_posture.py::test_metadata_without_independent_source_basis_cannot_support
tests/repo_quality/tools/test_trust_claim_posture.py::test_declared_scope_assumption_is_limitation_not_support
tests/repo_quality/tools/test_trust_claim_posture.py::test_generator_is_byte_deterministic_and_scratch_bounded
tests/repo_quality/tools/test_trust_claim_posture.py::test_runtime_producer_evidence_binding_cannot_enter_posture_compiler
apps/runtime-dashboard/src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx
apps/runtime-dashboard/src/features/trust/export/trustPostureTwin.test.ts
apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.a11y.test.tsx
apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.route-contract.test.tsx
apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewAuthority.test.tsx
```

Negative mutations independently cover: `planned -> supported`, `candidate ->
supported`, forbidden purpose removed, review date refreshed without evidence,
source digest rebound to different content, source-body fact removed while new
frontmatter remains, declared scope assumption changed with support unchanged,
one anti-role removed, CRM omitted,
raw `manages your cases` JSX/translation, performance family relabeled,
limitation omitted, row reordered, MACHINE bytes reserialized, dynamic source
silently dropped, structural verification metadata forged, and runtime-new
dispute/status values.

## Clustered execution plan

Caps count unique production/tooling mechanism paths. Tests; this plan and
execution journal; generated JSON/reference output; source/result inventories;
frontend disposition/debt/ledger rows; snapshots; and tests that pin a moved
constant are mandatory P39 companions outside caps. They are still committed
with their mechanism. Never split one mechanism across commits to fit a cap.

The observed cluster caps total **30 unique mechanism paths**. The hard
slice-wide ceiling is **34 unique mechanism paths**; path 35 is a real stop.
Headroom is 4 paths (11.8%), derived from three compiler paths, two source/
lifecycle paths (one a11y source document and the load-bearing generated-
family manifest), thirteen public-route/locale seams, eleven measured Trust
View issuer/scanner/checker paths, and the debt-ledger checker required by
CC24—not copied from DS9 or DS10. The manifest is counted because it creates
the CI bridge; deterministic JSON, rendered references, registers, reports,
snapshots, and tests are P39 records produced by those mechanisms, not hidden
mechanism paths.

The cap has two derivations: table arithmetic and a parser that unions the
declared Add/Modify mechanism lists while excluding P39 companions. Both must
return 30 (`3 + 2 + 13 + 11 + 1`) and independently sum the consumed widening
budgets to 9; known mechanism member
`src/polisyos/scientist/evidence/claims/posture.py` and known widening member
C03's three rounds.

The widening ceiling is **9 rounds**, all consumed. A round
adds a capability, surface, producer arm, permission, or source family.
Narrowing is free: a change that only removes a way the system can be fooled is
pre-authorized and consumes no widening round. Repair review still records its
finding bucket and transaction.

A production path outside a cluster's declared list is pre-authorized only when
a named closure item requires it and no existing seam suffices. Before editing,
record the CC item, path, and rejected seam. The path still counts against the
cluster cap and 34-path ceiling. A second finding in one class invokes P40:
widen the mechanism to the needed quantity or declare a bounded residual and
run its falsifier; do not patch another instance.

| cluster | property | path cap | round budget |
| --- | --- | ---: | ---: |
| C00 | Admit the plan, remeasure complete sets, pin behavioral reds and inherited baseline red. | 0 mechanism | 1 transaction; 0 widening |
| C01 | Define the strict posture calculus, dual source derivations, producer, and checker. | 3 | 2 widening |
| C02 | Bind a11y source metadata, register the generated family, and persist deterministic posture bytes. | 2 | 2 widening |
| C03 | Render the public methodology/envelope/limitations/a11y/register route and exact-byte MACHINE twin. | 13 | 3 widening |
| C04 | Rebind the two inherited Trust View authority roots through private exhaustive issuers and their complete scanner/checker/schema denominator. | 11 | 2 repair rounds; 0 widening when narrowing-only |
| C05 | Reproduce generated bytes, add the generic producer-planning grammar and content-bound custody appointment source family, run the corruption wave, and reconcile the debt owner. | 1 | 1 regeneration transaction; 2 widening |
| C06 | Freeze, review, run targeted a11y/visual/release lanes, register debts, and read back closure. | 0 mechanism | 1 verification transaction; 0 widening |

### C00 — plan admission, censuses, and behavioral reds

**Mechanism cap:** 0. **Round:** one test/register transaction; no widening.

**P39 only:** this plan; execution journal
`docs/superpowers/journals/2026-08-26-ds11-trust-docs-posture.md`; red test
witnesses; debt-register/ledger rows required by explicit non-closures; and timing
receipts, including raw page-a11y output plus the later normalized companion at
`docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/receipt.json`. No
product contract, producer, source metadata, generated output, route, or
product/generated writer runs in C00. The debt-ledger writer is the sole record
writer: first measure its read-only report, freeze its ceiling, register every
explicit non-closure with owner/signal, then regenerate `LEDGER.md` under the
register-family lock.

The raw receipt set is exactly `run-1/results.json`, `run-1/.last-run.json`,
`environment-before.json`, and `environment-after.json` under that directory.
The Playwright JSON reporter and environment capture produce it; prose does not.

Re-run the two 104-file derivations, the 35/13/21 and 59/24/28 censuses, the
seven-role extraction, feature/status denominators, runtime-registry seam, and
custody production-call scan from the exact execution base. Pin every
disagreement as data. Capture the global frontend check's exact base stderr and
complete input denominator before DS11 touches Trust View. Run the complete
page-a11y suite with no product writer and bind its full 24-test denominator and
[DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4) before DS11 adds a
route.

**Acceptance:** CC01, CC02, and CC07 entry receipts reproduce; every named DS11
test is collected and red only for missing DS11 behavior; the release guardrail
is green; the one inherited C13 red and
[DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4) reproduce; the
debt-ledger check has zero DS11 missing/nonclosure/render-drift
findings after its writer; no product mechanism changed.

```bash
git status -sb
git symbolic-ref -q HEAD
git rev-parse --show-prefix
git merge-base --is-ancestor fd243d1ad HEAD
git merge-base --is-ancestor 176276ef0 HEAD
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check
corepack pnpm --filter @polisyos/runtime-dashboard run test:a11y:pages
uv run python tools/quality/validation/check_debt_ledger.py --write
uv run python tools/quality/validation/check_debt_ledger.py --check
uv run polisyos-tools architecture guardrails check
uv run pytest tests/unit/scientist/evidence/claims/test_posture.py tests/repo_quality/tools/test_trust_claim_posture.py -q
```

**Commit boundary:** `test(atlas): bind DS11 posture reds`.

### C01 — canonical contract, compiler, and authority calculus

**Mechanism cap:** 3. **Rounds:** at most 2 widening.

**Add:**

1. `src/polisyos/scientist/evidence/claims/posture.py`
2. `tools/quality/validation/trust_claim_posture_sources.py`
3. `tools/quality/validation/check_trust_claim_posture.py`

The model is strict and fully typed. The source compiler owns AST derivation;
the checker owns the independent tokenizer reconciliation, artifact validation,
identity/copy binding, deterministic writer, and `--check`. Public API export is
not added. Rule version changes are explicit and force regeneration.

**Acceptance:** CC03-CC09 and CC15-CC18 model/compiler negatives pass, including
both CC09 direction tests: `test_posture_artifact_cannot_enter_runtime_claim_registry`
and `test_runtime_producer_evidence_binding_cannot_enter_posture_compiler`.
Removing
the property while retaining markers fails: a constructor-only model, a literal
subject list, a row-count assertion, a self-attested verifier, or an authored
effective status cannot satisfy the tests. The first complete no-writer
compiler/checker run records its uptime pair and completed `user + sys`, fixing
the C02 writer ceiling before any artifact write.

```bash
uv run pytest tests/unit/scientist/evidence/claims/test_posture.py tests/repo_quality/tools/test_trust_claim_posture.py -q
.venv/bin/python -m ruff check src/polisyos/scientist/evidence/claims/posture.py tools/quality/validation/trust_claim_posture_sources.py tools/quality/validation/check_trust_claim_posture.py tests/unit/scientist/evidence/claims/test_posture.py tests/repo_quality/tools/test_trust_claim_posture.py
.venv/bin/python -m ruff format --check src/polisyos/scientist/evidence/claims/posture.py tools/quality/validation/trust_claim_posture_sources.py tools/quality/validation/check_trust_claim_posture.py tests/unit/scientist/evidence/claims/test_posture.py tests/repo_quality/tools/test_trust_claim_posture.py
```

**Commit boundary:** `feat(claims): compile typed trust posture`.

### C02 — source bindings, generated lifecycle, and honest opening rows

**Mechanism cap:** 2. **Rounds:** at most 2 widening.

**Modify:**

1. `docs/compliance/A11Y_AUDIT_2026Q2.md` — projection-index frontmatter only
2. `architecture/generated_artifacts.toml` — one surgically inserted family

The identity document is a read-only source. The a11y body hash is captured
before editing and must remain identical. Its frontmatter is candidate indexing:
each value must resolve to a pre-existing body span and establishment class;
metadata alone cannot make a gate green. No new identity, anti-role,
certification, performance, or custody implementation claim is added.

**P39 companions:** generated `docs/reference/generated-artifacts.md` and
`apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json`, plus the
content-bound page-a11y baseline receipt at
`docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/receipt.json`
consumed by the accessibility row.

Opening semantic rows are fixed by evidence, not target counts:

- system identity may be source-supported only within the ratified document's
  exact identity purpose and non-jurisdiction-specific bound;
- the universal custody promise is `planned`, never supported;
- the 2026-Q2 internal pre-audit completion is eligible only as the narrow
  historical fact content-bound to its dated body spans; any unsupported
  owner/review/jurisdiction predicate blocks it;
- current accessibility conformance is `blocked` by
  [DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4); external
  certification is separately `blocked` pending a content-bound countersign;
  and
- source declarations missing claim-specific review, jurisdiction, or evidence
  are visible and blocked rather than omitted.

**Acceptance:** CC10, CC13, and CC14 pass; two writes are byte-identical; output
probe writes only to scratch; source-body bytes are unchanged; no grounded-
performance row is supported; the generated family is part of the default CI
freshness set without a workflow edit; changing the a11y body fact while keeping
new frontmatter intact removes support; the narrow generated-reference writer
changes no other guardrail inventory.

```bash
uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --write --write-generated-reference
uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check
uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check-a11y-receipt
uv run polisyos-tools architecture guardrails check
```

**Commit boundary:** `feat(atlas): generate honest claim posture`.

### C03 — public posture route and exact-byte MACHINE twin

**Mechanism cap:** 13. **Rounds:** at most 3 widening.

**Add:**

1. `apps/runtime-dashboard/src/features/trust/index.ts`
2. `apps/runtime-dashboard/src/features/trust/routes.public.tsx`
3. `apps/runtime-dashboard/src/features/trust/domain/posture.ts`
4. `apps/runtime-dashboard/src/features/trust/domain/loadPosture.ts`
5. `apps/runtime-dashboard/src/features/trust/components/ClaimPostureRegister.tsx`
6. `apps/runtime-dashboard/src/features/trust/components/PostureMethodology.tsx`
7. `apps/runtime-dashboard/src/features/trust/components/AccessibilityEvidence.tsx`
8. `apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.tsx`
9. `apps/runtime-dashboard/src/features/trust/export/trustPostureTwin.ts`

**Modify:**

10. `apps/runtime-dashboard/src/app/routes/routes.tsx`
11. `apps/runtime-dashboard/src/features/landing/routes/LandingPage.tsx`
12. `apps/runtime-dashboard/src/shared/i18n/locales/en.json`
13. `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`

No new `ru` keys: Russian remains `legacy_continuity_frozen`. Claim-bearing
subjects/statuses/limitations come from the artifact; locale files own only
closed interface labels and frames. `/trust` is public and static; it never
calls a protected runtime API or stores claim state client-side.

**P39 companions:** focused route/component/a11y/free-growth/twin tests, public
route visual helper, `apps/runtime-dashboard/e2e/ds11-runtime-dashboard.visual.spec.ts`
and its own snapshots (test title contains `DS11 trust posture`; no visual config edit),
and the complete browser denominator in
`apps/runtime-dashboard/e2e/helpers/runtime-dashboard.ts`. That helper adds the
`trust` readiness key, `trust-posture-page` test ID, and `/trust` surface; it is a
test-denominator companion, not product routing. `routeManifest.ts` remains
untouched because it is only the workspace-prefetch manifest and `/trust` has no
prefetch contract. If implementation proves otherwise, CC19 names it as a path
exception before editing.

**Acceptance:** CC11, CC12, CC19, CC20, and CC22 pass. PUBLIC defaults to
limitations and status; REVIEWER/EXPERT exposes all source/evidence detail;
MACHINE returns exact bytes. Removing, reordering, relabeling, or hiding one row
fails DOM parity. Loading/parsing failure renders explicit unavailable posture.
`trustRoute` is imported into `APP_ROUTES`, linked from landing, and appears
exactly once in the complete page-a11y inventory; the added route scan passes.

```bash
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run \
  src/features/trust/domain/posture.test.ts \
  src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx \
  src/features/trust/routes/TrustPosturePage.test.tsx \
  src/features/trust/routes/TrustPosturePage.a11y.test.tsx \
  src/features/trust/routes/TrustPosturePage.route-contract.test.tsx \
  src/features/trust/export/trustPostureTwin.test.ts
corepack pnpm --filter @polisyos/runtime-dashboard exec tsc -p tsconfig.app.json --noEmit
```

**Commit boundary:** `feat(atlas): render trust posture and machine twin`.

### C04 — Trust View private issuer repair

**Mechanism cap:** 11. **Rounds:** at most 2 repair rounds; narrowing consumes no
widening round.

The exhaustive two-root denominator is
`authority-presentation-prop-dispute-status` and
`authority-presentation-prop-verification-status-icon-tone`, independently
derived from the disposition register and checker descriptor map in the entry
census. No third DS11 Trust View authority root is silently excluded.

**Modify:**

1. `apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts`
2. `apps/runtime-dashboard/src/shared/ui/trust-view/DisputeBadge.tsx`
3. `apps/runtime-dashboard/src/shared/ui/trust-view/VerificationStatus.tsx`
4. `apps/runtime-dashboard/src/shared/ui/trust-view/TrustInspector.tsx`
5. `apps/runtime-dashboard/src/shared/ui/trust-view/TrustMetadata.tsx`
6. `apps/runtime-dashboard/src/shared/ui/trust-view/index.ts`
7. `apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewBadge.tsx`
8. `apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx`
9. `architecture/atlas_surfaces/status_retirement_scan.mjs`
10. `architecture/atlas_surfaces/check_frontend_disposition_register.py`
11. `architecture/atlas_surfaces/frontend-disposition-register.schema.json`

Two independent derivations agree on the eight dashboard production mechanisms
over the complete **625-file** dashboard production denominator (**304 `.ts`**
and **321 `.tsx`**). The three architecture scanner/checker/schema paths close
CC21's governed validation denominator, producing the declared eleven-path C04
mechanism set. A disagreeing scout set proposed `HashChip.tsx` and
`TrustViewBridge.tsx`; both are transports rather than clothing/issuer
mechanisms and are explicitly excluded rather than silently substituted.

One private issuer consumes the canonical runtime `VerificationMetadata`
contract owned at `src/polisyos/core/contracts/runtime.py`, transported through
the existing OpenAPI-generated runtime client, and returns an exhaustive
presentation union. It does **not** consume the DS11 posture artifact. The
issuer recomputes clothing from the closed verification/dispute/freshness
values plus the required verifier/hash/method facts: disputed/under-review
vetoes positive clothing, stale is distinct, absent/incomplete is unknown, and
wire-time novelty is `unrecognized`. Components accept the issued presentation,
not an open tone, raw status string, or shape-only `VerificationMetadata`.
Structural field presence remains transport evidence, not authority.

**P39 companions:** focused Trust View tests plus the surgical DS11 frontend-
disposition transition, report, debt ledger, and any moved denominator test.
Hold the register lock. The writer must update only the two DS11 finding IDs and
preserve every other byte/row. Because the whole checker has the pinned C13 red,
the DS11 receipt is targeted semantic tests plus exact error-set non-growth.

**Acceptance:** CC21 passes; both DS11 roots have content-bound private issuers
and novelty negatives; the final whole-check stderr equals the C00 single-error
baseline; no DS6 evidence is edited or reissued.

```bash
.venv/bin/python -m pytest \
  tests/unit/scientist/evidence/claims/test_posture.py \
  tests/repo_quality/tools/test_trust_claim_posture.py -q
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run \
  src/shared/ui/trust-view/DisputeBadge.a11y.test.tsx \
  src/shared/ui/trust-view/VerificationStatus.a11y.test.tsx \
  src/shared/ui/trust-view/TrustInspector.test.tsx \
  src/shared/ui/trust-view/TrustViewAuthority.test.tsx \
  src/shared/ui/trust-view/trustViewArchitecture.test.ts
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check
```

**Commit boundary:** `refactor(atlas): issue trust presentation privately`.

### C05 — deterministic regeneration and corruption wave

**Mechanism cap:** 1. **Rounds:** one regeneration transaction plus two
widening rounds. Round 8 buys the generic producer-local planned/candidate
grammar; round 9 buys the DEBT-register custody appointment source family.

**Modify:**

1. `tools/quality/validation/check_debt_ledger.py` — CC24's measured debt-row
   denominator owner; the stale pinned count could not be closed through the
   posture producer or generated record.

Freeze all source. Under the generated-artifact token, generate into two fresh
scratch roots and compare every byte with the committed output. Run the AST and
tokenizer derivations separately. Then run every named corruption, including the
two master-plan negatives and the free-growth witness. No later source review
lands after this wave; a blocking review finding is batched before rerun.

**Acceptance:** CC06, CC10, CC16-CC18, and CC20 pass; all corruptions are rejected
for their semantic reason; no source/output probe escapes scratch; the committed
artifact is reproduced byte-for-byte.

```bash
uv run pytest tests/unit/scientist/evidence/claims/test_posture.py tests/repo_quality/tools/test_trust_claim_posture.py -q
uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check --corruption-probes
uv run polisyos-tools architecture guardrails check
```

**Commit boundary:** `test(atlas): prove posture growth and authority bounds`.

### C06 — freeze, targeted verification, debt, and readback

**Mechanism cap:** 0. **Round:** one verification transaction; no widening.

Run delta-only code review after the C05 source freeze. Serialize the focused
browser/a11y/visual transaction. Run no full backend or dashboard suite. Verify
the changed modules plus importers, strict generator, read-only architecture
guardrail, `ruff`, focused TypeScript/Vitest, and exactly the DS11 visual grep.
One writer run may update DS11 snapshots; two following no-writer runs must
agree with zero retries and one worker.

Reconcile every C00 debt row's still-open/closed state with owner and executable
signal, regenerate the ledger through its writer, verify the global frontend
error-set delta and complete page-a11y error-set delta, and read the committed
branch—not the index—back after the C06 commit.

**Acceptance:** CC23-CC24 pass; actual unique mechanisms <=34, widening <=9;
every non-closure below is still precise; `git diff --check` passes; attached
branch readback contains the plan, receipts, generated artifact, and no
unrelated changes. The page suite is exactly 25 collected / 22 pass / 3 current
failures, all within the historical
[DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4); the fourth base
identity does not reproduce. It has no DS11 route failure and its denominator is
increased by the one derived, passing `/trust` surface. This measured correction
does not reissue the historical current-conformance evidence.

```bash
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run \
  src/features/trust/domain/posture.test.ts \
  src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx \
  src/features/trust/routes/TrustPosturePage.test.tsx \
  src/features/trust/routes/TrustPosturePage.a11y.test.tsx \
  src/features/trust/routes/TrustPosturePage.route-contract.test.tsx \
  src/features/trust/export/trustPostureTwin.test.ts \
  src/shared/ui/trust-view/DisputeBadge.a11y.test.tsx \
  src/shared/ui/trust-view/VerificationStatus.a11y.test.tsx \
  src/shared/ui/trust-view/TrustInspector.test.tsx \
  src/shared/ui/trust-view/TrustViewAuthority.test.tsx \
  src/shared/ui/trust-view/trustViewArchitecture.test.ts
corepack pnpm --filter @polisyos/runtime-dashboard exec tsc -p tsconfig.app.json --noEmit
corepack pnpm --filter @polisyos/runtime-dashboard run test:a11y:pages
.venv/bin/python -m ruff check \
  src/polisyos/scientist/evidence/claims/posture.py \
  tools/quality/validation/trust_claim_posture_sources.py \
  tools/quality/validation/check_trust_claim_posture.py \
  tools/quality/validation/check_debt_ledger.py \
  tests/unit/scientist/evidence/claims/test_posture.py \
  tests/repo_quality/tools/test_trust_claim_posture.py \
  tests/repo_quality/tools/test_debt_ledger_checker.py
.venv/bin/python -m ruff format --check \
  src/polisyos/scientist/evidence/claims/posture.py \
  tools/quality/validation/trust_claim_posture_sources.py \
  tools/quality/validation/check_trust_claim_posture.py \
  tools/quality/validation/check_debt_ledger.py \
  tests/unit/scientist/evidence/claims/test_posture.py \
  tests/repo_quality/tools/test_trust_claim_posture.py \
  tests/repo_quality/tools/test_debt_ledger_checker.py
uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check
uv run python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check-a11y-receipt
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check
uv run python tools/quality/validation/check_debt_ledger.py --write
uv run python tools/quality/validation/check_debt_ledger.py --check
uv run polisyos-tools architecture guardrails check
git diff --check
git status -sb
git symbolic-ref -q HEAD
git rev-parse --show-prefix
```

**Commit boundary:** `docs(atlas): close DS11 trust posture`.

## Serialized resources and fixed ceilings

| resource | cluster / ceiling and evidence |
| --- | --- |
| generated-artifact token | C02 and C05 as separate acquisitions; C01 first completes the exact no-writer compiler/checker with an uptime pair, then freezes `max(30s, 2x completed user+sys)` before C02's manifest/artifact/reference writer; no manifest/output writer overlaps register or visuals |
| register-family lock | C00 debt-ledger admission, C04 disposition transition, and C06 reconciliation are separate acquisitions; completed read-only debt reporting `user+sys=0.70s` -> fixed **30s** for its record writer/check; completed frontend transaction `user 195.14 + sys 27.53 = 222.67s` -> fixed **445.34s** for no-corruption checks; a surgical disposition writer/corruption transaction freezes at `max(445.34s, 2x first completed user+sys)` and never widens mid-run |
| focused dashboard | ordinary lane; the 4-file Trust View entry baseline was `user+sys=9.04s`. The first completed 11-file C06 wave measured `87.32 + 8.26 = 95.58s` and failed only because the exhaustive MACHINE-twin case crossed its unmeasured 30s internal wall timeout at 31.16s; its isolated semantic replay passed in 21.68s. The complete-set operational ceiling is therefore fixed at **191.16s user+sys** (`2 × 95.58`), while that one test carries a **60s internal completion timeout**, not a semantic or resource-budget predicate. The unchanged intermediate replay passed 73/73 at `86.77 + 8.25 = 95.02s`; the final source-frozen wave passed **92/92** at `57.31 + 5.89 = 63.20s`. |
| release guardrail | ordinary read-only closeout lane; completed `user+sys=80.65s` -> fixed **180s**; no `sync` |
| visual/a11y lane | Semantic/result agreement for replay B remains `consumer_asserted` / `not_established` and cannot support a semantic product gate or posture row. Separately, the completed-process `user+sys` ceiling is a **recomputed operational-resource predicate**: `/usr/bin/time -p` supplied `user` and `sys` for each completed invocation, and the harness recomputes `2 × max(241.97, 327.64) = 655.28s`. It may set only this harness timeout/stop budget; it cannot support product semantics, posture, certification, or any other semantic gate. C03 route a11y is focused. The C06 visual transaction uses one worker and zero retries; its predeclared **60s** floor remained the numeric ceiling because writer and both no-writer receipts each used less than 9s `user+sys`. The writer preceded the first no-writer measurement, contrary to the prose order, and that ordering mismatch is recorded rather than treated as semantic evidence. A post-freeze `/trust` axe run exposed the unrelated 60s Playwright per-test completion timeout; the test-only companion now allows 120s while preserving the exact axe assertion and the 655.28s suite CPU ceiling. Missing browser/killed run is a tooling non-receipt. |

The visual commands differ only by the first writer flag and use the exact grep:

```bash
CI=1 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 PLAYWRIGHT_RETRIES=0 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS11 trust posture' --workers=1 --update-snapshots
CI=1 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 PLAYWRIGHT_RETRIES=0 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS11 trust posture' --workers=1
CI=1 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 PLAYWRIGHT_RETRIES=0 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS11 trust posture' --workers=1
```

## File map

| role | planned home |
| --- | --- |
| strict artifact/status calculus | `scientist/evidence/claims/posture.py` |
| complete source compiler | `tools/quality/validation/trust_claim_posture_sources.py` |
| writer/checker/identity reconciliation | `tools/quality/validation/check_trust_claim_posture.py` |
| persisted public artifact | `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json` |
| generated lifecycle / CI bridge | `architecture/generated_artifacts.toml` default freshness family |
| frontend validation/byte capture | `features/trust/domain/posture.ts`, `loadPosture.ts` |
| human surface | `features/trust/routes/TrustPosturePage.tsx` and three bounded components |
| MACHINE / DOM parity | `features/trust/export/trustPostureTwin.ts` |
| public route | standalone `/trust`, linked from landing; no runtime API |
| Trust View narrowing | private issuer in `trust-glyphs.ts`, five measured consumers/components |
| governance | DS11 plan/journal, generated family, frontend register/report, debt/ledger |

## Issue codes

| code | meaning |
| --- | --- |
| `DS11-SOURCE-DERIVATION-DISAGREEMENT` | AST/tokenizer file role or subject differs; emit ambiguous and block |
| `DS11-SOURCE-RUNTIME-BOUND` | declaration exists but static subject/value cannot be proven |
| `DS11-SOURCE-COLLISION` | raw substring is a different field, such as `authoritative_for_runtime` |
| `DS11-OWNER-NOT-ESTABLISHED` | no canonical package/document claim owner resolves |
| `DS11-JURISDICTION-NOT-ESTABLISHED` | claim applicability is unknown; no inferred concrete scope |
| `DS11-GATE-PREDICATE-NOT-ESTABLISHED` | a support predicate is asserted/supplied but not recomputed or independently reconciled |
| `DS11-REVIEW-MISSING` / `DS11-REVIEW-STALE` | review predicate absent or expired |
| `DS11-AUTHORITY-PURPOSE-DENIED` | requested public use absent from `authoritative_for` or present in `may_not_use_for` |
| `DS11-STATUS-UPGRADE` | candidate/planned/blocked transported or rendered as supported |
| `DS11-IDENTITY-COPY-UNBOUND` | capability copy lacks a content-bound admitted source row |
| `DS11-IDENTITY-ANTI-ROLE-DRIFT` | ratified seven-role set omitted, changed, or hand-enumerated downstream |
| `DS11-PERFORMANCE-NOT-EARNED` | grounded-performance support attempted without governed producer/prerequisite |
| `DS11-A11Y-CERTIFICATION-NOT-EARNED` | internal/historical evidence projected as external/current certification |
| `DS11-CUSTODY-WATCHER-NOT-ESTABLISHED` | universal watcher promise lacks scheduled producer/orchestrated bridge/public population |
| `DS11-MACHINE-BYTE-DRIFT` / `DS11-DOM-PARITY-DRIFT` | download differs from captured bytes or DOM loses ordered truth |
| `DS11-GENERATOR-ESCAPE` / `DS11-GENERATED-DRIFT` | scratch producer writes outside output root or committed bytes are stale |
| `DS11-TRUST-PRESENTATION-FORGERY` | raw/open structural metadata issues trusted clothing |

## Pattern pass and capability state

Read the failure/repair register again before C00 and C06 closeout.

| patterns | opening anti-pattern | target pattern and acceptance signal |
| --- | --- | --- |
| P01/P02/P03/P12 | declarations and docs exist without producer -> persisted artifact -> bridge -> public/MACHINE consumer | strict compiler -> committed deterministic JSON -> static loader -> `/trust` + exact twin -> semantic negatives |
| P04/P05/P09/P15 | planned/candidate/blocked or copy can be relabeled as support | fail-closed effective-state calculus; source status survives every projection; mixed veto tests |
| P07/P08 | source-as-of, review date, validity, and supersession can collapse | separate time roles, rule version, content digest, deterministic replay |
| P10/P29/P32 | field presence, shape, keyword, or self-attestation used as evidence | resolve + content-bind + verifier provenance; behavior removed while markers remain must fail |
| P27/P31 | central claim map or per-copy patch duplicates distributed owners | open source walk plus one generic renderer/checker; no claim-ID enumeration |
| P35/P36 | loose 104 grep, 16/29 dashboard counts, or adjacent prose becomes authority | complete denominators, two methods, known member, exact source ID/section |
| P37/P38 | authored status, pending job, package owner, or keyword blacklist stands in for the guarded property | independently established predicate labels; blocked unknowns; structural no-free-copy boundary with declared residual |
| P33/P34 | tests teach to two named phrases or exclude a failing source without finishing isolation | synonym/indirect/default/dynamic/sibling mutations; scratch free growth; complete error-set comparison |
| P39 | budget counts mandatory plan/tests/generated/register companions | 30 mechanisms, companions outside, one mechanism never split |
| P40/P41 | repeat instance repairs or export the base C13 red as DS11 debt | bucket second finding; exact-base replay plus final error-set delta and changed-input accounting |

Target closure state is `typed contract + source-derived producer + persisted
generated artifact + CI/static bridge + public and MACHINE consumers +
verification + negative/e2e semantic test`. The custody watcher, typed scope
adjudication, external accessibility countersign, DS12 publication, and general
website-copy semantics remain precisely non-closed.

## Explicit non-closure

- `DS11-PUBLISHED-SIGNATURE-WATCHER` — `producer_missing`; `team-runtime`,
  producer lane `runtime/quality`; closure signal:
  `uv run pytest tests/integration/runtime_quality/test_published_signature_custody.py::test_every_public_signature_is_watched_for_staleness -q`.
- `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` —
  `implemented_but_not_orchestrated + bridge_missing`; `team-scientist` with
  runtime orchestration consumer; closure signal:
  `uv run pytest tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit -q`.
- `DS11-PUBLIC-SIGNATURE-POPULATION` — `surface_missing`, owned by DS12 /
  `team-design`; DS11 creates no substitute; closure signal:
  `uv run pytest tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound -q` after DS12's independent promotion gate.
- `DS11-SCOPE-ADJUDICATION-RECORD` — `absent/unallocated`; the ratified document
  owns the rule but no typed artifact/producer/bridge exists; owner allocation is
  `team-architecture`; closure signal:
  `uv run pytest tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific -q`.
- `DS11-EXTERNAL-A11Y-COUNTERSIGN` — `artifact_missing + verification_missing`;
  `team-design` accessibility evidence lane; closure signal:
  `uv run pytest tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact -q`.
- `DS11-CURRENT-PAGE-A11Y` — base-proven `verification_missing`: the complete
  page suite is 20/24, with
  [DS11-A11Y-BASE-FAILURE-SET-4](#ds11-a11y-base-failure-set-4) in the run
  paper. Two exact current-branch no-writer executions are 22/25 with three
  members of that base set; missing `Open run` does not reproduce, while the
  added `/trust passes axe` identity passes. This disagreement is recorded, not
  promoted into a current-conformance reissue; `team-design` run-paper/a11y
  lane; closure signal: two independent no-writer invocations of
  `corepack pnpm --filter @polisyos/runtime-dashboard run test:a11y:pages` exit
  zero with identical collected identities and reissue the content-bound
  current-conformance receipt.
- `DS11-GENERAL-COPY-SEMANTICS` — bounded residual: the structural checker owns
  the `/trust` feature and landing entry, not arbitrary future public copy;
  `team-design`; closure signal:
  `uv run pytest tests/repo_quality/frontend/test_public_claim_copy_inventory.py::test_every_public_capability_assertion_resolves_to_claim_posture -q`.
- `DS11-GROUNDED-PERFORMANCE` — intentionally blocked/out of DS11; runtime/GY
  evidence owner plus DS12 consumer; closure signal:
  `uv run pytest tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence -q` and DS12 still decides publication.
- `DS11-INHERITED-C13-PRINT-RECEIPT` — base-proven
  `verification_missing`, not DS11-owned; DS6 independent print-evidence lane;
  closure signal:
  `uv run pytest architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes -q` followed by the global frontend disposition `--check`.
- `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` — retained v7 plan material is a source
  inventory, not DS11 execution authority; security certifications, procurement
  downloads, telemetry/status, forms, sandbox, calculators, and general docs are
  `surface_out_of_scope`; `team-design` successor allocation; closure signal:
  `uv run pytest tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract -q`.

An absent future test file is `artifact_missing`, never a green receipt. C00
registers every declared non-closure; C06 reconciles each still-open or closed
state in `DEBT-REGISTER.md` before claiming closure.

## Commit sequence

| boundary | message |
| --- | --- |
| planning hand-back | `docs(atlas): plan DS11 trust posture` |
| C00 | `test(atlas): bind DS11 posture reds` |
| C01 | `feat(claims): compile typed trust posture` |
| C02 | `feat(atlas): generate honest claim posture` |
| C03 | `feat(atlas): render trust posture and machine twin` |
| C04 | `refactor(atlas): issue trust presentation privately` |
| C05 | `test(atlas): prove posture growth and authority bounds` |
| C06 | `docs(atlas): close DS11 trust posture` |

Before every commit: `git status -sb`, `git symbolic-ref -q HEAD`, prefix,
exact dirty-path read, cap/round receipt. History is append-only. No merge, push,
rebase, reset, stash storage, or unrelated cleanup.

## Hand-off packet

The executor receives: approved plan commit; exact base/prefix/gates; both
complete 104-file derivations and role sets; direct 21 and wrapper-inclusive 28
subject maps; 116 forbidden-boundary denominator; identity digest and derived
seven anti-roles; the master-plan six-vs-seven discrepancy; the distinct
`RuntimeClaimRegistry` ruling; four-way scope ruling; custody watcher/bridge
call census; feature/status/checker disagreements; red test identities; exact
free-growth scratch recipe; schema/rule/source digests; generated artifact and
raw/DOM/MACHINE hashes; source-body preservation hashes; path/round totals;
serialized-resource user+sys/uptime receipts; debt transitions; and committed-
branch readback.

Anything that adds a runtime endpoint, auth exception, OpenAPI/client ABI,
Python public facade, public signature, performance claim, scope-adjudication
contract, arbitrary copy channel, new source family, or raises the 34-path /
9-widening-round ceilings requires an owner-approved plan amendment before code.

## Non-negotiables

- Source declaration and evidence can authorize a claim; a register, dashboard,
  document projection, translation, LLM, or export cannot.
- `planned`, `candidate`, `blocked`, `unknown`, `stale`, and `contested` never
  compose to `supported`.
- Mostly negative posture is correct at DS11 entry and close; no positivity
  target exists.
- The seven anti-roles come from the ratified identity, including CRM.
- The custody promise stays planned until an autonomous watcher, orchestrated
  lifecycle bridge, and public signature population are evidenced.
- A new producer grows the register with zero register/dashboard/locale edit;
  missing metadata grows a blocked row, not an omission.
- Internal automated accessibility evidence is not external certification.
- MACHINE is the exact captured artifact bytes and the DOM loses no limitation.
- `/trust` and the registered generated artifact are the supported entrypoints;
  routing through an undeclared facade is not support.
- No grounded-performance claim, DS12 promotion/publication work, general trust
  center, CRM/case function, `guardrails sync`, full-suite substitution,
  unmeasured ceiling widening, hand-edited generated output, or unreported path.
