# Basis-grade carriers: stopped investigation and GY research task

Date: 2026-09-05. Branch: `codex/research-basis-grade-carriers`.
Source examined: `edcad691c3fc0e055338898fb3cc456592b9b962`.
Disposition: **STOP — the semantic carrier denominator is not established.**
This is an investigation record, not a ratification, implementation specification,
completed carrier census, or debt closure.

## Decision for the architect

The lexical counts reproduce. They do **not** establish that carrier types almost
never represent a value's standing. `AuthorityBoundary` deliberately separates
`DecisionGrade` from `EvidenceBasis`; the newer
`VersionedClaimVocabularyEnvelope` also carries a numeric value beside an explicit
candidate/absence status. Conversely, neither a grade string nor a bundle of refs
authenticates its own basis. `AdmittedClaimAdjudicationBatch` already declares
`admission_predicate="independently_reconciled"`, which is precisely the declaration
the forgeable-chain debt says cannot be trusted.

The seven leads do not describe seven identical current representation gaps.
The runner's limitation is already enforced as an explicit intake-only attestation
scope. C13's register row records a completed receipt reissue and a subsequent
schema reconciliation blocker. These are material corrections to the motivating
description, not reasons to close either row.

**The stronger hypothesis is neither established nor refuted.** There remain concrete
representation defects, notably the parameter omission/judgment collision and the
unmarked historical confidence described by its owning debt. There is no evidence
here that the carriers already express the entire ratified vocabulary, nor that the
seven debts are all unrelated. The hypothesis-refutation stop therefore does not fire.

The **census stop** does fire: the investigation reconciled file and Python
declaration sets, but did not derive and independently reconcile the complete set
of values at persistence and authority-projection boundaries. Substituting the
seven leads, symbol matches, annotated classes, or a public-schema inventory for
that set would be sampling or a proxy denominator. This is a limitation of this
investigation, not a claim that an exhaustive census is inherently impossible.

Only the research prerequisite `GY-BG0` below is ready to transcribe. A sized
carrier implementation task, a complete expressiveness matrix, and the number of
implementations are **withheld**. The material below preserves findings useful to
the resumed investigation without presenting its lead list as the missing census.

## Constitutional boundary

The reading applied here is the base pair, grounded claim with delta and honest
refusal, plus declared unknown and custody without a number. This wording avoids
reconciling inconsistent historical shorthand by inventing a fifth entry.

- **`S0-K06`, binding application note:** unknown scope limits the affected
  authority claim, protected action, or custody fact; candidate computation may
  continue with an explicit limitation. Its ratification expressly does not
  prescribe one persisted header or gate sequence.
- **`INT-K06`:** a bounded, falsifiable procedural custody claim may carry no
  statistical risk number. **`INT-K08`:** negative completion remains a valid
  governed result; a negative alone does not establish that refusal is substantively
  correct.
- **`W5-K04` and the wave-5 ratification §8:** a protective response with unresolved
  diagnosis is a composition of existing kinds. The 2026-08-30 ruling leaves the
  constitutional trigger armed. A newly necessary kind would require stopping for
  the consolidated constitutional question.
- **Identity decision §9 items 5–6:** institutional absence leaves the signature
  slot empty; it does not defer building or demonstrating the mechanism. Types and
  pure verification do not acquire an institutional appointment requirement.

Owners: [S0 ratification](../../system-design-decisions/stage0-custody-kernel-ratification.md),
[INT ratification](../../system-design-decisions/int-wave-claim-semantics-ratification.md),
[wave-5 ratification](../../system-design-decisions/wave5-evidence-substitution-ratification.md),
[identity decision](../../system-design-decisions/policyos-identity-and-custody-boundary.md).
The INT §8 forward note and wave-5 §8 ruling were read twice before writing this
record. No fifth kind was found or proposed. Candidate/absent supply status,
currentness, provenance, and decision admissibility are axes of a representation,
not additional constitutional outcomes.

## BG-F01 — measured denominators, and the denominator still missing

Measurements below are at the pinned source, before adding this document. The
complete path lists were walked by script; no truncated search result supplies a
count. Appendix A gives the reproducer.

