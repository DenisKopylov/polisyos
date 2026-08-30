---
title: INT-R2 — Recommended Revision
status: independent_audit_recommendation
research_task: INT-R2
package_head: 5e6a7063da770122155af6300647d0cd2e9c17ea
authoritative_for:
  - closing conditions for INT-R2 audit findings
may_not_use_for:
  - replacement package text
  - amendment disposition
  - capability claim
  - implementation authorization
---

# INT-R2 — Recommended Revision

## 1. Revision Boundary

This is a bounded amendment, not a request to redesign the research. Preserve:

- the eight commissioned case types;
- the same-stream row-invariance rule;
- the refusal to classify the fourteen without evidence;
- the no-auto-close re-entry rule;
- the common five-part `deeper_terminal` definition;
- the separation of PolicyOS custody from external institutional acts;
- the set-level holder/denominator discipline and refusal of the supplied zero;
- the source-ledger proposition/non-effect columns.

Do not appoint a canonical owner, institutional signer or provider from the amendment stage. Do not
turn the 63-case proposal into code. The amendment repairs research evidence, classification logic and
handoff precision.

## 2. Finding-Register Repair

### AUD-F001 — three-column list is not an auditable register (`material`)

Replace the F01–F40 table with at least:

```text
ID
kind
research_standing
source_or_transfer_class
holder_label
source/evidence refs
finding
consequence
non_effect
```

Allowed `kind` examples are descriptive, not standing values: repository observation, external
transfer, logical derivation, design rule, benchmark protocol, impossibility/limit, capability
boundary.

**Closure test:** a reader can determine, from one row, what class of claim it is, who supplied the
predicate, what evidence supports it, what changes if accepted and what it may not establish.
Surrounding prose may expand a row but may not supply mandatory missing columns.

### AUD-F002 — six mixed standing cells (`material`)

Normalize exactly:

- F13 → `confirmed`;
- F27 → `confirmed`;
- F29 → `confirmed`;
- F31 → `confirmed`;
- F34 → `accepted_narrow_scope`;
- F39 → `confirmed`.

Move `within the declared regime`, `design rule`, `by producer/proof/ceiling derivation`, `benchmark
protocol` and `project-boundary result` into scope/kind/basis columns.

**Closure test:** every standing cell is an exact member of the registered five-value vocabulary;
parsing does not strip or interpret suffix prose.

### AUD-F003 — F01 cites the wrong owner/lines (`material`)

Locate the canonical owner of each named refusal token. Do not cite a search result as a denominator.
Update F01 and the baseline row with exact pin, path and line range. Where the five terms live in more
than one owner, split the finding or state the owner relationship.

**Closure test:** re-reading the cited lines at `dc7bdf79a` displays the named vocabulary and its
meaning. `gy_waist.py:218-255` is removed unless the claim is changed to the comparison contract it
actually contains.

### AUD-F004 — repo-wide absence claims outrun evidence (`material`)

Split the following findings:

- F05: confirm the data passport/overlay shape; separate the repository-wide “no non-data path” claim;
- F07: confirm CG3 routing; separate “no generic external producer”;
- F11: confirm authority fragments; separate “no generic evaluator”;
- F32: retain capability `absent/unallocated`; do not call the eight-way source-tree absence a
  confirmed census without executing it.

For each absence either:

1. execute a complete tracked-tree walk with path denominator, file-type denominator, executing party,
   positive control and impossible-token negative control; or
2. use holder-relative `not_established` and name the missing denominator.

**Closure test:** no package row derives a repository zero from selected owner files or connector
search.

## 3. Standing-Vocabulary Repair

The package-level three-axis standing may remain:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

Per-finding revisions:

- F20 should be `accepted_narrow_scope` unless rewritten as a claim bounded to the named professional
  regimes;
- F25 should carry `kind: design_rule` and its derivation; its token may remain `confirmed` only if
  `confirmed` is explicitly about the logical necessity under the package's premises, not an empirical
  repository fact;
- F34 stays `accepted_narrow_scope` and must not be described as an executed benchmark.

**Closure test:** package standing, capability standing, gate standing and audit verdict remain four
separate concepts; none is inferred from another.

## 4. Evidence And Transfer Repair

### AUD-F006 — external source content is not durably replayable (`material`)

Keep all 22 source rows and their proposition/non-effect boundaries. Add:

- exact document edition or publication date;
- section/paragraph/page or theorem locator;
- stable report/standard identifier where available;
- retrieval date;
- for mutable landing/guidance pages, an immutable owner publication or preserved content identity
  permitted by repository policy.

Mandatory replacements/supplements include:

- S04: actual IARC Preamble edition, not only a news page;
- S13: exact IESBA Code edition/paragraphs, not “current standards” landing;
- S14: exact ISAE 3000 text/paragraphs, not only a news overview.

Apply the same locator rule to live FDA, HHS, ICO, GOV.UK, HMLR, GMC, UK-SPEC, Treasury and RE-AIM
pages.

**Closure test:** an offline repository reader can identify the exact source state and claim-bearing
passage for every S01–S22 transfer, or the row explicitly says why external replay remains unavailable.

## 5. Union And Classifier Repair

### AUD-F005 — `GapShapeAssessment` records rather than constructs classification (`material`)

Add a branch-decision appendix. For every type specify:

- minimal blocked-predicate form;
- evidence required to select the type;
- at least one neighboring type ruled out and the falsifier that rules it out;
- compound/split rule;
- P37 provenance required for each predicate;
- result when the evidence is missing.