| Set and file-type denominator | Measurement | Cross-check | What it establishes |
| --- | ---: | --- | --- |
| Entire Git tree, every tracked file type | 10,550 paths | Product subtree plus 22 paths outside it | Repository scope only |
| `policy-engine/`, every tracked file type | 10,528 paths | Git index versus committed tree: both directional differences empty | The product file set was complete and clean |
| `policy-engine/src/`, every tracked file type | 2,829 files | Independent filesystem walk: identical path set, excluding Python cache files | Complete source-file coverage for the lexical scan |
| `policy-engine/src/**/*.py` | 2,619 files | Filesystem-derived `.py` subset; zero AST parse failures | Python syntax was inspectable throughout this set |
| Classes with direct simple-name annotated assignments in those 2,619 `.py` files | 7,028 classes | `ast.walk` and an explicit child-stack traversal agree | A syntactic declaration population, including classes other than DTOs |
| Direct simple-name annotated assignments in those classes | 52,666 declarations | Both traversals agree | Not inherited fields, semantic values, or persistence boundaries |
| Those annotations containing an AST `Name` equal to `Any` | 2,477 declarations | Complete annotation walk | A syntax fact, not a count of unsafe or authority-bearing values |
| **Semantic carriers in the user's requested classes** | **`not_established`** | **No independent membership reconciliation obtained** | **Cannot support coverage or contract-change totals** |

The two AST traversals share a parser and definition of a declaration. Their
agreement is a traversal check, **not** independent evidence of semantic membership.
The file-set cross-check also proves nothing about whether a value reaches an
authority consumer. That distinction is the reason for the stop.

Two relevant existing inventories were inspected in full as structured arrays:

| Existing inventory | Enumerated population | Why it cannot replace the requested denominator |
| --- | --- | --- |
| `architecture/policy_design_case/layer3_gy_authority_candidate_inventory.json` | 406 `rows`; all `status_text` values are `pass` | Candidate-positive occurrences in named audit artifacts, not all persisted numbers, evidence fields, receipts, or projections |
| `architecture/atlas_surfaces/status-retirement-inventory.json` | 47 `entries`, separate from its 59 `semantic_exemptions` | Historical DS1 status-definition retirement identities; its own authority scope excludes inventing runtime authority and treating scanner findings as runtime authority |

Neither population is claimed fresh by executing its owner validator here. Their
array contents and declared scope are the evidence; their counts are not added to
the Python counts. They use different units and can overlap.

The missing semantic step is concrete. For example:

- `ir/artifacts/io.py:24` accepts `payload: Any` and caller-supplied schema name and
  version in `put_json_artifact`; `get_json_artifact` returns `Any`. Counting model
  fields therefore omits some payload structures; counting that function once
  merges distinct contracts and their consumers.
- `ir/analytics/evidence_bundle.py:238` persists an `EvidenceBundle` containing
  `diagnostic_scores: dict[str, float]`, string identification status, and nested
  dictionary payloads for estimands, dashboards, and reports. Its docstrings name
  downstream reconstruction types. Those links must be followed; an `Any` match
  neither proves absence of a typed owner nor establishes its expressiveness.
- `scientist/publishing/publisher.py:87` has a `DecisionGradeExport` whose
  `payload` is `dict[str, Any]`, with consumer-specific validation of trust and
  current-head material. The class name is not the `DecisionGrade` literal, and
  its field declarations do not enumerate its exported claim shapes.
- SKG confidence lives in SQL declarations inside a Python string; the GY task
  standing lives in Markdown table cells; public verification uses a TypeScript
  discriminated union and route consumer. None is counted as an annotated Python
  class merely because the enclosing file was scanned.

An exhaustive continuation must reconcile **producer/persistence discovery with
consumer/projection discovery**, explicitly resolve these representations and
their ownership links, and record exclusions by purpose. That work was not
completed. There is no denominator-sized per-carrier table in this document.

## BG-F02 — re-derived lexical hypothesis

Case-sensitive substring matching over every file in `src/**/*.py` gives:

| Token | Matching files out of 2,619 | Independent `rg -l -F` path-set check |
| --- | ---: | --- |
| `basis_grade` | 0 | Equal |
| `evidence_grade` | 0 | Equal |
| `claim_grade` | 0 | Equal |
| `OutcomeKind` | 0 | Equal |
| `ClaimGrade` | 0 | Equal |
| `custody_without` | 0 | Equal |
| `declared_unknown` | 0 | Equal |
| `basis_rank` | 1 | Equal; `foundry/methods/catalog/causal/eif_bounds.py` |
| `not_established` | 84 | Equal |

The architect's counts thus have a reproducible **Python-source** denominator.
They are not whole-repository zeroes. In the complete 2,829-file `src/` set,
`not_established` occurs in 86 files. These measurements say which spellings exist;
they cannot measure a semantics implemented under another name.

## BG-F03 — DecisionGrade is a deliberate separate axis

In [layer2_readiness.py](../../../src/polisyos/pdc/_impl/layer2_readiness.py),
`DecisionGrade` is defined at line 39, `EvidenceBasis` at 53, and
`AuthorityBoundary` at 62. Their separation is functional, not merely adjacent
declarations:

- `_meet_decision_grade` takes the weaker rank. `None` and `unsupported` both rank
  at zero. The meet loses the distinction between missing and explicitly
  unsupported grade.
- `_merge_evidence_basis` combines evidence references. It does not compute their
  decision grade. This is a different operation over a different axis.
- `AuthorityBoundary.meet` intersects permitted purposes, unions denied purposes,
  combines rule references and limitations, and invokes both operations separately.
- The local simulation validator rejects advisory-or-stronger simulation without
  calibration refs. This class checks reference presence there; this observation
  is **not** an audit of resolution and verification elsewhere in the pipeline.

This establishes a deliberate implementation distinction between an admissibility
ceiling and the references supporting it. It does not establish that its designers
intended a universal representation of the constitutional outcomes.

The distinction already reaches generated declarations:
`packages/runtime-api-client/types.ts:3158` carries both optional fields on
`AuthorityBoundary`, and `:6406` contains the four-member `DecisionGrade` union;
`canonicalRuntimeApiClient.ts:532` aliases the generated owner.
`decisionGradePresentation.ts` imports that alias and separately distinguishes
recognized from unrecognized owner labels. These are inspected source facts;
generated-artifact freshness and TypeScript resolution were not executed in this
worktree, which has no local `node_modules`.

Another existing representation matters:
[VersionedClaimVocabularyEnvelope](../../../src/polisyos/ir/analytics/literature.py)
at line 166 carries optional numeric `claim_extraction_confidence` beside
`claim_extraction_confidence_status`. Its validator requires a present value to be
`candidate` and an absent value to be `not_established`. The same shape is used for
its vocabulary axes. Its explicit docstring denies authority. This is a useful
counterexample to treating “value or absence” as the only existing design; it is
not evidence that all four constitutional outcomes are already implemented.

## BG-F04 — hard-case generalization checks

These are source-grounded countermodels and representation requirements, not
executed red tests or an approved new contract.

| Hard case | Why replacing the value with DecisionGrade fails | Shape that could retain the information, subject to the missing census |
| --- | --- | --- |
| A confidence float | A string cannot remain a `DOUBLE` or preserve arithmetic. A confidence score also does not automatically mean delta or `1 - delta`. The same stored number can have different rule/currentness histories. | Keep the numeric observation separately from a bound assessment of the specific claim made from it: purpose, basis identity/rule, standing and limitations. A sibling field, existing containing record, or joined assessment could carry it; their completeness and cost are not established here. |
| Boolean public badge | `decision_admissible` does not establish that a packet's verifier is independent or that a signature is authentic. A browser could self-assert the new string just as it computes the current token. | Derive the display from an admitted, purpose-scoped verification result. Preserve negative and unavailable results at that boundary. Merely adding a grade to the browser packet would not close the debt. |
| GY census row | Task execution status, evidence of one Done-when conjunct, and discharge of all conjuncts are different propositions. A decision-admissibility rank cannot name which proposition was measured. | Keep task status and per-predicate assessment separate, binding each assessment to the source revision, method and actual result. An unmeasured conjunct stays unmeasured even if another passes. |
| Omitted versus explicitly unknown parameter evidence | Both currently construct the same `EvidenceStrength.UNKNOWN`. Mapping both to `unsupported` preserves the information loss. | Supply/judgment provenance must survive construction and transport independently of the vocabulary value and any later authority assessment. This is not a fifth outcome kind. |