Apply the appendix to the three capstones. For the fourteen later residuals, do not invent identities;
provide a row template that names exactly which classifier input is unavailable for each.

**Closure test:** a reviewer can take a frozen residual with its demanding predicate and reproduce
`data_gap`, one case, ordered split or `not_established` without reading the classifier author's
intent.

### AUD-F010 — `owner_writability` hides two obligations (`minor`)

Represent separately:

1. substantive change authority over the canonical object/operation; and
2. technical execution grant/least privilege for the actor/system.

Either make both mandatory sub-obligations of one discriminator or allow an ordered split. State that
neither artifact closes the other.

**Closure test:** the valid-token/no-substantive-right fixture and the substantive-order/no-executable-
grant fixture both remain blocked for different reasons.

### AUD-F011 — HD and IA need explicit no-substitution (`minor`)

Define a shared reconstructable-work base only if useful. Preserve:

- HD: accountable case-specific decision, role/competence/work/conclusion;
- IA: subject/criteria/scope/procedures/assurance level plus relational independence.

Add two negative rules:

- external HD is not IA without the assurance engagement and independence proof;
- favourable IA is not the underlying management/professional decision.

**Closure test:** both cross-substitution fixtures fail while legitimate dependency references remain
possible.

## 6. Ceiling And Benchmark Repair

### AUD-F007 — `AuthorityCeiling` lacks field-level algebras (`material`)

Replace the aggregate “subset-testable” claim with a checkability matrix. For each field state:

- vocabulary owner;
- equality, set-subset, hierarchy, interval or compatibility relation;
- unknown behavior;
- conflict/precedence rule;
- current implementation status.

At minimum define or defer explicitly:

- population set containment;
- jurisdiction overlap/subordination;
- purpose and audience subsumption;
- source→target context compatibility/transport;
- evidence-class-to-claim mapping;
- maintained-assumption currentness;
- claim-strength and commitment-stage partial orders;
- operation ontology and prohibition-wins composition.

Exact refs and timestamps may be marked locally checkable. Opaque refs without an evaluator are not.

**Closure test:** every one of the twelve dimensions is labelled `checkable_today`,
`checkable_after_registered_mapping`, or `not_checkable`, with no narrative field counted as an
enforced subset relation.

### AUD-F008 — the 63-case floor is not yet non-vacuous (`material`)

Keep the denominator but add a committed research fixture manifest containing all 63 case IDs. Each
row must bind:

- discriminator and exact input state;
- protected property;
- independent oracle and adjudicator/source;
- expected closure/terminal/ceiling result;
- volatile fields excluded from comparison;
- mutant(s) the case must kill.

Required mutants include:

- row-count closes relation/estimand/mandate;
- presence/signature/`external=true` closes admission;
- route/artifact auto-closes without owner re-entry;
- exact-membership ceiling evaluator used where hierarchy/subset is required;
- terminal emitted from timeout/silence;
- surface composes authority.

Retain the ordinary data-gap positive control. Add the remove-property/keep-markers probe: deleting the
actual non-closure check while preserving labels must make the battery fail.

**Closure test:** every public case is instantiated, at least one named wrong implementation fails each
family, and `0/63` is not true by construction.

### AUD-F009 — open-world terminal pairs lack coverage proof (`material`)

For OW, LM, IC, HD and IA terminals based on “no source/route exists,” require either:

- a bounded coverage artifact with declared universe, searched sources, exclusions, freshness,
  challenger path and unknown remainder; or
- narrower wording: `exhausted_declared_route_at_epoch`, never universal absence.

For IC bind the decision horizon and enumerate tested build, rescope and alternative-channel paths.
For HD/IA distinguish registry/provider non-receipt from proved absence.

**Closure test:** falsifying the coverage premise while leaving a terminal label intact turns the
fixture red. The deeper member contains new admitted boundary evidence, not merely a preassigned name.

### AUD-F012 — drafted consumer row lacks resolvable holder evidence (`minor`)

Where the package cites `gap_acquisition_case_union`, add:

- immutable branch/ref and path if the draft is legitimately citeable; or
- `holder_label: institutionally_supplied`, with explicit non-effect.

Do not claim registration, merge, owner allocation or consumer readiness from the draft.

**Closure test:** a reader can either resolve the exact row or see immediately that its existence and
status were supplied rather than independently verified.

## 7. Closure Checklist

The amendment is ready for verification only when all are true:

- [ ] F01–F40 register carries the expanded columns.
- [ ] Six mixed standing cells are exact tokens.
- [ ] F01 anchor resolves to its claimed vocabulary.
- [ ] F05/F07/F11/F32 zeroes are recomputed or downgraded.
- [ ] S01–S22 have exact document locators and source-state identities.
- [ ] Eight classifier branches have positive predicates and sibling falsifiers.
- [ ] Writability's two conjuncts and HD/IA non-substitution are explicit.
- [ ] Twelve ceiling dimensions have field-level checkability dispositions.
- [ ] All 63 public fixtures have IDs, exact oracles and mutant failures.
- [ ] Open-world terminals carry bounded coverage or narrower wording.
- [ ] Consumer-row demand is resolvable or holder-labelled.
- [ ] Package standing remains separate on three W4-K05 axes.
- [ ] No owner, signer, provider, capability or gate is appointed/opened by the amendment.

No source, workflow, runtime contract, pattern-register or `AGENTS.md` change is required to close this
audit.