The four DecisionGrade members form an ordered admissibility ceiling. The
constitutional kinds distinguish different **contents of a claim**; custody and
declared unknown can coexist in a record under the wave-5 ruling. There is no
justified one-to-one mapping between these two sets merely because both are
described with four entries. A bare shared literal is therefore insufficient.
Whether to reuse a containing boundary, add local sidecars, or reference a shared
assessment remains open; no universal envelope is prescribed.

For every shape above, unknown or weak basis constrains **promotion and projection**.
It cannot prevent candidate calculation, retention of a historical numeric
observation, evaluation, demonstration, or an explicitly limited report. A
verified observation about intake also cannot acquire a claim about transitive
runner integrity through a new grade. The executing party and the proposition it
actually checked remain necessary.

## BG-F05 — expressiveness observations on the leads, not a census

“Partial” below means a local representation exists but does not, by itself,
establish the named ratified outcome. “Unassessed” is not “absent.” A textual
reason can describe an outcome without providing a discriminated, verified
machine representation. None of these cells claims complete chain conformance.

| Lead carrier | Grounded with delta | Honest refusal | Custody without a number | Declared unknown |
| --- | --- | --- | --- | --- |
| `AuthorityBoundary` control case | Partial: grade, purpose and refs; no delta field in this type | Partial: prohibitions/limits, not a refusal outcome | Partial: purpose can name procedure, with refs; no distinct custody variant | Partial: optional grade and limits; missing grade meets as unsupported |
| `SignedPacketVerification` / public badge | No such variant; `valid:true` is local token verification | Local invalidity only: bad format/payload/signature | Current true branch asserts more than the browser token earns | No unavailable/unknown branch in this union |
| `BenchmarkEvaluation` → `ChampionPointer` → `AdmittedClaimAdjudicationBatch` | Numeric metrics, booleans and refs are present; no demonstrated delta claim | Local non-promotion is expressible; substantive refusal not established by it | A declared admission predicate exists; independent custody is the open debt | Local unclear/insufficient/default values exist; complete unknown-scope semantics unassessed |
| `ac_skg_family_edges.confidence` and `ac_skg_contested_edges.confidence` | `DOUBLE NOT NULL`; not itself a delta-accounted claim | The number alone cannot carry refusal | The number alone cannot carry procedural custody | The number alone cannot disclose a withdrawn basis; other consumers are not fully censused |
| GY §8.5 task row and checker's `_WorkRow.basis` | Free text may describe a proof; no typed delta outcome established | Prose/status can record non-execution; refusal justification remains separate | Prose can describe delivered-artifact custody | Explicit `not_measured` prose is possible; complete per-conjunct machine distinction unestablished |
| Readiness `basis.kind="observed_by_reconciler"` | Intake attestation expressly does not claim runner integrity or statistical control | Negative observation status and reason exist; not a policy-refusal proof | Bounded intake scope is explicitly carried and checked | `observation_unavailable` plus reason exists; broader scope semantics unassessed |
| C13 print receipt | Not assessed as a statistical carrier | Full current receipt outcome semantics unassessed | Register records content-bound procedural capture evidence | Register records earlier `not_established` currentness; full consumer mapping not audited here |
| `EvidenceParameter.evidence_strength` | An evidence label/interval is not a delta-accounted claim | Model requires at least one parameter value representation | No such distinction on the evidence-strength field | Explicit `UNKNOWN` and omission collide at construction |
| `VersionedClaimVocabularyEnvelope` control case | Numeric extraction confidence is expressly candidate, not authority | Candidate/absence status is not substantive refusal | Legacy provenance can be retained; no custody authority conferred | Explicit axis absence versus candidate value is represented; not a complete S0 scope contract |

Primary code anchors beyond BG-F03: `publicationPacket.ts:234,1067,1150` and
`PublicDecisionViewerPage.tsx:12,26`; `autotune/models.py`'s `BenchmarkEvaluation`
and `ChampionPointer`, `autotune/registry.py:68`; `literature.py:488,821,849`;
`academic/knowledge/skg_store.py:99,118`; `persist_atlas_evidence.py:152,1610`;
and `check_debt_ledger.py`'s `_WorkRow` declaration. Paths are relative to the
packages named in BG-F01–BG-F04 or the product root. The C13 cell is explicitly
register evidence, not a fresh receipt replay.

## BG-F06 — contract-change cost is not established

The number of types requiring fields, frozen types affected, generated identities
requiring regeneration, schema/OpenAPI crossings, and migration cohorts cannot be
honestly totaled before carrier membership and the representation choice are known.
Seven debt rows are not seven contract changes. A field on a containing object, a
joined assessment and a universal wrapper have different compatibility effects.

The inspected constraints already rule out a “just add a literal everywhere” cost:

- `AuthorityBoundary` inherits strict frozen `Layer2ReadinessModel` and already
  appears in generated API types. Changing it may affect containing contracts,
  serialized bytes and generated-owner receipts.
- `EvidenceParameter` and `AdmittedClaimAdjudicationBatch` are strict frozen
  Pydantic contracts. The batch's `schema_version` and `rule_version` are literal
  fields. Field addition cannot be described as a presentation-only edit.
- `BenchmarkEvaluation`, `ChampionPointer`, and `DecisionGradeExport` declare
  `extra="forbid"` without those frozen declarations. Their artifacts and downstream
  consumers still need a compatibility inventory.
- SKG numeric columns are relational contracts. A companion grade need not replace
  a `DOUBLE`, but persistence and joins must preserve the binding. The GY Markdown
  table has a parser and ledger consumer; changing its representation is another
  mechanism. A generated alias is a projection of a source contract, not an
  independent owner to edit.

These are constraints witnessed in named types, **not lower-bound estimates of the
required edit set**. No proposal commits those types to gaining a field.

The historical cohorts named by the commission, 342 and 458 rows, are consumers of
the future decision. Their sizes and current contents were not re-derived. No
snapshot query, data producer, reweighting, reissue, or migration ran in this task.
The declared currentness rule in the group-A journal is useful precedent for one
semantic rule with several local mechanisms; it does not settle the missing carrier
count or make the new mechanism cost-free.

## Task decomposition and draft GY text

The provisional “one shared decision, several implementations” has a sound reason:
scope-limited authority is shared, while numeric storage, a route verification
result, a procedural receipt and a plan row retain distinct semantics. The
DecisionGrade countermodels argue against forcing them through one runtime enum.
However, the unmeasured contract graph prevents choosing the implementation split
or asserting that two, three, or any other number of implementation tasks suffices.
The safe transcription is a research prerequisite only.

### GY-BG0 — establish the carrier denominator before selecting a representation

- **Phase:** 0, the form; research prerequisite for a cross-package representation
  decision and any subsequent authority-surface implementation.
- **Owner:** proposed `team-architecture`, with the source-owning package lanes
  supplying producer and consumer facts. This names engineering accountability,
  not a new institutional signer.
- **Boundary:** `own` the accuracy and scope of our assessment and public claim;
  `integrate` externally signed evaluator/runner evidence; appointments stay
  typed-empty when absent. External institutional execution is out of scope.
- **Scope:** research and written hand-back. Resolve the unit of membership at
  persistence/projection boundaries, including dictionary payloads, SQL columns,
  generated projections and parsed Markdown rows. Reuse existing owner inventories
  and resolvers where their scopes actually match. No source, test, schema, data or
  active-plan change is authorized by this draft.
- **Done when:** a pinned, fully enumerated carrier set is derived from actual
  producers/persistence paths and independently reconciled against actual
  consumers/projections, with both directional differences resolved, representation
  ownership and exclusions recorded, and no keyword/name/presence proxy deciding
  membership; every admitted member has a four-outcome expressiveness assessment
  that separates representation from earned verification and names its authority
  purpose; the hard cases retain their original values and unrestricted candidate
  computation; the resulting proposal counts the complete source contracts, frozen
  contracts, generated projections and schema/OpenAPI crossings for each proposed
  implementation group; and each of the seven debt signals is mapped to what the
  decision can establish and what still needs separate evidence or infrastructure.
  Unresolved membership ends as a stopped research result, never an estimated total.
- **First three red tests (acceptance falsifiers to specify and execute in that
  research; none implemented or run here):**
  1. Remove a discovered producer or persistence carrier from the proposed census
     while leaving its live consumer and the file/keyword counts unchanged. The
     independent consumer reconciliation must reject the coverage claim and name
     the missing carrier. Run against the actual enumerated membership, not a
     hand-picked success list.
  2. Leave a dictionary-carried value, SQL column, generated alias, or parsed plan
     row without its source-to-consumer representation mapping while retaining its
     enclosing file and class. The census must report `not_established`, not
     “covered” because the file exists or because a surrounding contract has a
     status field. Derive the variants from the representation forms actually found.
  3. Preserve a value and its asserted positive label while withholding the basis
     for the exact projected proposition. The assessment must not upgrade it:
     client-computed validity cannot become authenticated custody; intake closure
     cannot become runner integrity; a passed task conjunct cannot discharge an
     unmeasured conjunct. Candidate calculation and observation must remain available.

**Pattern pass:** `P35/P38` are the immediate failure: file/declaration completeness
would be substituted for semantic carrier completeness. `P37/P32` apply because
an asserted grade or verifier label cannot establish its decisive predicate.
`P04/P05/P07/P08/P09` protect composition, authority scope and currentness;
`P01/P02/P03/P10/P27` prevent a contract-only or duplicate waist proposal;
`P13/P40` prevent repairing every debt by adding progressively larger wrappers.
The target is a reconciled authority-use inventory and a costed decision, not a
new general-purpose gate. No cross-carrier runtime capability is delivered;
allocation of such a capability remains `absent/unallocated`. Within the examined
leads, missing verification and surfaces must retain their local labels, including
`verification_missing`; prose is not a completed capability chain.

**Predicate provenance at this handoff (`P37`):** file and lexical counts are
`recomputed`, with the independent path-set comparisons described in BG-F01/BG-F02;
semantic carrier completeness and total contract cost are `not_established`.
The register's earlier execution receipts were not replayed, so they are cited as
historical register evidence rather than promoted to freshly recomputed facts.
An existing `independently_reconciled` literal in a payload remains a declaration
until the exact verification chain establishes it. None of these limitations gates
candidate work; they withhold only the corresponding research or authority claim.

## Every original debt: prospective closure and what this decision would buy

All seven rows retain the standing recorded in
[DEBT-REGISTER.md](../../plans/active/DEBT-REGISTER.md). No closure is proposed by
this investigation or by `GY-BG0`. Each sentence below describes the later evidence
required; a grade representation alone does not supply it.

| Debt ID | Sentence that could close it later; relation to the proposed research |
| --- | --- |
| `public-decision-verified-badge-is-client-computed` | Close when the public route renders verified only from a server-backed admitted verification response, the client-computed token path is strangled, and the forged packet fails the public-route negative. BG0 must map that verification boundary and its generated/public contracts; adding a client grade buys no closure. |
| `adjudication-and-champion-chain-is-forgeable` | Close when a named non-producing verifier authenticates an appointed evaluator's receipt, recomputes the bound observations, metrics, guards and champion predicate before publishability materialization, and a self-stamped chain is insufficient. BG0 must separate the existing asserted predicate from earned verification; the appointment is an empty authority slot, not a mechanism blocker. |
| `transitive-runner-closure-unbound` | Close only when an out-of-band runner identity exists, is bound and independently admitted for the claimed transitive scope; until then retain the explicit intake-only scope and the bounded residual. BG0 cannot close an infrastructure absence by renaming `observed_by_reconciler` or adding a stronger grade. |
| `historical-confidence-carries-a-withdrawn-contribution` | Close when an authorized data pass re-derives the affected values, or a machine-readable binding identifies the withdrawn rule and is consumed to refuse or limit those values' authority. BG0 may determine the carrier and contract cost; the 458-row historical work remains out of scope. |
| `gy-census-decisive-property-unmeasured` | Close when the owning census records decisive-property evidence or an explicit unmeasured disposition for the remaining required predicates, preserves failures over artifact-presence claims, and its complete census/status diff satisfies the row's signal. BG0 must preserve predicate-level granularity; passing one conjunct or adding a row-level grade does not discharge the others. |
| `ds10-c13-print-receipt-reissue` | Close when the current independent receipt conjunction and global disposition checker both pass under an admitted schema-versioned reconciliation. The row's Task P append already records the evidence reissue as done and names the DS18 append-only checkpoint schema as the remaining block; a basis grade alone closes neither gate. |
| `parameter-contract-cannot-distinguish-unsupplied-from-unknown` | Close when omission and a recorded unknown judgment remain separately representable through construction, persistence and every reading consumer, with the negative proving omission cannot present as judgment. BG0 must count that entire contract chain; a common unsupported grade alone preserves the collision. |

The updated GY and C13 descriptions above cite the respective debt IDs and their
Task Q/Task P append records, not a revision-log aside. Their earlier quantities
are historical context. This task did not replay their tests, recalculate the
historical cohorts, or certify their current global gates.

## Preservation and closeout

The source branch was attached at the requested base and clean before this work.
Only this research document is intended for the single commit. No edits were made
to `docs/plans/active/`, production code, tests, schemas, apps, or data. No rebase,
stash, producer, migration, or historical recomputation was used.

The linked snapshot was opened only for binary read-only hashing:

```text
production_data/policyos_academic_runtime_slim_20260411T112032Z/
academic/graph/scholar_knowledge.duckdb
sha256:583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967
```

After committing and reading this path back from the attached branch, run the
bound debt checker once with both streams redirected to ignored harness scratch,
then re-hash the same snapshot. The actual checker exit, receipt path and final
hash belong in the task handoff; they are not pre-claimed by this document.
A nonzero checker result without a replay from the slice base remains
`not_established` under `P41`, not automatically inherited debt. This task's
one-checker limit is not an authorization to assert otherwise.

## Appendix A — read-only reproduction of BG-F01/BG-F02

Run from the provisioned `policy-engine/` with Python 3.14. This reproduces the
file/declaration/lexical measurements, **not** semantic carrier coverage. The
source-diff guard keeps the measurements tied to the pinned source; the added
research document is outside that source set. No product module is imported.

```python
import ast
from collections import Counter
from pathlib import Path
import subprocess

root = Path.cwd()
base = "edcad691c3fc0e055338898fb3cc456592b9b962"
subprocess.run(["git", "diff", "--exit-code", base, "--", "src"], check=True)
all_paths = subprocess.check_output(
    ["git", "ls-tree", "--full-tree", "-r", "--name-only", base], text=True
).splitlines()
product = {p.removeprefix("policy-engine/") for p in all_paths
           if p.startswith("policy-engine/")}
index = set(subprocess.check_output(
    ["git", "ls-files", "-z", "--", "."]
).decode().rstrip("\0").split("\0"))
report_path = "docs/superpowers/specs/2026-09-05-basis-grade-carrier-investigation.md"
assert index - {report_path} == product
source = {p for p in product if p.startswith("src/")}
filesystem = {str(p.relative_to(root)) for p in (root / "src").rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
assert source == filesystem
python_paths = sorted(p for p in source if p.endswith(".py"))
texts = {p: (root / p).read_text() for p in python_paths}
print(len(all_paths), len(product), len(source), len(python_paths))
# 10550, 10528, 2829, 2619

totals = Counter()
second = Counter()
for path, text in texts.items():
    tree = ast.parse(text, filename=path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        fields = [x for x in node.body if isinstance(x, ast.AnnAssign)
                  and isinstance(x.target, ast.Name)]
        totals["classes"] += bool(fields)
        totals["fields"] += len(fields)
        for field in fields:
            names = {x.id for x in ast.walk(field.annotation) if isinstance(x, ast.Name)}
            totals["annotations_containing_Any"] += "Any" in names
    stack = [tree]
    while stack:
        node = stack.pop()
        stack.extend(ast.iter_child_nodes(node))
        if isinstance(node, ast.ClassDef):
            count = sum(isinstance(x, ast.AnnAssign) and isinstance(x.target, ast.Name)
                        for x in node.body)
            second["classes"] += bool(count)
            second["fields"] += count
assert totals["classes"] == second["classes"] == 7028
assert totals["fields"] == second["fields"] == 52666
assert totals["annotations_containing_Any"] == 2477
print(totals)

tokens = ("basis_grade", "evidence_grade", "claim_grade", "OutcomeKind", "ClaimGrade",
          "custody_without", "declared_unknown", "basis_rank", "not_established")
for token in tokens:
    primary = {p for p, text in texts.items() if token in text}
    result = subprocess.run(
        ["rg", "--files-with-matches", "--null", "--fixed-strings", "--glob", "*.py",
         token, "src"], capture_output=True, check=False
    )
    assert result.returncode in (0, 1), result.stderr
    other = set(result.stdout.decode().rstrip("\0").split("\0")) if result.stdout else set()
    assert primary == other
    print(token, len(primary))

print("not_established, all src file types:",
      sum("not_established" in (root / p).read_text() for p in source))
# 86; count files, not unique contents.
```
