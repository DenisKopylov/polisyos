---
plan_id: atlas-ds17-confidence-ledger-risk-spend
title: "DS17 - Confidence-Ledger & Risk-Spend Surface"
type: slice-plan
status: proposed_approval_gated
created: 2026-08-27
amended: 2026-08-27
last_verified: 2026-08-27
stability: measured_planning_handback
slice: DS17
baseline_commit: 2525da7306d329ae28fa394690e1c39133eb0d55
branch: codex/ds17-confidence-ledger-risk-spend-plan
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
int_r1: ../../../research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md
int_wave_claim_semantics: ../../../system-design-decisions/int-wave-claim-semantics-ratification.md
public_verification_semantics: ../../../system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md
int_r8_falsifier_suite: ../../../research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md
stage0_custody_kernel: ../../../system-design-decisions/stage0-custody-kernel-ratification.md
int_r9_amendment_verification: ../../../research/policy-operations/audits/int-r9/int-r9-amendment-verification.md
int_r9_independent_audit: ../../../research/policy-operations/audits/int-r9/int-r9-independent-audit.md
int_r9_recommended_revision: ../../../research/policy-operations/audits/int-r9/int-r9-recommended-revision.md
gy_gap1_journal: ../../../superpowers/journals/2026-08-19-gy-gap1-obligation-instance-identity.md
audiences: [REVIEWER, EXPERT, MACHINE]
artifact_owner: team-runtime-quality
producer_lane: runtime/quality
surface_owner: team-design
feature_flags: none
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ../../../research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md
  - ../../../research/policy-operations/int-r1/artifact-and-state-machine-sketch.md
  - ../../../system-design-decisions/int-wave-claim-semantics-ratification.md
  - ../../../system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md
  - ../../../research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md
  - ../../../system-design-decisions/stage0-custody-kernel-ratification.md
  - ../../../research/policy-operations/audits/int-r9/int-r9-amendment-verification.md
  - ../../../research/policy-operations/audits/int-r9/int-r9-independent-audit.md
  - ../../../research/policy-operations/audits/int-r9/int-r9-recommended-revision.md
  - ../../../superpowers/journals/2026-08-19-gy-gap1-obligation-instance-identity.md
---

# DS17 - Confidence-Ledger & Risk-Spend Surface

## For agentic workers

This is an approval-gated implementation plan, not authorization to implement.
Planning occurred in the isolated worktree
<code>/Users/deniskopylov/polisyos/.worktrees/ds17-confidence-ledger-risk-spend-plan</code>
on attached branch
<code>codex/ds17-confidence-ledger-risk-spend-plan</code>. Before this file was
written, <code>HEAD</code> was
<code>2525da7306d329ae28fa394690e1c39133eb0d55</code>, the branch was attached
and clean, and both required commits were ancestors:
DS7 <code>74f26ca2d</code> and GY-N11 <code>f41d49071</code>. This plan is the
only permitted planning change. No source, register, generated artifact, merge,
push, rebase, reset, or stash storage is authorized by the planning hand-back.

This amendment changes that plan only. The independently repeated standing
agrees with every original load-bearing measurement: 13 instrument definitions,
six certificate-class routes, 15 unique obligation classes across seven pools,
weights summing to 20/20, per-class allocations summing to exactly δ = 1/100,
zero N11 identifiers in the complete 100-file HTTP denominator, and zero
<code>ObligationCoverageEnvelope</code> occurrences under the complete
<code>src/**</code> plus <code>schemas/**</code> denominator. The original P37
table, DS11 fence, honestly-empty register, and MACHINE parity design remain in
force. The amendment adds no cluster and no mechanism path: assessment
derivation stays in C01's already-declared
<code>runtime/quality/obligation_coverage.py</code>, and the scope-locality
disclosure stays inside C04's existing
<code>ConditionalDeltaFigure</code>. The declared 18-path set and 22-path hard
ceiling therefore remain unchanged.

At execution entry, run <code>git rev-parse --show-prefix</code> immediately
before every path coordinate, including commands run from the product root.
From the repository root the prefix is empty; from the product root it is
<code>policy-engine/</code>. Re-read <code>git status -sb</code>,
<code>git symbolic-ref -q HEAD</code>, and the exact cluster path fence before
every commit. History is append-only. Use <code>corepack pnpm</code>, never bare
<code>pnpm</code>, and install the frozen workspace before trusting a TypeScript
scanner.

DS11 owns a measured 63-path in-flight delta. No DS17 execution may write
<code>apps/runtime-dashboard/**</code> or
<code>architecture/atlas_surfaces/**</code> until DS11 is merged and its merge
commit is the DS17 execution base. Backend producer, projection, HTTP contract,
and the canonical checked-in OpenAPI schema may proceed first. The first
committed dashboard byte, including generated
<code>apps/runtime-dashboard/src/api/types.ts</code>, is the hard wait boundary.

## Mission and scope ruling

DS17 puts conditional promotion-risk accounting on the reviewer glass:

1. the refusal and acquisition instruments that actually exist;
2. exact δ spent and remaining for every declared obligation class;
3. the registered instrument/proof posture, including hard blockers;
4. an honestly empty positive-promotion-certificate register;
5. the obligation-set conditional that makes every rendered δ figure sayable,
   plus the same chip's scope-locality disclosure on every aggregate;
6. one exact-response MACHINE twin.

The surface is an authenticated child panel of the existing global Cycle Board.
That is the smallest reuse-first placement: DS7 is DS17's gate, the N11 source
is not run-bound but remains one exact source-owned confidence scope, the Cycle
Board already has <code>runs.review</code> authorization, and a new standalone
route would create a second navigation and permission owner without adding
truth. The DS17 panel loads independently so a Cycle Board source error cannot
erase its governed empty state, and a DS17 source error cannot erase the Cycle
Board.

The persisted verification/evidence source is the committed, generated GY-N11 artifact
<code>architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json</code>.
The surface must display its exact risk scope and source identity. It must not
describe that frozen N10+N13b accounting scope as a live, global deployment
ledger. A future live multi-scope index is a separately named non-closure below.
It must not combine several per-design-problem roots, create a parent risk scope,
or describe one scope's total as a family or sequence-level guarantee.

DS17 implements Surface Laws 3, 4, 5, and 8:

- missing/invalid/over-spent/non-anytime-valid inputs fail closed;
- the weakest grounded boundary controls the visible promotion posture;
- zero positive certificates and unresolved coverage are designed truths, not
  degraded usefulness;
- runtime statuses and reason codes drive presentation; the UI invents no
  authority lattice.

DS12, DS13, public δ claims, the first governed promotion, institutional
appointments, live deployment-wide ledger enumeration, the debt register,
other slices' evidence, and the deep-import baseline are out of scope.

## Measured entry evidence

### Gate, coordinate, and branch receipt

The planning base and both gates were checked without a pipe:

~~~text
branch  refs/heads/codex/ds17-confidence-ledger-risk-spend-plan
HEAD    2525da7306d329ae28fa394690e1c39133eb0d55
DS7     git merge-base --is-ancestor 74f26ca2d HEAD -> 0
N11     git merge-base --is-ancestor f41d49071 HEAD -> 0
prefix  empty at repository root
~~~

No planning command is used as a timing claim. Execution timing receipts follow
the user + sys and uptime protocol defined below.

### GY-N11 actual-output census

The census is pinned to the N11 merge
<code>f41d49071</code> for “what N11 emitted,” and to the current planning base
only for “what is reachable over HTTP now.” The later
<code>N9PromotionSemanticLedgerProjection</code> did not exist at the N11 merge
and must not be attributed to N11.

#### Durable runtime output

N11 is not contract-only. <code>ConfidenceLedgerSession</code> opens a canonical
scope, emits a <code>ConfidenceLedgerHistoryToken</code>, moves checks through
prepared → started → completed, and returns a
<code>ConfidenceLedgerReceipt</code>. Its storage path durably writes:

- scope-anchor and registry payloads;
- <code>ConfidenceLedgerRoot</code>;
- stored ledger events materialized as <code>ConfidenceLedgerEvent</code>;
- optional <code>ConfidenceLedgerReceipt</code>;
- terminal deployment-drift poison;
- local head, scope-journal WAL, tombstone, and locks.

Owner certificate binding, invocation identity, rational spend, ordinals,
eligibility, and refusal values are embedded in checks and receipts rather than
persisted as independent artifact families.

The N9 consumer path is also real. <code>CanonicalN9PromotionPort</code> opens
the ledger session, requests the N9 projection, binds risk-spend summaries and
records into <code>CanonicalPromotionReceipt</code>, and returns them through
the generation-cycle observation. N11's checker additionally persists one
registered generated audit artifact:
<code>architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json</code>.

#### Direct projection families

Two independent complete derivations agree on exactly three N11 projection
families:

| derivation | complete denominator | result |
| --- | --- | --- |
| class declarations at <code>f41d49071</code> | all N11 projection model declarations | <code>ConfidenceLedgerSemanticReceiptProjection</code>, <code>N9PromotionCertificateProjection</code>, <code>N12EpochReferenceProjection</code> |
| producer functions at <code>f41d49071</code> | all public <code>project_*</code> N11 producers | <code>project_confidence_ledger_semantic_receipt</code>, <code>project_n9_promotion_certificate</code>, <code>project_n12_epoch_reference</code> |

There is no disagreement. The semantic receipt and N12 projection are returned
in-process but are not persisted as projection artifacts. N12 truthfully says
<code>epoch_not_implemented</code>.

#### Reachability partition

| partition | measured N11 output | capability reading |
| --- | --- | --- |
| Direct typed HTTP | **0** direct N11 receipt, event, root, semantic-receipt, N9-certificate, or N12-reference operations | <code>surface_missing</code> / P03 |
| Typed contract without route | **0** N11 HTTP DTO families without an operation | no hidden ready-made bridge |
| Indirect HTTP carrier | <code>POST /api/v1/control/runs/nl</code> can persist an outer compiled recursive-cycle artifact; <code>GET /api/v1/control/jobs/{job_id}</code> exposes only untyped progress keys such as the compiled-cycle ref and refusal reasons | not a typed N11 surface |
| In-process only | root/check/event/receipt, all three direct projections, and N9 nested risk-spend values | bridge/surface work remains |
| Generated audit | one committed N11 JSON artifact with source, registry, real-ledger, N9, conformance, owner-bundle, and audit projections | real persisted source for DS17 |

The zero direct-HTTP result was derived twice: a complete identifier walk over
all 100 current <code>src/polisyos/runtime/http/**/*.py</code> files and a
separate walk over core contracts, packages, and public-surface declarations.
Both returned no match; the explicit app router census also has no N11 router.
The generic artifact route is not a counterexample: N11 payloads lack the
authority-surface signal that route requires and therefore fail closed at
<code>authority_surface_signal_missing</code>.

Opening capability state:

- the core ledger/N9 chain has producer + persisted artifact/event +
  orchestration bridge + consumer + verification;
- direct N11 visibility is <code>surface_missing</code>;
- semantic-receipt and N12 projection persistence is
  <code>artifact_missing</code>, and each lacks an independent DS17 consumer;
- DS17 should build a narrow projection bridge and chrome, not a second ledger.

### Instrument inventory: definitions are not instances

The current real inventory is intentionally small. Two independent methods were
run over each complete denominator and agree.

| denominator | derivation A | derivation B | measured result |
| --- | --- | --- | --- |
| sole registry TOML | Python <code>tomllib</code> structural parse | section-scanning <code>awk</code> walk | 2 schedule profiles, 7 obligation pools, 5 proof profiles, **13 instrument definitions**, 6 certificate-class routes |
| instrument role memberships | structural flatten of every definition's role tuple | textual scan of every <code>certificate_roles</code> row | acquisition 1, admission 5, promotion 11, promotion-conformance 1, refusal 6 |
| route roles | structural count of all six routes | textual count of every singular route role | acquisition 1, admission 1, promotion 2, refusal 2 |
| sole persisted N11 JSON | Python JSON structural parse | <code>jq</code> over all real checks and N9 rows | **3 actual instances = 1 refusal + 2 acquisition; 0 positive promotion rows** |
| owner input projection | Python JSON structural parse | <code>jq</code> over N10/N13b projections | N10 3 routes = 1 refusal + 2 acquisition + 0 owner-data-gap; N13b 5 attempts, 2 raw responses, 0 admissions, 0 passports |

There is no disagreement. Test constructors are excluded from the persisted
instance denominator.

The three real instrument instances are:

| role | instrument | persisted certificate refs | count | promotion risk spend |
| --- | --- | --- | ---: | ---: |
| refusal | <code>deterministic_refusal_certificate</code> | <code>n10-route://education</code> | 1 | 0 |
| acquisition | <code>deterministic_owner_proof</code> | <code>n10-route://first_vertical</code>, <code>n10-route://unseen</code> | 2 | 0 |
| positive promotion | none | N9 <code>promotion_rows=[]</code> | 0 | 0 |

The conformance ledger has one separate
<code>constant_unit_e_process</code> check. Its role is
<code>promotion_conformance</code>; it is not a positive promotion certificate
and must not be merged into the three real rows or the zero-row N9 register.
N13b's five attempts and two raw responses are acquisition evidence, not admitted
instrument instances; zero passports produced zero ledger rows.

Python JSON and <code>jq</code> walks of all three real checks also agree on
**0 non-deterministic checks and 0 non-null good-event refs**. Thus the opening
good-event posture is an honest empty promotion set plus the existing
union-bound/no-independence clause, not an inferred probabilistic guarantee.

The only two registered positive-offer routes are already fail-closed:

- N8 calibration → <code>fixed_time_confidence_interval</code> →
  <code>fixed_time_ineligible</code> → <code>non_anytime_valid</code>;
- N8 data trust → <code>owner_verified_e_process</code> →
  <code>owner_theorem_unavailable</code>.

The registry also contains
<code>bayesian_credible_interval</code> with proof profile
<code>bayesian_credible_interval_ineligible</code> and refusal code
<code>coverage_argument_missing</code>. No current producer can populate an
eligible positive N9 row. The honest capability label is
<code>producer_missing</code> for an eligible, owner-verified promotion
instrument chain—not “zero-spend positive certificate.”

### Exact declared-class budget

The registry expands seven pools to 15 declared obligation classes. A direct
TOML/Fraction derivation and the runtime
<code>ConfidenceLedgerRegistry.obligation_weights</code> derivation both
returned 15 rows, weights summing to 1, and class allocations summing to
δ = 1/100. There is no disagreement.

| obligation classes | per-class allocation |
| --- | --- |
| normative, value, data | 1/1000 each |
| syntax, type, slot, param | 3/8000 each |
| effect, identification, measurement | 1/1500 each |
| calibration | 3/2000 |
| implementation, eval_safety, coupling, equilibrium | 1/2000 each |

All three current checks are deterministic and spend zero, so every current
class has zero spent and its full exact allocation remaining. The human UI may
also show a decimal, but exact numerator/denominator values remain in the
contract and MACHINE twin; no float performs the accounting.

### ObligationCoverageEnvelope field check

There is no canonical executable
<code>ObligationCoverageEnvelope</code> DTO or producer today. INT-R1's compact
and detailed research sketches contain all four fields the DS17 chip needs;
that is a shape finding, not the object's complete standing. The object's
meaning is also constrained by the ratified INT wave and its accepted
<code>INT-R9-H-002</code> repair: completeness is relative to a named
basis/language/cutoff, both negative states block the affected protected action,
and post-result narrowing cannot rescue that action
(<code>docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:209-226</code>).

| chip disclosure | research sketch | executable repository state |
| --- | --- | --- |
| declared scope | <code>scope: ScopeDescriptor</code> with purpose, audiences, cutoffs, and limitations | no canonical DTO or producer |
| searched sources | <code>searched_sources</code> with source, query/snapshot identity, availability, recall limits, and time roles | no canonical DTO or producer |
| exclusions | <code>exclusions</code> with rationale, authority, materiality, expiry, and challengeability | no canonical DTO or producer |
| unknown residue | named <code>unknown_remainder</code>, deliberately <code>not_estimated</code> and <code>not_calibrated</code> | no canonical DTO or producer |

The sketches also carry obligation-language version, source/cutoff time,
review/expiry/TTL, independence evidence, public rider, authority purpose, and
may-not-use-for. They explicitly have no canonical package placement,
serialization, or current issuer. The ratified <code>INT-K03</code> ruling says
declared or self-authored independence cannot issue
<code>bounded_complete</code>, and records constructed independence as absent
(<code>docs/system-design-decisions/int-wave-claim-semantics-ratification.md:130-140</code>).

Under the repository capability vocabulary, the admitted executable envelope
chain is <code>absent/unallocated</code>; relative gaps are
<code>producer_missing + artifact_missing + bridge_missing +
semantic_test_missing</code>. The research memo's own shorthand is
<code>contract_missing</code>. This is a producer finding, not a rendering
defect.

DS17 closes only a narrow negative projection. It defines an executable
<code>ObligationCoverageEnvelope</code> whose producer derives over
<code>{known_incomplete, open_world_unresolved}</code>. The caller cannot select
the arm. A non-empty tuple of admitted, content-bound concrete-witness receipts
selects <code>known_incomplete</code> and the envelope carries every witness ref;
otherwise unresolved closure/remainder selects
<code>open_world_unresolved</code>. This is the exact INT-R1 distinction:
concrete omission, exclusion, traversal, validator-unsoundness, conflict, or
challenge evidence at
<code>docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:428-437</code>.
<code>bounded_complete</code> remains structurally absent.

The current N11-artifact-only input has no admitted concrete witness and thus
derives <code>open_world_unresolved</code>; it is not a constant. The envelope
contains the four disclosures plus language, cutoff, and TTL state. Because no
obligation-search producer exists, its searched-source collection is honestly
empty and carries
<code>search_basis_state=not_established</code>; N11 dependency edges remain a
separate <code>source_provenance</code> collection and cannot populate that
field. The envelope has no
<code>bounded_complete</code> constructor or production issuer. That keeps the
typed refusal real without turning an unresolved research question into a
positive code contract.

### Ratified rider and projection bindings

These are authority constraints on the existing design, not authority to build
a family/coverage subsystem:

| invariant | binding DS17 consequence | anchor |
| --- | --- | --- |
| <code>INT-K02</code> | Every δ statement content-binds its declared obligation set and maintained assumptions and visibly carries the relative-basis rider. A field/chip name alone is not passage. | <code>docs/system-design-decisions/int-wave-claim-semantics-ratification.md:117-128</code>; projection-side categorical blocker <code>PV-K05</code> at <code>docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:152-164</code> |
| <code>INT-R9</code> Option B / <code>INT-K04</code> / <code>INT-K07</code> | Each valid receipt remains local; no first-positive, sequence, cumulative, or family-wise probability is emitted. The family theorem constrains a hypothetical governed family; it does not authorize DS17 to create one. | <code>docs/research/policy-operations/audits/int-r9/int-r9-amendment-verification.md:112-122</code>; ratified standing at <code>docs/system-design-decisions/int-wave-claim-semantics-ratification.md:257-265,286-310</code> |
| <code>INT-K05</code> | Preserve the canonical per-problem root. The view is never a parent risk scope, merged ordinal, reset, second ledger, or cross-scope total. | <code>docs/system-design-decisions/int-wave-claim-semantics-ratification.md:160-172</code> |
| <code>INT-R10</code> corrected local semantics | <code>budget_delta</code> is a root policy ceiling, not a member-event probability or ordinal-zero reservation; class allocations partition it, and spend is the exact sum of prospective schedule reservations. | <code>docs/research/policy-operations/audits/int-r10/int-r10-revision-verification.md:264-278</code>; local owner arithmetic at <code>docs/research/policy-operations/int-r10-family-wise-risk-composition.md:215-237,257-274</code> |
| <code>INT-R9-H-002</code> anti-narrowing | <code>known_incomplete</code> and material <code>open_world_unresolved</code> are NO-GO for the affected action. A narrower action needs a new prospective scope and envelope; changing the displayed claim after inspection cannot make the old action satisfied. | finding <code>INT-R9-H-002</code> at <code>docs/research/policy-operations/audits/int-r9/int-r9-independent-audit.md:136</code>; accepted repair at <code>docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:213-226</code> |
| <code>S0-K05</code>, <code>S0-K06</code>, <code>S0-K07</code> | Receipt, validation, transport, hash, and Atlas projection mint no authority. Candidate/local accounting may continue under a declared unknown, while protected use remains blocked. | ratified dispositions at <code>docs/system-design-decisions/stage0-custody-kernel-ratification.md:94-101</code>; precise seam at <code>docs/research/policy-operations/consolidation/stage0/stage0-consensus-kernel.md:128-170</code>; band rule at <code>docs/system-design-decisions/stage0-custody-kernel-ratification.md:155-176</code> |
| <code>PV-K04</code>, <code>PV-K06</code> | The human projection may reduce detail but never amplify truth, certainty, authority, currency, or permission. MACHINE byte identity proves transport fidelity only; the twin separately performs exact protected-query evaluation over the declared finite response schema. A closed exact-or-blocked result algebra makes missing/unsupported/out-of-model/incomplete evaluation observable as typed blocking, never safe parity; v1 has no unproved conservative arm. | <code>docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:138-150,166-180</code>; timeout, missing-input, inconsistent-model, and unowned-approximation falsifiers <code>F21-A/B/D/E</code> at <code>docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:145-149</code> |

### Complete blocker/refusal vocabulary against the INT-R1 witness test

The raw ledger carrier does **not** have a finite reason-code denominator.
Two independent derivations establish that finding:

1. a structural declaration/projection walk finds both runtime and semantic
   <code>refusal_code</code> declared as arbitrary non-empty strings and copied
   into the semantic projection, with proof-profile values constrained only to
   be present for ineligible profiles
   (<code>src/polisyos/runtime/quality/confidence_ledger.py:600-626,830-845,3378-3394,4284-4301</code>);
2. a separate emission/validator walk finds arbitrary
   <code>ConfidenceLedgerError.code</code> forwarded by the owner resolver and
   arbitrary caller <code>code: str</code> persisted by
   <code>record_owner_failure</code> through unvalidated
   <code>model_copy</code>, so even empty/malformed strings can reach persisted
   runtime state as a poison event despite the declared field constraint; later
   event/receipt revalidation fails, so they are not valid canonical values.
   Two complete declaration derivations—the Pydantic
   <code>model_fields</code> denominator and an independent annotation/AST
   walk—agree on 39 frozen-check fields. A validator AST walk directly
   interprets 36; <code>schema_version</code>, <code>proof_detail</code>, and
   <code>refusal_code</code> are only content-bound through the complete
   <code>model_dump</code>/hash comparison and are not semantically
   interpreted. A naive token walk returns 37 because it counts
   <code>model_dump</code> as a field reference; that disagreement is reported,
   not reconciled into the denominator
   (<code>src/polisyos/runtime/quality/confidence_ledger.py:1548-1569,1604-1622,2771-2789,2896-2905</code>;
   <code>tools/quality/validation/check_layer3_gy_confidence_ledger.py:1844-1996</code>,
   with the all-field hash binding at <code>:1851-1854</code>).

The derivations disagree if they are incorrectly treated as the same
denominator, and that disagreement is not normalized away: the complete raw
carrier is unbounded, while the pre-amendment plan/artifact projection walk
appears finite because it observes only currently rendered values. The runtime
has a finite set of code-owned literal seeds **plus** arbitrary strings through
the three seams above; tests independently persist caller values outside the
literal/registry set
(<code>tests/unit/runtime/quality/test_confidence_ledger.py:2442-2460,2866-2875</code>).
The previous plan's **current rendered** blocker list does have a complete
denominator of five. A lexical enumeration of that list and an independent
union of the registry's three proof-profile refusals plus the derived current
coverage and appointment states both return exactly
<code>{open_world_unresolved, coverage_argument_missing,
non_anytime_valid, owner_theorem_unavailable,
institutional_authority_unappointed}</code>.

C01/C02 must therefore define a closed, **tagged** DS17 projection vocabulary
instead of echoing the raw string. A flat blocker enum would permit impossible
states such as an obligation assessment on an instrument row or
<code>over_spend</code> inside an available packet. The complete cross-layer
union is eight, but its four semantic slots remain disjoint: C01 owns the seven
available-domain values; C02 alone owns transport and
<code>SourceBlockedReason.over_spend</code>. C00 binds the red contract and C06
derives the implemented union independently from every emitter branch,
reporting disagreement rather than normalizing it:

| complete DS17 reason-value union (8/8) | typed slot | INT-R1 concrete witness? | derivation rule |
| --- | --- | --- | --- |
| <code>known_incomplete</code> | <code>CoverageAssessment</code> (2 members) | only with a non-empty admitted concrete-witness tuple; the label/string alone is never evidence | real coverage-witness receipt and refs |
| <code>open_world_unresolved</code> | <code>CoverageAssessment</code> | no — this is specifically the no-concrete-witness arm | unresolved closure/remainder and zero admitted witnesses |
| <code>coverage_argument_missing</code> | <code>InstrumentBlocker</code> (4 members) | no — this is a statistical instrument's missing coverage argument, not an omitted obligation source | registry/profile resolution, never raw-code equality |
| <code>non_anytime_valid</code> | <code>InstrumentBlocker</code> | no — proof timing validity says nothing about obligation inclusion | registry/profile resolution |
| <code>owner_theorem_unavailable</code> | <code>InstrumentBlocker</code> | no — an unavailable instrument theorem is not a missed obligation or unsound validator witness | registry/profile resolution |
| <code>other_runtime_refusal</code> | <code>InstrumentBlocker</code> | no — catch-all preserves fail-closed posture and expressly carries no coverage semantics | valid owner-grounded refused/owner-error outcome with a non-empty unrecognized raw code; empty/malformed source is invalid instead |
| <code>institutional_authority_unappointed</code> | <code>AppointmentPosture</code> (1 negative member) | no — appointment absence is an authority blocker, not coverage evidence | complete configured appointment-ref denominator |
| <code>over_spend</code> | <code>SourceBlockedReason</code> (1 member) | no — exact risk-budget failure is not obligation incompleteness | exact allowset of five N11 spend/determinism diagnostics plus independent <code>recomputed_total_spend</code> arithmetic |

The amendment's two independent finite projection derivations agree at eight:
the tagged-type cardinality is <code>2 + 4 + 1 + 1</code>, while the separate
emitter-branch walk returns two assessment branches, four owner-grounded
instrument mappings including catch-all, one empty-appointment branch, and one
source-blocked branch. There is no disagreement. C01 repeats both derivations
for its 7-value available-domain subset; C02/C06 repeat them for the full 8/8
cross-layer union.

The transport discriminator is separately exhaustive:
<code>{available, source_blocked, artifact_missing, invalid_source}</code>.
Only <code>source_blocked</code> carries a
<code>SourceBlockedReason</code>. Exact replay-pin disagreement is HTTP 409 with
the existing <code>governed_projection_replay_pin_mismatch</code> code
(<code>src/polisyos/runtime/http/routes/governed_projections.py:178-187</code>),
not a packet arm or domain blocker. Neither transport failures nor replay
conflict are INT-R1 witnesses.

The source-blocked allowset is exactly
<code>{semantic_forged_spend_row, semantic_total_spend_drift,
semantic_budget_status_drift, semantic_deterministic_spend_nonzero,
deterministic_real_run_spend_nonzero}</code>. A structural branch walk derives
the first three from row/aggregate/budget comparisons and the last two from the
real artifact's deterministic-check invariants
(<code>tools/quality/validation/check_layer3_gy_confidence_ledger.py:1976-1983,2152-2180,2394-2401</code>).
An independent parameterized reachability walk over all three real
deterministic checks returns the same five-code allowset. Its coherent-total
variant changes one deterministic row above δ, recomputes the row/aggregate
display, duplicated semantic event/check rows, accounted evidence rows,
N9/N12 fields and edges, and every hash, and deliberately holds
<code>within_budget=true</code>;
it reaches the forged-row, semantic-deterministic, real-run-deterministic, and
budget-status members. Its stale-total variant retains the old total fraction
while binding the displayed total to the recomputed rows and recomputing every
hash; that additionally reaches <code>semantic_total_spend_drift</code> without
introducing an outside diagnostic. There is no disagreement. Even one of those
codes is insufficient. After resolving the complete current-check/event
denominator, the isolated worker defines
<code>recomputed_total_spend = Σ current projected check.spend</code> and must
prove <code>recomputed_total_spend &gt; registry.policy.delta</code>. The persisted
<code>projection.total_spend</code> field is never the gate. The complete
issue set must be a non-empty subset of that allowset; any validator issue
outside it yields
<code>invalid_source</code>, even if its text sounds budget-related. The
falsifier therefore recomputes exact row/total decimals and all dependent
hashes instead of freezing numeric source fields.
<code>independent_coverage_producer_missing</code> remains an unknown-remainder
disclosure reason, not a blocker code; it contributes to the derived
<code>open_world_unresolved</code> arm.

A valid, non-empty, unrecognized raw refusal may be retained as content-bound
expert/source provenance, but it cannot directly populate any typed reason
slot, select an INT-R1 assessment, or appear as a promotion certificate. Its
only gate effect is the explicit
<code>InstrumentBlocker.other_runtime_refusal</code> catch-all. Empty/malformed
raw codes fail source admission as <code>invalid_source</code>. This closes the
P32/P37 seam without changing N11 or inventing a coverage-search producer.

### GY-GAP1 output and DS17 reachability

GY-GAP1 is a real in-process substrate, not a research sketch. It adds
content-derived <code>decisive_predicate</code> rows beside the complete 15-row
<code>class_gate</code> denominator and validates them against the bound N9 run
scope. The closure is literal: removing one decisive instance keeps the class
denominator total and green while the authority result turns red
(<code>docs/plans/active/layer3-slices/GY-engine-subordination.md:4703-4716</code>;
<code>docs/superpowers/journals/2026-08-19-gy-gap1-obligation-instance-identity.md:667-673</code>).

Two independent complete derivations of the issue vocabulary ultimately agree,
but the first naïve AST pass disagreed 6 versus lexical 5 because it counted the
payload-field key <code>obligation_instance_id</code> as an issue-code value.
That 6/5 disagreement is retained as a method finding; it is not averaged or
silently reconciled. Restricting the structural selector to dictionary values
whose key is exactly <code>code</code>, then cross-checking the bounded lexical
walk against both focused behavioral tests, returns five in both valid
derivations:

| complete GY-GAP1 validator issue denominator (5/5) | INT-R1 concrete witness? | DS17 treatment |
| --- | --- | --- |
| <code>decisive_obligation_omitted</code> | yes — it names the expected decisive obligation instance that is absent | admitted as <code>known_incomplete</code> only from the real validator receipt plus bound replay input and scope |
| <code>duplicate_obligation_instance_id</code> | no — the validator detected identity corruption; that is not evidence that the validator is unsound or that an applicable obligation is missing | invalid source / no coverage arm selected from the code |
| <code>obligation_instance_identity_mismatch</code> | no — detected binding corruption is not validator-unsoundness | invalid source / no coverage arm selected from the code |
| <code>unexpected_decisive_obligation_instance</code> | no — an extra instance alone does not witness a missed applicable obligation | invalid source / no coverage arm selected from the code |
| <code>decisive_obligation_substituted</code> | no on its current issue payload — it names an unequal row but does not itself prove which INT-R1 omission/unsoundness category holds | invalid source unless a separately admitted concrete-witness receipt proves the category |

The source derivation is exhaustive at
<code>src/polisyos/runtime/quality/promotion_sequence.py:3135-3197</code>; the
behavioral derivation exercises all five outcomes at
<code>tests/unit/runtime/quality/test_promotion_sequence.py:279-381</code>.
Calling <code>validate_canonical_promotion_receipt</code> reaches that validator
in process
(<code>src/polisyos/runtime/quality/promotion_sequence.py:2477-2485</code>).
The persisted OM-01 witness is real: it removes
<code>sha256:e851d66c2bd10d68316fa0b3e74aab1b973648434fb6ed614312acd0e7c9aac4</code>,
the decisive <code>ValueGateReceipt#transport_wmr_hash_equals_receipt_wmr_hash</code>
instance, while retaining 15 class rows
(<code>architecture/policy_design_case/layer3_gy_promotion_contract.json:2635-2652</code>).
Independent <code>jq</code> and recursive Python JSON derivations agree that its
<code>contract_lane_anytime_refusal</code> source receipt has 17 rows = 15
class-gate + 2 decisive-predicate rows; the writer selects that exact scenario
for OM-01
(<code>tools/quality/validation/check_layer3_gy_promotion_contract.py:240-255</code>).
They also agree on 10 <code>satisfied</code>, 2 <code>failed</code>, 2
<code>scope_insufficient</code>, and 1
<code>not_applicable_data_only</code> class status. “Class denominator green”
is the writer's exact 15-member tuple
totality check; it does not mean every class row or the pre-mutation protected
action was green. OM-01 makes the receipt validator red on a fixture already in
verification-only <code>shadow</code> posture.

That witness is **not** bound to DS17's selected scope. The GY fixture uses
<code>owner_scope_key=design-problem:frozen_n9_contract</code>; the N11 artifact
uses <code>owner_scope_key=frozen-owner-bundle:n10+n13b</code> and a distinct
scope ID
(<code>architecture/policy_design_case/layer3_gy_promotion_contract.json:183-193</code>;
<code>architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json:396-445</code>).
The current HTTP tree has no route for GY-GAP1, and a structured complete walk
of the one DS17 N11 source artifact finds zero
<code>obligation_instance_id</code>, <code>obligation_role</code>,
<code>source_obligation_ref</code>, or
<code>source_obligation_content_hash</code> fields, zero promotion-contract refs,
and zero promotion rows. A separate <code>jq</code> walk returns the same zeros.
The GY-GAP1 record also says the confidence artifact was deliberately left
stale for a later joint reissue
(<code>docs/superpowers/journals/2026-08-19-gy-gap1-obligation-instance-identity.md:24-32,652-665</code>).

Therefore GY-GAP1 makes omission verification executable in process and
persists a witness for its own N9 scope, but supplies **no concrete INT-R1
witness bound to DS17's scope**. The current packet consequently derives
<code>open_world_unresolved</code>; the production
<code>known_incomplete</code> arm is unreachable until a canonical receipt plus
bound replay input and matching verifier receipt arrive for this exact scope,
or the selected N11 artifact is legitimately reissued with that chain.

C01 proves the result is derived rather than hardcoded in two directions. It
must reject the real GY fixture with a typed scope-mismatch validation failure,
and a
test-only content-bound witness input carrying the exact DS17 assessment key
(scope, source, rule, purpose, audience, cutoff/expiry, and challenge state)
must move the derivation to <code>known_incomplete</code> with its ref. This
tests the consumer/derivation port; it does not create an obligation-search
producer or claim a current witness. A merely shaped dict, issue string, caller
boolean, or cross-scope GY receipt is rejected under P32/P37.

### DS11 overlap and frontend wait

DS11's in-flight branch was compared against its merge base twice:
<code>git diff --name-status</code> and <code>git diff --raw</code> both returned
exactly **63 changed paths**. There is no disagreement.

- 37 are under <code>apps/runtime-dashboard/**</code>;
- 5 are under <code>architecture/atlas_surfaces/**</code>;
- 2 are under <code>src/polisyos/**</code>;
- 19 are plans, receipts, references, tests, tools, or other companions.

The two DS11 source paths are Scientist posture paths, not DS17 runtime/HTTP
paths. DS11 does not touch the runtime OpenAPI schema or generated client family.
Thus C01 and C02 below are path-disjoint and may execute before DS11 lands.

The hard wait begins before C03 because generated-client completion writes
<code>apps/runtime-dashboard/src/api/types.ts</code>. C02 is deliberately the
independent <code>src/polisyos/ + schemas/</code> lane and writes the canonical
OpenAPI schema before that wait. After DS11 lands, rebase is still forbidden:
start or fast-forward by the repository's approved append-only integration
procedure from a fresh attached execution branch. Then re-derive the 63-path
set against the actual DS11 merge, check the DS17 path intersection, and proceed
only if the frontend/register paths are clean.

DS17 must not edit DS11's
<code>apps/runtime-dashboard/e2e/ds11-runtime-dashboard.visual.spec.ts</code>,
its snapshots, or its evidence. DS17 also must not edit DS6's
<code>apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts</code> or its
content-bound snapshot root.

## Canonical design

### One source, one projection, two consumers

~~~text
verified persisted N11 artifact
        |
        v
governed source adapter + isolated owner validator
        |
        v
exact risk-spend / instrument / unresolved-coverage projector
        |
        v
review-protected replayable HTTP packet
        |
        +-------------------+
        |                   |
        v                   v
Cycle Board DS17 panel   exact-byte MACHINE download
        |
        v
DOM-to-packet parity verifier
~~~

There is no UI ledger, second registry, or hand-authored class list. The domain
projector imports the canonical N11 registry/receipt vocabulary, expands class
weights generically, resolves proof profiles and routes, and recomputes all
spend/status predicates. The HTTP layer validates the persisted N11 artifact
through the isolated governed-projection validator before it is projected.

### Domain projection contract

The strict, frozen domain models use <code>extra="forbid"</code> and exact
rational values. The proposed contract includes:

- <code>ConditionalDeltaAmount</code>: exact numerator, denominator, canonical
  decimal, semantic role, obligation class if applicable, one two-disclosure
  conditional rider, mandatory <code>scope_id</code> and
  <code>owner_scope_key</code>, and mandatory content-bound
  <code>coverage_envelope_ref</code> plus hash; construction receives and
  resolves the envelope rather than trusting a shaped ref;
- <code>ObligationClassRiskSpend</code>: allocation, spent,
  <code>remaining=max(allocation-spent, 0)</code>,
  <code>overspend_amount=max(spent-allocation, 0)</code>, instrument/check refs,
  and good-event refs for one class;
- <code>InstrumentInstanceRow</code>: role, class, instrument/profile/route,
  certificate ref, execution/outcome, spend, anytime-validity, support,
  eligibility, and an optional blocker from the closed four-member
  <code>InstrumentBlocker</code>; any raw runtime refusal is separate source
  provenance and never the gate;
- <code>InstrumentDefinitionRow</code>: all 13 definitions and their proof
  posture, clearly separated from instances;
- <code>PositivePromotionCertificateRegister</code>: eligible entries, exact
  population count, population state, authority-appointment resolution, blocker
  codes, and typed “would populate when” predicates;
- <code>GoodEventPosture</code>: the existing union-bound clause, every executed
  probabilistic good-event ref, and an explicit no-independence-claim flag;
- <code>ConfidenceLedgerRiskSpendProjection</code>: source scope, all 15 class
  rows, instrument sections, positive register, coverage envelope with its
  two-member <code>CoverageAssessment</code>, appointment posture, overall
  promotion status, the fixed one-scope/no-family disclosure, separate
  source-provenance rows, and source/projection hashes. It accepts exactly one
  <code>ConfidenceRiskBudgetScope</code>; there is no family, parent-scope, or
  cross-scope aggregate field. Its validator requires every amount's
  <code>scope_id</code> and <code>owner_scope_key</code> to equal both the
  resolved envelope scope and this top-level scope; swapping another valid
  single-scope envelope is a hard scope/family claim failure.

The shared production-domain/MACHINE evaluator returns one closed
<code>ProjectionSafetyEvaluation</code> tagged union:

- <code>{status: "exact"}</code>; or
- <code>{status: "blocked", reason}</code>, where <code>reason</code> is exactly
  one of <code>timeout</code>,
  <code>missing_input_or_incomplete_history</code>,
  <code>parser_or_schema_failure</code>,
  <code>unsupported_or_out_of_model</code>,
  <code>empty_consistency_set</code>,
  <code>model_observation_inconsistent</code>, or
  <code>unproved_approximation</code>.

There is no boolean <code>safe</code>, arbitrary-string reason, fall-through
default, or v1 <code>proved_conservative</code> arm. Adding a future conservative
arm requires a proof-bearing contract change; it cannot be inferred from
transport parity or a sampled search.

Every amount is created by one constructor that resolves the exact envelope,
content-binds its declared set and maintained assumptions, and requires one
fixed chip carrying both disclosures:

> ≤ δ relative to the declared obligation set

> Local accounting for this exact confidence scope; no family or sequence-level
> claim is asserted.

No optional/bare δ type crosses the domain-to-HTTP boundary. The UI receives no
primitive δ number outside <code>ConditionalDeltaAmount</code>.

### ObligationCoverageEnvelope: derived negative assessment

The DS17 v1 envelope is a surface projection, not a claim of global coverage.
Its public constructor does not accept an assessment. The producer first
resolves every supplied existing-runtime witness receipt, content-binds it to
the exact protected action and scope, and derives:

- <code>known_incomplete</code> iff at least one admitted receipt proves an
  INT-R1 concrete-witness category; <code>known_incomplete_witness_refs</code>
  is then non-empty and exact;
- <code>open_world_unresolved</code> iff that admitted-witness tuple is empty
  while closure/remainder is unresolved;
- no <code>bounded_complete</code> member, constructor, dormant flag, or
  deserialization arm.

The current N11 source supplies an empty admitted-witness tuple, so it derives
<code>open_world_unresolved</code>. Independently of the selected negative arm,
the producer derives:

- declared scope from N11's exact
  <code>ConfidenceRiskBudgetScope</code>, the registry's complete 15-class
  declared denominator, and reviewer/expert/machine purpose;
- searched sources as an explicit empty tuple with
  <code>search_basis_state=not_established</code>, rendered as “no governed
  obligation search is established; source provenance is not a search”;
- N11's content-bound projection/dependency edges and owner-bundle refs/hashes
  as separate <code>source_provenance</code> rows that may establish replay and
  source identity only;
- exclusions as an explicit empty tuple with
  <code>exclusion_basis_state=not_established</code>, rendered as “no governed
  exclusion basis is established; none declared does not mean none exist”;
- unknown remainder as at least one typed
  <code>independent_coverage_producer_missing</code> row with cardinality
  <code>not_estimated</code> and probability
  <code>not_calibrated</code>;
- obligation-language/schema/rule refs from the canonical registry and N11
  scope;
- source cutoff as <code>not_established</code> when the artifact does not
  supply one;
- TTL as <code>not_issued_known_incomplete</code> or
  <code>not_issued_open_world_unresolved</code>, matching the derived arm, with
  no infinite or fabricated expiry;
- authoritative-for only conditionality disclosure and declared-set
  accounting; may-not-use-for includes promotion authority, publication,
  bounded completeness, and world completeness.

Both the declared-set and scope-locality disclosures remain in the MACHINE
packet even though PUBLIC is not an authorized DS17 audience. A future positive
assessment requires a versioned contract addition backed by an independent
producer, scorer, governance record, challenge route, and persistence. DS17
does not add a dormant boolean that a caller can flip to
<code>bounded_complete</code>, and it does not build an obligation-search
producer. GY-GAP1 is consumed only as an already-recomputed concrete-witness
input when its receipt, replay input, verifier provenance, and complete
assessment key match the exact DS17 scope. The persisted GY fixture does not
match and is rejected; no such production input exists today.

### Promotion/status calculus

The projector, not the browser, recomputes the visible promotion posture. A
certificate can enter the positive register only if all of these are true:

1. the owner-validated N11 projection contains a promotion-role row;
2. execution is completed and outcome is supported;
3. the registry-bound proof profile is anytime-valid;
4. the row supports its obligation and is eligible for promotion;
5. total and per-class risk are within exact budget;
6. an admitted coverage envelope supports the protected use;
7. the relevant institutional authority is appointed and independently
   resolved.

At the planning base, conditions 6 and 7 fail and there are zero N9 rows.
The DS17 source contract therefore carries a complete, code-owned denominator
of verified promotion-authority appointment refs. Its v1 producer can construct
only <code>NoPromotionAuthorityAppointment</code>, with that denominator equal
to the empty tuple and a scope that says “this PolicyOS runtime”; callers cannot
self-assert a positive arm. Emptiness of that exact denominator is
<code>recomputed</code> and permits the scoped copy “institutional authority
unappointed in this PolicyOS runtime.” Sufficiency of any future positive
appointment remains <code>not_established</code> until a separate institutional
resolver supplies content-bound, independently verified evidence. DS17 neither
appoints an institution nor defines the positive verifier.

The visible overall status reuses the runtime promotion vocabulary:
<code>not_promoted</code> for the current state and
<code>certified_current_valid</code> only when the complete owner chain produces
it. “Hard blocker” is presentation severity attached to runtime blocker reason
codes, not a second authority status.

The weakest condition vetoes the aggregate. <code>within_budget=true</code> is
never enough to render promotable. Zero spend plus unresolved coverage remains
not promoted.

The veto cannot be evaded by narrowing after inspection. While either negative
coverage assessment remains bound to the protected action, per-class headroom
is accounting information only and no subset/narrowed claim may render as
satisfied. A genuinely narrower protected action is a new prospective scope
with a new identity, envelope, cutoff, and admission; DS17 neither constructs
nor retrofits it.

Every decisive gate predicate is frozen with its P37 establishment class:

| decisive predicate | admission class | permitted effect |
| --- | --- | --- |
| exact total/per-class spend and allocation | <code>recomputed</code> from registry weights and checks | may establish only arithmetic within-budget |
| proof-profile, route, anytime-validity, support, and eligibility | <code>recomputed</code> from registry-bound rows | may establish only instrument posture |
| persisted N11 source validity and semantic/dependency hashes | <code>recomputed</code> by the isolated non-producing worker using N11's canonical validator; common-validator dependence remains declared | may admit the source for projection, never establish coverage independence |
| over-spend blocker reason for a rejected source | <code>recomputed</code> only when the complete issue set is a non-empty subset of the exact five-code N11 spend/determinism allowset and independently derived <code>recomputed_total_spend &gt; registry.policy.delta</code>, then content-bound to the validator receipt; persisted <code>projection.total_spend</code> never turns the gate | may select only <code>source_blocked/over_spend</code>; either signal alone falls back to generic invalid |
| Bayesian/non-anytime refusal posture | <code>recomputed</code> from the valid canonical registry/profile and real refused check, when present | may hard-block a row inside the available packet; raw labels/eligibility/refusal strings may not |
| negative coverage assessment arm | <code>recomputed</code> over the complete tuple of resolve+content-bind+verifier-provenance witness receipts for the exact assessment key; zero admitted witnesses plus unresolved remainder selects <code>open_world_unresolved</code>, while a matching admitted witness input selects <code>known_incomplete</code>; the real GY fixture is rejected for scope mismatch | may select only one negative assessment and its witness refs; both block protected use |
| configured verified appointment-ref denominator is empty | <code>recomputed</code> from the complete typed v1 input tuple | may render only “unappointed in this PolicyOS runtime” |
| obligation coverage sufficient for protected promotion | <code>not_established</code> at v1; <code>bounded_complete</code> is structurally unavailable | must block promotion |
| institutionally sufficient promotion appointment | <code>not_established</code> until an independent resolver returns content-bound verified evidence | must block promotion |
| UI badge/copy, caller booleans, and packet labels | <code>consumer_asserted</code> | may never turn the gate |

P38 divergences are explicit: a true <code>within_budget</code> field can
disagree with an exact sum over δ; a caller's anytime/eligible booleans can
disagree with its bound fixed-time proof profile; a well-formed coverage ref can
resolve to either negative arm; a raw refusal string can look like a concrete
witness while its resolved evidence proves none; the same per-class headroom
can accompany an unresolved original claim and a separately identified future
narrower claim; a zero register can occur under either appointed or unappointed
authority; and a correctly labelled download can contain reserialized bytes.
The implementation must consult the distinguishing source context in each
case, not the cheap marker.

### Human information order and honestly empty state

Within the DS17 panel, DOM order and visual order are:

1. **Actual refusal and acquisition instruments** — current counts 1 and 2,
   source-bound rows, and zero-spend explanation;
2. **δ budget by obligation class** — total plus all 15 class rows, exact spent
   and remaining for the one displayed scope, with the two-disclosure
   conditional chip beside every number and no cross-scope total;
3. **Registered instrument posture** — 13 definitions and six routes, with
   ineligible/non-anytime/owner-unavailable proof states shown as blockers;
4. **Positive promotion certificates** — always rendered, even at zero;
5. **Good-event and source/replay details**;
6. **MACHINE download**.

The positive register's current zero state is not an error, loading skeleton,
404, omitted section, green “all clear,” or zero-spend certificate. Its minimum
rendered content is:

- heading: “Positive promotion certificates”;
- status: “0 issued · institutional authority unappointed in this PolicyOS
  runtime”;
- body: “No promotion certificate is currently issuable. This is a governed
  empty state, not a load failure.”;
- current coverage assessment: the derived
  <code>open_world_unresolved</code> arm; a valid concrete-witness packet instead
  renders <code>known_incomplete</code> and its exact witness ref;
- current instrument blockers: <code>coverage_argument_missing</code>,
  <code>non_anytime_valid</code>, <code>owner_theorem_unavailable</code>, and
  <code>other_runtime_refusal</code> when present in the packet;
- appointment posture: <code>institutional_authority_unappointed</code>;
- a source-derived “what would populate this register” list matching the seven
  predicates above;
- exact source scope, rule/schema, and replay link.

The valid current N11 response itself is the primary demonstration fixture. No
institutional appointment or positive certificate is needed to render a
complete, useful screen. A source error is a separate hard-blocked error state
and must never be confused with the valid zero register.

### Conditional chip interaction

Every <code>ConditionalDeltaFigure</code> renders the rider as a first-class
focusable button/chip in the same semantic figure as the number. It resolves to
an accessible details/dialog view containing:

- both always-visible disclosures: “≤ δ relative to the declared obligation
  set” and “Local accounting for this exact confidence scope; no family or
  sequence-level claim is asserted”;
- declared scope and all limitations;
- searched sources plus <code>search_basis_state</code>; in v1 this says no
  governed obligation search is established and shows no fabricated refs;
- separate N11 source-provenance refs, hashes, and availability, explicitly
  labelled as replay provenance rather than searched sources;
- exclusions plus their establishment state;
- unknown remainder, with no invented count/probability;
- obligation-language version, cutoff state, and TTL state;
- assessment and reason codes;
- authoritative-for / may-not-use-for;
- challenge route or the explicit missing-route limitation.

The chip is not a tooltip-only decoration and is present in print/keyboard/
screen-reader traversal. Closing the details view never removes the rider from
the number.

### HTTP and replay contract

Reuse the existing governed-projection route owner:

- add one internal/raw governed source projection ID whose sole value is
  <code>confidence-ledger-risk-spend</code>; the protected static route owns
  that same stable address, so there is no second unprotected raw-source slug;
- validate it in the isolated owner-validation worker by calling N11's existing
  structural/semantic <code>validate_payload</code>, not by checking names or
  hashes alone;
- add one static reviewer route before the dynamic projection route:
  <code>GET /api/v1/exports/governed-projections/confidence-ledger-risk-spend</code>;
- protect it with <code>RuntimePermission.RUNS_REVIEW</code> and a
  tenant-collection resource binding;
- return the specialized available packet when the source validates;
- when the real N11 artifact validator rejects a source, require its complete
  issue set to be a non-empty subset of the exact five-code allowset above and
  require the isolated worker's additional exact current-check/event sum to
  prove <code>recomputed_total_spend &gt; registry.policy.delta</code> before binding canonical reason
  <code>over_spend</code> into the validator receipt and returning
  <code>source_blocked</code>; that arm carries
  only the blocker code, source content hash, validator receipt ref/hash, and
  replay identity—never rejected-source numeric/certificate detail;
- derive <code>coverage_argument_missing</code> and
  <code>non_anytime_valid</code> only inside an available projection by resolving
  the valid canonical registry/profile or a real N11 refused check. They are
  not artifact-validator issue codes and cannot be selected by a raw field or
  generic drift diagnostic;
- map every other owner-grounded refused instrument outcome to the typed
  <code>other_runtime_refusal</code> catch-all only after strict source admission
  proves its raw code is non-empty; retain that raw code only as expert/source
  provenance. Empty/malformed raw refusal values are
  <code>invalid_source</code>; raw strings can neither select a coverage arm nor
  escape the hard blocker;
- keep missing sources and all unknown/malformed/other invalid sources in
  distinct typed <code>artifact_missing</code> and generic
  <code>invalid_source</code> arms; issue strings not recomputed by the canonical
  N11 worker cannot select <code>source_blocked</code>;
- support exact replay pins for artifact content, source dependency,
  projection rule, and projection hash;
- declare REVIEWER/EXPERT/MACHINE intent and deny public/promotion authority.

The OpenAPI success example uses the real measured shape: 1 refusal,
2 acquisitions, 15 class rows, 13 definitions, 0 positive certificates,
zero spend, <code>open_world_unresolved</code>, and
<code>not_promoted</code>. It is an example of a real negative state, not an
authored positive fixture.

### MACHINE twin

The dashboard hook captures
<code>response.clone().arrayBuffer()</code> before generated-client decoding.
The download returns those exact bytes without reserialization. The rendered
DOM exposes ordered semantic leaves sufficient for a test-only decoder to
reconstruct the packet, including every class, instrument, blocker, coverage
field, both conditional disclosures, status, source binding, denied use, and
limitation. Byte identity proves MACHINE transport fidelity. Separately, the
production domain validator and twin share an exact evaluator over the declared
finite packet schema; packet admission uses it before render, and the twin
compares every governed protected query against the human projection. That is
the <code>PV-K06</code> exact-evaluation proof and the <code>PV-K04</code>
no-amplification proof. Parser failure, missing/incomplete history,
unsupported/out-of-model field, timeout, empty reconstruction, or any unproved
approximation returns typed blocking/not-established; none can inherit safe
parity. Byte mutation, omitted/reordered row, hidden blocker, mismatched scope,
missing rider/locality disclosure, or changed empty-state reason fails. Any
future deliberate human reduction must replace exact reconstruction with a
proved-conservative protected-query evaluator before it is allowed.


**Architect amendment 2026-08-29 (2) — declared twin threat model.** The earlier
completeness instruction did not bound the adversary, and an unbounded
completeness demand over an in-page verifier is unsatisfiable by construction
rather than by missing capability. The twin's adversary is hereby declared to be
<strong>content and projection code</strong> — packet payload, stylesheets, and
the rendered DOM — matching this section's own enumerated failure modes (byte
mutation, omitted or reordered row, hidden blocker, mismatched scope, missing
rider/locality disclosure, changed empty-state reason). It is <strong>not</strong>
same-origin script holding privileges equal to the twin's own: such script can
replace the twin, patch <code>getComputedStyle</code>, or forge the packet, so no
paint-containment work can make an in-page verifier sound against it. Under this
model C04's property is: <em>every paint source the platform exposes is either
proved contained or refused</em>. Sources the platform deliberately hides from
page script are a declared limitation, registered in *Explicit non-closure*, not
an open defect.

## Canonical closure contract

DS17 closes only when every item has its named behavioral receipt.

- [ ] **CC01** Attached execution branch, exact base, prefix, DS7/N11 ancestry,
  and DS11 merge/wait receipt are recorded before source edits.
- [ ] **CC02** The N11 output/reachability census and both instrument-inventory
  derivations reproduce the measured sets with no disagreement. A strict
  tagged-type enumeration and an independent complete emitter walk reproduce
  the available-domain reason set at 7/7 and the cross-layer set at 8/8. A
  structural owner-diagnostic walk and parameterized reachability walk
  independently reproduce the exact five-code over-spend allowset; their
  complete denominators and any disagreement are recorded.
- [ ] **CC03** The domain projector derives all 15 exact class allocations from
  the canonical registry and recomputes spent/remaining from checks; no class or
  decimal budget is authored in UI code.
- [ ] **CC04** Every domain/HTTP δ value is a
  <code>ConditionalDeltaAmount</code> whose resolved envelope content-binds the
  declared set and maintained assumptions. Its single chip carries both the
  exact declared-set rider and the exact local-scope/no-family disclosure; a
  bare amount, shaped-only ref, or family/cross-scope aggregate cannot be
  constructed. The amount's <code>scope_id</code> and
  <code>owner_scope_key</code> must equal the resolved envelope and the one
  top-level <code>ConfidenceRiskBudgetScope</code>; swapping two otherwise valid
  local envelopes fails.
- [ ] **CC05** The executable v1 coverage envelope contains declared scope,
  searched sources plus establishment state, exclusions, unknown remainder,
  language version, cutoff, and TTL state. Its caller cannot select the
  assessment: zero admitted witnesses plus unresolved remainder derives
  <code>open_world_unresolved</code>; a content-bound witness input with the exact
  assessment key derives <code>known_incomplete</code> with its exact witness
  ref, while the existing GY-GAP1 fixture is rejected for scope mismatch;
  <code>bounded_complete</code> is structurally absent. N11 dependency refs are
  retained only as separate source provenance; they cannot populate searched
  sources, and a witness-shaped dict/string/boolean is rejected.
- [ ] **CC06** Empty exclusions carry
  <code>exclusion_basis_state=not_established</code>; they never mean exhaustive
  no-exclusions.
- [ ] **CC07** Actual instances render before definitions and positives:
  1 refusal, 2 acquisition, and 0 positive rows from the real artifact.
- [ ] **CC08** The 13-definition registry is visibly distinct from the
  3-instance register, and the conformance-only row is not counted as a
  promotion certificate.
- [ ] **CC09** The positive register remains present at zero, says
  “unappointed in this PolicyOS runtime” from the recomputed empty configured
  denominator, distinguishes valid empty from load failure, and states the
  source-derived population criteria. Positive appointment sufficiency remains
  not established.
- [ ] **CC10** The valid zero register and all 15 zero-spend class rows render
  demonstrably from the real N11 HTTP packet without a positive appointment.
- [ ] **CC11** A raw ledger source whose headings, instrument/check IDs, chip
  marker, and <code>within_budget</code> input stay unchanged while exact spend
  crosses δ canonically recomputes duplicated semantic/accounted/N9/N12
  dependents, row/total decimals, and every hash.
  Its complete validator issue set must be a non-empty subset of the exact
  five-code N11 spend/determinism allowset. Only when the independently derived
  <code>recomputed_total_spend &gt; registry.policy.delta</code>
  agrees does it become the typed
  <code>source_blocked/over_spend</code> HTTP arm and change the DOM to a hard
  blocker with no promotable clothing or rejected-source numbers; any outside
  diagnostic remains <code>invalid_source</code>.
- [ ] **CC12** A canonical N11 session persisted in harness scratch attempts a
  Bayesian promotion check while interval label, role, panel markers, and
  caller eligibility stay constant. Registry/profile resolution produces the
  real refused check <code>coverage_argument_missing</code>; the available HTTP
  packet gains the hard-blocked instance, the DOM changes, and the positive
  register remains zero. No nonexistent raw coverage field is mutated.
- [ ] **CC13** The same canonical-session construction for fixed-time and other
  non-anytime-valid profiles produces real <code>non_anytime_valid</code> refused
  checks that render as hard blockers; changing copy, caller eligibility, or UI
  badges cannot upgrade them.
- [ ] **CC14** Either negative coverage arm, unappointed authority,
  over-spend, invalid source, or any row-level blocker vetoes aggregate
  promotability; zero spend never grants it. Keeping the original envelope
  negative while narrowing its displayed claim/headroom cannot render
  satisfied; only a separately identified prospective action can be assessed.
- [ ] **CC15** The isolated owner validator imports and executes N11's real
  semantic validator, binds dependency/source/projection hashes, and fails
  closed on malformed, stale, or changed bytes.
- [ ] **CC16** The static HTTP route has <code>runs.review</code> authorization,
  tenant resource binding, the four typed transport arms, exact replay, and an
  honest negative OpenAPI example. The complete validator issue set must be a
  non-empty subset of the exact five-code N11 spend/determinism allowset, and the
  independently derived <code>recomputed_total_spend &gt; registry.policy.delta</code>
  must agree, before the route can select
  <code>source_blocked/over_spend</code>; every other validator issue is
  <code>invalid_source</code>. Bayesian/non-anytime/owner-theorem/catch-all
  instrument blockers live only in the available packet after owner
  resolution. Replay-pin mismatch remains the existing HTTP conflict, not a
  packet arm. No arm exposes untrusted rejected-source details.
- [ ] **CC17** OpenAPI, both generated runtime clients, canonical twins,
  package types, and dashboard types reproduce from two scratch roots with
  zero byte drift. The checked-in OpenAPI schema lands in pre-DS11 C02; C03
  proves it unchanged while completing the clients after the frontend wait.
- [ ] **CC18** The Cycle Board panel consumes the generated client, validates
  the specialized packet, never caches authority, and renders independently of
  the Cycle Board query.
- [ ] **CC19** Every rendered δ figure has one visible, focusable conditional
  chip with both exact disclosures. Removing either disclosure, changing its
  resolved declared-set/assumption binding, or introducing family/cross-scope
  language—or swapping a second valid scope/envelope pair while preserving
  number, label, chip marker, and wrapper—fails semantic, a11y, and DOM-parity
  tests with
  <code>DS17-DELTA-FAMILY-CLAIM</code> where applicable.
- [ ] **CC20** MACHINE bytes equal the captured response exactly. Separately,
  the shared production-domain/twin evaluator covers the declared finite packet
  schema under <code>PV-K06</code>, returns only
  <code>ProjectionSafetyEvaluation.exact</code> or one of the seven closed typed
  blocker reasons, and makes every protected human query equal or more
  conservative under <code>PV-K04</code>. The <code>F21-A/B/D/E</code> timeout,
  missing-input, model-observation-inconsistent, and unproved-approximation
  mutations each select their observable blocked reason; no boolean/default or
  unproved conservative arm exists. Hiding the empty register, negative
  assessment, denied use, locality rider, or unknown remainder fails.
- [ ] **CC21** PUBLIC cannot access or be named as an intended audience; no
  public δ claim, promotion, publication, or DS12/DS13 work enters the slice.
- [ ] **CC22** DS17 owns
  <code>ds17-confidence-ledger-risk-spend.semantic.spec.ts</code>,
  <code>ds17-runtime-dashboard.visual.spec.ts</code>, and its own snapshot root;
  DS6 and DS11 visual specs/snapshots remain byte-identical.
- [ ] **CC23** DS11 is merged before the first dashboard or Atlas-register
  write, and the re-derived path intersection is recorded.
- [ ] **CC24** Targeted backend/frontend/auth/OpenAPI/a11y/visual/register
  checks pass, all falsifiers fail for their semantic reasons, only approved
  paths changed, and the committed attached branch is read back after writing.

## Path and widening budget

### Mechanism ceiling

P39 accounting counts implementation mechanisms, not mandatory plan/journal,
tests, nearest-parent README updates, generated outputs, release fragment,
register bytes/report, snapshots, or tests that pin a moved constant. The three
README companions and the Atlas writer's fixed report are mandatory, not
optional expansion; excluding them leaves the 18-path mechanism derivation
unchanged.

This amendment changes no mechanism arithmetic. The two-arm assessment is
derived in C01's already-declared
<code>runtime/quality/obligation_coverage.py</code>; the second disclosure lives
inside C04's already-declared <code>ConditionalDeltaFigure</code>; and both new
behavioral falsifiers are P39 test companions. The declared set remains **18**
and the hard ceiling remains **22**.

The declared mechanism set is derived from the exact cluster paths:

~~~text
C01 domain producer/contracts              2
C02 governed source + HTTP bridge          6
C03 generated ABI                          0
C04 dashboard consumer                     9
C05 Atlas writer/governance                1
C00/C06 admission and closeout             0
                                            --
declared unique mechanism paths           18
one bounded seam reserve per C01/C02/C04/C05
                                             4
                                            --
hard slice-wide mechanism ceiling         22
~~~

The four-path reserve is not permission to expand scope. It can be spent only
when a named cluster property cannot be closed within its declared paths and
the new path is the smallest owner-correct seam. Any 23rd mechanism path,
new route, second source artifact, second UI host, or new positive coverage arm
requires a plan amendment.

### Widening-round budget

| cluster | mechanism cap | widening rounds | independent property buckets |
| --- | ---: | ---: | --- |
| C00 | 0 | 0 | admission/census/red shells only |
| C01 | 2 | 2 | derived-negative coverage contract; exact ledger/instrument calculus |
| C02 | 6 | 3 | source-owner validation; specialized auth/replay; OpenAPI semantics |
| C03 | 0 | 1 transaction | generated-family reproduction only |
| C04 | 9 | 3 | transport/MACHINE; conditional rendering; honest-empty/blocker behavior |
| C05 | 1 | 1 | surgical Atlas disposition + owned visuals |
| C06 | 0 | 1 transaction | review/verification/readback only |

For every review finding, record NEW class or same class one level deeper.
On the second finding in one class, stop instance repair: widen the mechanism to
the property or declare a bounded residual and run its falsifier. A worked
example of an already declared residual consumes no further round.

## Cluster plan

### C00 — admit the slice and bind real reds

**Mechanism cap:** 0. **Widening:** 0.

**Allowed P39 companions:**

- this plan;
- execution journal
  <code>docs/superpowers/journals/2026-08-27-ds17-confidence-ledger-risk-spend.md</code>;
- new backend red tests named below.

The debt register, LEDGER, generated artifacts, frontend disposition register,
and all production paths remain untouched.

**Red-first tests:**

- <code>test_every_delta_amount_requires_the_coverage_envelope_ref_and_rider</code>;
- <code>test_coverage_assessment_moves_on_admitted_witness</code>;
- <code>test_negative_coverage_cannot_be_rescued_by_claim_narrowing</code>;
- <code>test_ds17_reason_algebra_matches_every_emitter</code>;
- <code>test_ds17_over_spend_allowset_matches_every_owner_diagnostic</code>;
- <code>test_over_spend_recomputes_blocker_when_display_markers_stay_constant</code>;
- <code>test_bayesian_interval_without_coverage_never_enters_positive_register</code>;
- <code>test_valid_zero_positive_register_is_not_missing_or_loading</code>;
- <code>test_confidence_ledger_risk_spend_operation_is_typed_and_protected</code>.

C00 is backend-only. It must not create a dashboard, visual, or Atlas test
shell before DS11 lands. The frontend reds begin in C04 and the visual/register
reds begin in C05, after the hard wait.

The HTTP red asserts the required typed, review-protected operation and must
fail on the current missing operation/404. A baseline assertion that the route
is absent is green entry evidence, not a red test, and is not accepted.

**Acceptance:** both prerequisites and DS11 state are re-read; two census methods
and two inventory methods reproduce the entry receipts; test collection proves
the named red set; every failure points to missing DS17 behavior rather than an
import/tooling failure. Record exit before filtering any test output.

~~~bash
git rev-parse --show-prefix
git status -sb
git symbolic-ref -q HEAD
git merge-base --is-ancestor 74f26ca2d HEAD
ds7_rc=$?
git merge-base --is-ancestor f41d49071 HEAD
n11_rc=$?
printf 'ds7=%s n11=%s\n' "$ds7_rc" "$n11_rc"
~~~

**Commit boundary:** <code>test(atlas): bind DS17 risk-spend reds</code>.

### C01 — typed derived-negative coverage and exact ledger projection

**Mechanism cap:** 2. **Widening:** 2.

**Add:**

1. <code>src/polisyos/runtime/quality/obligation_coverage.py</code>
2. <code>src/polisyos/runtime/quality/confidence_ledger_surface.py</code>

**P39 tests:**

- <code>tests/unit/runtime/quality/test_obligation_coverage.py</code>
- <code>tests/unit/runtime/quality/test_confidence_ledger_surface.py</code>
- existing focused confidence-ledger tests required by importer impact.

**Mandatory P39 documentation companion:**

- <code>src/polisyos/runtime/quality/README.md</code>, updated for the two new
  public domain modules and their negative-only authority boundary.

**Red-first falsifiers:**

1. remove the envelope ref, or swap a second valid local envelope/scope while
   keeping δ number, decimal, label, chip text, and semantic role;
2. change a check's exact spend over δ while retaining its labels, IDs, chip
   marker, and <code>within_budget=true</code> input, but canonically recompute
   exact row/total decimals and dependent hashes;
3. set a Bayesian/fixed-time row's caller-supplied eligibility to true while
   retaining the registry's ineligible proof profile;
4. remove one class from the registry, duplicate one class, or change one pool
   weight while leaving 15 UI labels untouched;
5. turn exclusions into an empty tuple without the
   <code>not_established</code> basis;
6. supply an empty unknown remainder or a numeric estimate/probability;
7. attempt to construct <code>bounded_complete</code> or an infinite TTL;
8. populate a caller-authored appointment flag while the complete verified-ref
   denominator remains empty;
9. copy N11 source-provenance edges into searched sources while the governed
   search basis remains not established;
10. while assessment labels, δ figures, headroom, and display markers stay
    constant, inject a test-only content-bound witness input carrying the exact
    DS17 assessment key: the assessment must move from
    <code>open_world_unresolved</code> to <code>known_incomplete</code> with the
    exact ref; the real cross-scope GY fixture and a shaped dict/string/boolean
    must fail;
11. keep the original negative envelope while presenting a narrower subset or
    per-class headroom as satisfied; it must remain NO-GO unless a new
    prospective action identity and envelope are admitted;
12. supply a valid non-empty unrecognized raw refusal while all display markers
    are fixed: it must become
    <code>InstrumentBlocker.other_runtime_refusal</code> and must not change the
    coverage assessment; empty/malformed values fail source admission.

**Implementation:**

- define the strict two-arm negative envelope and negative appointment posture;
- derive assessment only from resolved, content-bound, verifier-provenance
  witness inputs with the exact assessment key; leave the production tuple
  empty at v1, reject the scope-mismatched GY fixture, and use a harness-only
  matching witness to prove the dormant arm is behavioral rather than a
  constant;
- derive scope and source-provenance disclosures from owner-validated N11
  inputs, but emit searched sources as empty/not-established until a real
  obligation-search producer exists;
- derive all 15 allocations through
  <code>ConfidenceLedgerRegistry.obligation_weights</code>;
- group spend by class × instrument using exact <code>Fraction</code> values;
- keep definition, instance, conformance, refused candidate, and positive
  certificate sets disjoint;
- recompute eligibility and over-spend from registry-bound values;
- emit the three disjoint available-domain reason slots (two coverage
  assessments, four instrument blockers, one appointment posture); map valid
  non-empty unrecognized owner-grounded raw refusal strings to the hard-blocking
  instrument catch-all without coverage semantics;
- bind every amount to the envelope;
- emit the good-event posture without an independence claim;
- produce content-bound projection/source hashes.

**Acceptance:** the two measured obligation derivations and both 7-value
available-domain derivations agree; every negative fails at the domain
boundary; current
real inputs produce 15 class rows, 3 actual instances, 13 definitions, 0
positive entries, derived <code>open_world_unresolved</code>, and
<code>not_promoted</code>. The real GY fixture is rejected as cross-scope; the
matching content-bound test witness changes only the derived arm and witness
refs to <code>known_incomplete</code>; narrowing does not rescue it. No source
artifact or checker is modified, and no coverage-search producer is built.

~~~bash
git rev-parse --show-prefix
uv run pytest \
  tests/unit/runtime/quality/test_obligation_coverage.py \
  tests/unit/runtime/quality/test_confidence_ledger_surface.py \
  tests/unit/runtime/quality/test_confidence_ledger.py -q
git rev-parse --show-prefix
.venv/bin/python -m ruff check \
  src/polisyos/runtime/quality/obligation_coverage.py \
  src/polisyos/runtime/quality/confidence_ledger_surface.py \
  tests/unit/runtime/quality/test_obligation_coverage.py \
  tests/unit/runtime/quality/test_confidence_ledger_surface.py
~~~

**Commit boundary:** <code>feat(runtime): project conditional confidence risk</code>.

### C02 — owner-validated governed source and reviewer HTTP bridge

**Mechanism cap:** 6. **Widening:** 3.

**Add:**

1. <code>src/polisyos/runtime/http/services/confidence_ledger_risk_spend_contracts.py</code>
2. <code>src/polisyos/runtime/http/services/confidence_ledger_risk_spend_projection.py</code>

**Modify:**

3. <code>src/polisyos/runtime/http/services/governed_projections.py</code>
4. <code>src/polisyos/runtime/http/services/governed_projection_validation_worker.py</code>
5. <code>src/polisyos/runtime/http/routes/governed_projections.py</code>
6. <code>src/polisyos/runtime/http/openapi_contract.py</code>

**P39 tests:**

- <code>tests/unit/runtime/http/test_confidence_ledger_risk_spend_contracts.py</code>
- <code>tests/unit/runtime/http/test_confidence_ledger_risk_spend_projection.py</code>
- <code>tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py</code>
- existing governed-projection service, worker, API, authz, replay, and OpenAPI
  hardening tests.

**Mandatory P39 documentation companions:**

- <code>src/polisyos/runtime/http/services/README.md</code>;
- <code>src/polisyos/runtime/http/routes/README.md</code>.

**Pre-DS11 governed schema companion:**

- <code>schemas/runtime_api_v1.openapi.json</code>, emitted only by the
  canonical exporter after C02 source freeze. This is the requested independent
  <code>schemas/</code> contract lane; it is not a hand-authored second schema.

**Red-first falsifiers:**

1. present-but-malformed N11 JSON;
2. valid field names with one forged nested content/projection hash;
3. owner validator absent, timed out, or dependency bytes changed during check;
4. generic dynamic route available while the protected static route is absent;
5. no <code>runs.review</code>, unknown authz, wrong tenant binding, or PUBLIC
   audience;
6. source/replay pin mismatch;
7. artifact missing versus valid-zero source;
8. raw exact spend crosses δ while labels, IDs, chip marker, and
   <code>within_budget</code> input stay constant; exact row/total decimals and
   dependent hashes are recomputed. Parameterize a coherent-total variant over
   all three real deterministic checks and a stale-total-fraction variant whose
   display remains bound to the recomputed row total. Both variants also
   recompute duplicated semantic event/check rows, accounted evidence rows,
   N9/N12 fields and edges, decimals, and hashes, so all five reachable owner
   diagnostics are exercised without an outside diagnostic. A complete
   non-empty issue set contained in
   the five-code spend/determinism allowset plus agreeing exact
   <code>recomputed_total_spend &gt; registry.policy.delta</code> may select over-spend. Any outside
   issue, allowlisted issue without agreeing arithmetic, or arithmetic without
   an allowlisted issue remains generic invalid;
9. a real scratch <code>ConfidenceLedgerSession</code> attempts Bayesian and
   fixed-time promotion while labels/roles/caller eligibility stay constant;
   canonical registry/profile resolution must persist refused checks with
   <code>coverage_argument_missing</code> / <code>non_anytime_valid</code>;
10. open-world coverage or unappointed authority hidden from the packet;
11. arbitrary owner-grounded raw refusal string while the typed projection
    markers remain fixed: a valid non-empty value becomes
    <code>other_runtime_refusal</code>, never a coverage assessment or positive
    certificate; empty/malformed value remains <code>invalid_source</code>.

**Implementation:**

- add the N11 artifact to the governed source denominator and catalog under the
  same <code>confidence-ledger-risk-spend</code> ID used by the protected static
  route;
- project only fields required by the strict domain input;
- add worker metadata and a real N11 validator invocation;
- preserve N11 dependency/source/semantic hashes in the packet;
- compose the specialized reviewer/expert/machine available packet and the
  <code>source_blocked/over_spend</code> arm only when the complete validator
  issue set is a non-empty subset of the exact allowset and the independent
  exact <code>recomputed_total_spend &gt; registry.policy.delta</code> check/event
  sum agrees; persisted <code>projection.total_spend</code> never gates; expose no
  rejected-source numeric or certificate fields;
- keep the four transport arms, two coverage assessments, four instrument
  blockers, appointment posture, and one source-blocked reason as disjoint
  tagged fields; replay conflict stays at the existing HTTP owner;
- keep Bayesian and non-anytime refusal inside the available projection by
  resolving canonical registry/profile data and real refused checks; use an
  injected owner-source adapter only in tests to read a canonical scratch
  session, never a hand-authored response or second production source;
- add the static route before the dynamic projection path and prove route
  resolution cannot fall through to the generic unprotected handler;
- reuse <code>RUNS_REVIEW</code> and tenant-collection authorization;
- bind exact replay addresses and conflicts;
- publish the measured honest-negative OpenAPI example;
- freeze C02 source, acquire the generated-family token, run the canonical
  OpenAPI exporter, reproduce the schema from two fresh scratch roots, write
  <code>schemas/runtime_api_v1.openapi.json</code>, and release the token.

**Acceptance:** real artifact → worker validation → domain projection → static
HTTP response is one tested available chain. Marker-constant raw over-spend
with canonically recomputed numeric displays/hashes traverses the exact
allowlisted issue subset + negative-only recomputation → typed source blocker →
API receipt; any mixed/outside issue set remains invalid. Both cross-layer
derivations close at 8/8. A real N11 scratch session produces the Bayesian
and non-anytime refused checks, which traverse the available projection → API
receipt. C04/C05 extend both paths to DOM behavior. Missing and generic-invalid
sources remain distinct and hard-blocking. The generic route cannot bypass
reviewer authorization for the specialized surface. The checked-in OpenAPI
schema contains the operation before DS11; source, schema, validator receipt,
and response bytes have distinct named identities.

~~~bash
git rev-parse --show-prefix
mkdir -p _build/.tmp
git rev-parse --show-prefix
ds17_schema_a=$(mktemp -d _build/.tmp/ds17-schema-a.XXXXXX)
git rev-parse --show-prefix
ds17_schema_b=$(mktemp -d _build/.tmp/ds17-schema-b.XXXXXX)
git rev-parse --show-prefix
test -d "$ds17_schema_a"
git rev-parse --show-prefix
test -d "$ds17_schema_b"
git rev-parse --show-prefix
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output "$ds17_schema_a/runtime_api_v1.openapi.json"
git rev-parse --show-prefix
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output "$ds17_schema_b/runtime_api_v1.openapi.json"
git rev-parse --show-prefix
cmp "$ds17_schema_a/runtime_api_v1.openapi.json" \
  "$ds17_schema_b/runtime_api_v1.openapi.json"
git rev-parse --show-prefix
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json
git rev-parse --show-prefix
uv run pytest \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_contracts.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_projection.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py \
  tests/unit/runtime/http/test_governed_projection_service.py \
  tests/unit/runtime/http/test_governed_projection_validation_worker.py \
  tests/unit/runtime/http/test_governed_projection_api.py -q
~~~

**Pre-DS11 stop:** commit C02 with backend source and the reproduced checked-in
OpenAPI schema, then stop. Do not write any dashboard or Atlas path until the
DS11 merge receipt is recorded.

This is the producer/contract parallel lane requested by the slice:
authoritative DTO/route work lands under <code>src/polisyos/</code> and its
canonical generated contract lands under <code>schemas/</code> without entering
the contended frontend tree. The bounded intermediate branch state is explicit:
the schema is current and the generated clients are intentionally stale, so the
full runtime-contract drift check must be red only on those client outputs.
This branch cannot merge or claim ABI closure in that state; C03 is the required
completion transaction after DS11.

**Commit boundary:** <code>feat(api): expose governed confidence risk spend</code>.

### C03 — DS11 wait, then generated-client completion

**Mechanism cap:** 0. **Widening:** one regeneration transaction.

**Hard start condition:** DS11 is merged; a fresh attached DS17 execution branch
contains C01/C02 by the approved append-only integration procedure; both
independent DS11 diff derivations have been re-run; no DS17 dashboard or Atlas
path was written before this point.

**Read-only precondition:**

- <code>schemas/runtime_api_v1.openapi.json</code> must reproduce byte-for-byte
  from frozen C02 source before any client writer runs. It remains C02-owned and
  must not move in C03.

**P39 generated/release companions:**

1. <code>packages/runtime-api-client/types.ts</code>
2. <code>packages/runtime-api-client/runtimeApiClient.ts</code>
3. <code>packages/runtime-api-client/runtimeApiClient.js</code>
4. <code>packages/runtime-api-client/canonicalRuntimeApiClient.ts</code>
5. <code>packages/runtime-api-client/canonicalRuntimeApiClient.js</code>
6. <code>apps/runtime-dashboard/src/api/types.ts</code>
7. <code>release-fragments/unreleased/2026-08-27-ds17-confidence-ledger-risk-spend.toml</code>

**Red first:** at entry, the runtime contract drift check must fail specifically
because the generated clients do not yet match the already-current schema. A
schema drift, an extra stale path, or a green check is a C02/marker failure and
blocks C03.

Reacquire the generated-family token. Reproduce the OpenAPI schema to two fresh
scratch roots and prove both equal the checked-in C02 bytes, then run canonical
client writers only; never hand-edit governed JSON or generated TypeScript.
Reproduce every generated client output from two fresh scratch roots and
compare exact bytes.

~~~bash
git rev-parse --show-prefix
mkdir -p _build/.tmp
git rev-parse --show-prefix
ds17_schema_verify_a=$(mktemp -d _build/.tmp/ds17-schema-verify-a.XXXXXX)
git rev-parse --show-prefix
ds17_schema_verify_b=$(mktemp -d _build/.tmp/ds17-schema-verify-b.XXXXXX)
git rev-parse --show-prefix
test -d "$ds17_schema_verify_a"
git rev-parse --show-prefix
test -d "$ds17_schema_verify_b"
git rev-parse --show-prefix
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output "$ds17_schema_verify_a/runtime_api_v1.openapi.json"
git rev-parse --show-prefix
PYTHONPATH=src:. uv run --extra runtime --extra ml python \
  tools/ops_runners/runtime/export_runtime_openapi.py \
  --output "$ds17_schema_verify_b/runtime_api_v1.openapi.json"
git rev-parse --show-prefix
cmp "$ds17_schema_verify_a/runtime_api_v1.openapi.json" \
  "$ds17_schema_verify_b/runtime_api_v1.openapi.json"
git rev-parse --show-prefix
cmp "$ds17_schema_verify_a/runtime_api_v1.openapi.json" \
  schemas/runtime_api_v1.openapi.json
corepack pnpm --filter @polisyos/runtime-api-client run generate
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
git rev-parse --show-prefix
uv run pytest \
  tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py -q
~~~

**Acceptance:** the schema remains byte-identical and all six generated client
outputs reproduce byte-for-byte; the
specialized operation, response union, exact negative example, authorization
metadata, replay pins, and generated client method agree; the release fragment
declares additive API and generated-client compatibility. No DS11 generated
output/evidence is altered.

**Commit boundary:** <code>chore(api): regenerate confidence risk-spend ABI</code>.

### C04 — conditional reviewer panel and exact MACHINE twin

**Mechanism cap:** 9. **Widening:** 3.

**Add:**

1. <code>apps/runtime-dashboard/src/features/runs/api/useConfidenceLedgerRiskSpend.ts</code>
2. <code>apps/runtime-dashboard/src/features/runs/domain/confidenceLedgerRiskSpend.ts</code>
3. <code>apps/runtime-dashboard/src/features/runs/components/ConditionalDeltaFigure.tsx</code>
4. <code>apps/runtime-dashboard/src/features/runs/components/ConfidenceLedgerRiskSpend.tsx</code>
5. <code>apps/runtime-dashboard/src/features/runs/export/confidenceLedgerRiskSpendTwin.ts</code>

**Modify:**

6. <code>apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.tsx</code>
7. <code>apps/runtime-dashboard/src/api/queryKeys.ts</code>
8. <code>apps/runtime-dashboard/src/shared/i18n/locales/en.json</code>
9. <code>apps/runtime-dashboard/src/shared/i18n/locales/uk.json</code>

**Forbidden production paths:** app route registry, workspace registry,
standalone navigation, DS6 visual spec/snapshots, DS11 visual spec/snapshots,
DS11 trust feature, and any public route. DS17 is a child panel of the existing
reviewer Cycle Board.

**P39 tests:**

- <code>apps/runtime-dashboard/src/features/runs/api/useConfidenceLedgerRiskSpend.test.tsx</code>
- <code>apps/runtime-dashboard/src/features/runs/domain/confidenceLedgerRiskSpend.test.ts</code>
- <code>apps/runtime-dashboard/src/features/runs/components/ConditionalDeltaFigure.test.tsx</code>
- <code>apps/runtime-dashboard/src/features/runs/components/ConfidenceLedgerRiskSpend.test.tsx</code>
- <code>apps/runtime-dashboard/src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx</code>
- <code>apps/runtime-dashboard/src/features/runs/export/confidenceLedgerRiskSpendTwin.test.ts</code>
- existing Cycle Board page/parity/consumer-census tests;
- existing i18n parity tests.

**Red-first falsifiers:**

1. same number, label, data-testid, and wrapper while the chip is removed, one
   of its two disclosures is removed, its resolved set/assumption binding is
   changed, its locality copy is changed into a family claim, or another valid
   local scope/envelope is swapped in;
2. feed the captured typed blocker response produced by the C02 raw
   marker-constant over-spend mutation while keeping visual copy and instrument
   labels constant;
3. feed the captured available response produced by the C02 canonical N11
   scratch-session Bayesian refusal while keeping row label/role/caller
   eligibility constant;
4. valid zero register versus artifact-missing response;
5. zero register section omitted from DOM;
6. class/instrument row removed or reordered;
7. raw response bytes reserialized before download;
8. either negative coverage arm presented as loading, success, bounded
   complete, or a satisfied narrowed claim;
9. one query failure blanks the sibling Cycle Board/DS17 panel;
10. PUBLIC/unauthorized user sees the panel.
11. hold response bytes, filenames, DOM/test markers, and apparent safe copy
    constant while exercising the ratified <code>F21</code> non-receipts: force
    evaluator timeout; remove one material input/history item; select an empty
    record model with no admitted controlled observation; or replace exact
    evaluation with sampled search returning “safe.” Each must return its
    distinct closed <code>ProjectionSafetyEvaluation.blocked</code> reason and
    render blocked/not-established, never parity
    (<code>docs/research/policy-operations/int-r8/falsifier-suite-and-integration-handoff.md:145-149</code>).

**Implementation:**

- use the generated static operation and existing auth-aware fetch;
- capture exact response bytes and validate/narrow the specialized packet;
- admit the packet and drive the twin through the same exact finite-schema
  protected-query evaluator; return only the closed exact-or-seven-reason
  <code>ProjectionSafetyEvaluation</code>. Unsupported/incomplete/out-of-model
  inputs, timeout, inconsistent observations, empty consistency sets, parser
  failure, and unproved approximation render typed blocking/not-established,
  never a safe budget state;
- use never-cache-authority query policy and a distinct query key;
- render refusal/acquisition first;
- route every amount through <code>ConditionalDeltaFigure</code>;
- keep both disclosures inside the one chip and reject any parent/family/
  cross-scope aggregate before render;
- expose the complete coverage details interaction;
- render definition, blocker, positive-empty, and good-event sections;
- keep source missing/invalid distinct from governed zero;
- render the over-spend source blocker from its validator receipt without
  displaying rejected-source detail, and render Bayesian/non-anytime refused
  rows from valid available packets;
- download exact captured bytes;
- preserve independent loading/error boundaries inside
  <code>CycleBoardPage</code>.

**Acceptance:** current real response renders 1/2/0 and all 15 class rows; the
zero positive register remains visible and demo-ready. The current arm is
derived <code>open_world_unresolved</code>; a validated domain fixture for a
matching witness renders <code>known_incomplete</code> with its ref, while the
real cross-scope GY fixture is rejected, and neither negative arm can be
narrowed into satisfied. The exact C02
marker-constant over-spend mutation produces the typed source blocker, while
the canonical Bayesian scratch session produces a valid available packet with
the refused row; both change the rendered state without UI-authored status
or authority. The four <code>F21-A/B/D/E</code> mutations select distinct typed
blocked results while byte/DOM markers remain fixed; only the exact evaluator
arm can satisfy MACHINE/domain parity, and there is no v1 conservative
fall-through.
No raw runtime status is mapped through a new UI enum; keyboard,
screen reader, and contrast tests pass.

~~~bash
git rev-parse --show-prefix
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run \
  src/features/runs/api/useConfidenceLedgerRiskSpend.test.tsx \
  src/features/runs/domain/confidenceLedgerRiskSpend.test.ts \
  src/features/runs/components/ConditionalDeltaFigure.test.tsx \
  src/features/runs/components/ConfidenceLedgerRiskSpend.test.tsx \
  src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx \
  src/features/runs/export/confidenceLedgerRiskSpendTwin.test.ts \
  src/features/runs/routes/CycleBoardPage.test.tsx \
  src/features/runs/routes/CycleBoardPage.parity.test.tsx \
  src/features/runs/routes/CycleBoardConsumerCensus.test.ts
git rev-parse --show-prefix
corepack pnpm --filter @polisyos/runtime-dashboard exec tsc -p tsconfig.app.json --noEmit
~~~

**Commit boundary:** <code>feat(atlas): render conditional confidence risk spend</code>.

### C05 — surgical Atlas registration and DS17-owned visuals

**Mechanism cap:** 1. **Widening:** 1.

**Architect amendment 2026-08-29 — C05 scope.** The Bayesian-without-coverage
semantic/visual witness is removed from C05's required set and registered in
*Explicit non-closure* with owner GY-N11. Its blocker is another lane's
validator contract and is not reachable from C05's single Atlas-writer
mechanism path. Everything else in C05 — the disposition-register writer, its
register/report/test companions, and every semantic and visual scenario not
requiring a real Bayesian-without-coverage packet — remains required. The
source-chain prohibitions are unchanged: no hand-authored packet, no
<code>page.route</code>, no second source artifact, no second route or UI host,
no C02 test injection, no synthesized coverage row. A remaining scenario that
needs one of those is a stop, not a workaround.


**Modify mechanism:**

1. <code>architecture/atlas_surfaces/check_frontend_disposition_register.py</code>

The writer adds one DS17 unit for the governed projection, domain validator,
conditional figure, panel, exact twin, and Cycle Board consumer. It does not
rewrite DS7/DS11 ownership or teach the checker a list of the 15 classes or 13
instruments.

**Architect amendment 2026-08-29 (3) — C05 registration shape.** The C05 preflight
correctly established, with executable mutation probes, that none of the register's
three seed extension points admits an implemented surface: <code>entries</code> is
fixed by <code>seed_policy.rules[0]</code> to one root row per DS1 <code>surface_id</code>
at <code>ds1_root_count: 261</code>; <code>subunits.scope_kind</code> is
<code>['dead_subgraph', 'legacy_continuity']</code>; and every
<code>supplemental_findings.finding_kind</code> is a debt or a declaration. Refusing to
register the surface as a <code>producer_binding_debt</code> row was correct — it would
have left the surface unregistered and attributed a GY-N11-owned closure to DS17.

The resolution is neither a new generic implemented-unit family nor any relaxation of
DS1/DS7 preservation. **DS19 owns the seed** — <code>entries</code>, <code>subunits</code>,
<code>supplemental_findings</code> — <strong>not the whole file</strong>. Post-seed slices
record themselves in their own top-level block, and the repository has done this five
times: <code>storage_construction_census</code> (DS5), <code>ds8_strangle_coverage</code>
(DS8), <code>ds8b_post_freeze_transition</code> (DS8-B),
<code>ds18_time_semantics_coverage</code> (DS18), <code>seeded_negative_lifecycle</code>
(DS19). DS17 adds one such block. It touches no seed array.

Because <code>additionalProperties</code> is <code>false</code>, a new block requires the
schema property that backs it. <code>architecture/atlas_surfaces/frontend-disposition-register.schema.json</code>
is therefore added to C05's P39 companion set — the one companion the original list omitted.
Both precedents confirm it is a companion of the checker mechanism rather than a mechanism
of its own: DS8-B's <code>ba987a3be</code> changed exactly checker + schema + test, and
DS18's <code>54f9ff4f2</code> changed checker + schema + register + test. **The mechanism
cap of 1 is unchanged.**

**Architect amendment 2026-08-29 (4) — C05 demonstrable state set.** Three C05
preflights established the same root cause from three different arms: C05 was
specified to demonstrate several packet states through the real source chain, while
the sole GY-N11 producer emits exactly one — <code>available</code>, total spend
<code>0</code>, <code>open_world_unresolved</code>, 13 instruments, 15 classes, 0
positive entries. Two requested states are not merely absent but <strong>forbidden by
the owner's own contract</strong>: <code>over_spend</code> is refused at type level
(<code>spend_numerator: Literal[0]</code> in
<code>tools/quality/validation/check_layer3_gy_confidence_ledger.py</code>, with
<code>source_flip_deterministic_proof_nonzero_spend</code> as its named refusal), and
<code>coverage_argument_missing</code> cannot enter an owner-admitted packet under the
N9 promotion-row bind recorded in amendment (1).

C05's required demonstration is therefore narrowed to <strong>the one state the
producer can emit</strong>. The <code>over_spend</code> end-to-end semantic/visual
witness joins the Bayesian-without-coverage witness in *Explicit non-closure*, owner
GY-N11. Scope the debt exactly: the over-spend <em>gate</em> is implemented and proved
at domain level against constructed inputs, and that proof stands; what is absent is
only the path from a real owner artifact through HTTP to a rendered visual. Recording
"over-spend is unproved" would be false.

Everything else in C05 remains required and is reachable without packet variety: the
disposition-register block and its schema property, the checker validation, its test,
the writer-owned report, and every semantic and visual scenario of the real state. The
source-chain prohibitions are unchanged and are what produced these three correct
stops: no hand-authored packet, no <code>page.route</code>, no second source artifact,
no second route or UI host, no C02 test injection, no synthesized coverage row, and no
mutated or fabricated owner content under any artifact root.

**Architect amendment 2026-08-29 (5) — the DS18 landing reconciliation is DS17's, and
amendment (3)'s wording is narrowed.** Amendment (3) said a slice "must not change
another slice's block". That was written to forbid rewriting DS18's semantics or
weakening its validator; as worded it also forbade the one action DS18 explicitly
assigns to its consumers, and the C05 preflight correctly stopped on it.

DS18's own block carries <code>frontend_freeze_commit</code>, which arms
<code>post_freeze_is_landing_red</code> in
<code>check_frontend_disposition_register.py:16094-16104</code>, and its stored
<code>landing_slice_rule</code> reads: <em>"the slice landing a post-freeze production
render/export root owns its fresh file/root receipt, independent classification, and
behavioral proof."</em> The measured checker output is five
<code>ds18_time_semantics_landing_slice_reconciliation_required</code> errors plus two
<code>file_receipt_drift</code> and one <code>root_inventory_drift</code> — all eight
DS17-owned, and five of them named in DS18's own reconciliation vocabulary.

**DS17 therefore performs the DS18 landing reconciliation.** It is not a cross-slice
edit in the sense (3) forbade; it is the designed path, and DS15 travelled it before
DS17. The reconciliation supplies, for DS17's own paths only: fresh file and root
receipts, the recomputed <code>source_file_count</code>, <code>root_count</code>,
<code>file_manifest_sha256</code> and <code>root_manifest_sha256</code>, an independent
classification of each new root, and the behavioral proof the rule names.

**Still forbidden, and this is what (3) meant:** altering DS18's
<code>landing_slice_rule</code>, <code>frontend_freeze_commit</code>,
<code>schema_id</code>, <code>predicate_provenance</code>, scanner receipt or exclusion
policy; weakening any DS18 validator or its historical frozen replay; touching a row for
a path DS17 did not change; or reconciling by editing the scanner rather than the census.
Every number DS17 writes into that block must come from executing DS18's own scanner and
must be reported with its executor.

**Architect amendment 2026-08-29 (6) — the third classification terminal, and (5)'s
"scanner" narrowed.** The fifth C05 stop reports only two options: label decision-bearing
roots <code>non_decision_bearing</code>, or reopen C04 to add temporal chrome. **There is a
third, and the slice landing immediately before DS17 used it.**

DS18 does not let anyone <em>label</em> a root; the builder <em>derives</em> the
classification at <code>check_frontend_disposition_register.py:15770-15779</code>. A root
falls to <code>non_decision_bearing</code> only when it is in no strict-projection file,
is no primary root, <strong>and has no owner</strong>. A decision-bearing root whose
temporal semantics live in an admitted ancestor classifies as
<code>inherits_admitted_dom</code>, and that branch increments both
<code>obligated_roots</code> and <code>covered_roots</code> — it is not an escape from
obligation, it is the designed answer for inherited temporal ownership.

The owner comes from the content-bound maps
<code>DS18_TIME_SEMANTICS_ROOT_INHERITANCE</code> and
<code>DS18_TIME_SEMANTICS_CROSS_FILE_INHERITANCE</code>. **DS15 populated the first of
these in <code>8c20b6f74</code>, "DS15 reconcile acquisition surfaces with DS18 freeze",
touching checker + register + test and <strong>not</strong> the scanner.** DS17 does the
same for its own roots.

**Amendment (5)'s prohibition on "reconciling by editing the scanner" means the scanner:
<code>architecture/atlas_surfaces/decision_time_semantics_scan.mjs</code>.** It does not
reach the checker's inheritance maps, which are the delegated reconciliation surface. The
checker is already DS17's declared mechanism path 18, so this adds no path.

**The truth condition binds and is not optional.** <code>inherits_admitted_dom</code>
asserts that the named owner root genuinely contains the inheriting root in the rendered
DOM. Prove containment per root against the real render; do not assert it, and do not name
an owner of convenience. A root that no admitted owner actually contains is not eligible
for this terminal, and forcing it there would be the false classification the stop rightly
refused.

**Still forbidden:** editing the scanner; weakening any DS18 validator or its historical
frozen replay; touching a row, entry, or inheritance key for a path DS17 did not change;
and classifying any decision-bearing root as <code>non_decision_bearing</code>.

**Architect amendment 2026-08-29 (7) — root cause named; C04 reopens, bounded.** Six C05
stops are not six obstacles. They are **one omission surfacing at six checkpoints**: DS17
builds a decision-bearing surface, and in this repository such a surface owes a producer
that can emit the states it demonstrates (stops 1 and 3), a registration slot (stop 2), and
an admitted temporal owner (stops 4, 5, 6). C04 built and froze the panel with **zero**
temporal chrome — <code>as_of</code>, epoch, validity and staleness counts are all 0 in
<code>ConfidenceLedgerRiskSpend.tsx</code> and <code>ConditionalDeltaFigure.tsx</code> —
while every DS18-admitted decision surface carries it (<code>RunReportPage.tsx</code>
epoch=20, <code>RunDeckPage.tsx</code> epoch=12). C05 is simply where the repository asks.

The sixth stop is the limit of routing around it. <code>inherits_admitted_dom</code> requires
real containment, and DS17's panel is structurally a **sibling** of DS15's admitted owner:
in <code>AuthorizedCycleBoardPage</code>, <code>CycleBoardQueryPanel</code> and
<code>ConfidenceLedgerRiskSpendQueryPanel</code> are siblings, and
<code>AcquisitionGrowthBoundary</code> lives inside the first one's subtree. The executor
measured <code>owner.contains(risk)=false</code> and stopped exactly as amendment (6)
required.

**C04 therefore reopens, bounded to temporal semantics.** This reverses a prohibition
restated in amendments (3)–(6); the prohibition was mine and it was protecting a closure that
had never been tested against this obligation.

Scope of the reopening — additive only:

- render the temporal coordinates the packet **already carries** (<code>as_of</code>,
  <code>freshness.observed_at</code>, <code>freshness.source_as_of</code>,
  <code>freshness.state</code>) and the epoch/validity/staleness posture the DS18 regime
  requires of a decision-bearing root, with the canonical admitted-or-nonreceipt terminal;
- supply the behavioral <code>as_of</code>/epoch/validity/staleness proof DS18 names;
- both files are **already DS17 mechanism paths**, so the mechanism cap of 1 for C05 and the
  18/22 ledger are unchanged. If this appears to need a nineteenth path, stop and report.

**Everything C04 proved stays proved and is not revisited:** the browser-enumerated
paint-containment verifier, the native lane at 73/0, the closed shadow-root boundary tripwire,
and the declared twin threat model from amendment (2). This reopening adds a surface
obligation; it does not reopen the verification property.

Once the roots carry a real temporal binding they classify <code>decision_bearing</code> by
derivation, and the DS18 landing reconciliation closes on receipts and behavioral evidence
**without any inheritance claim** — no owner of convenience, no portal-local fiction.

**P39 register/test companions:**

- <code>architecture/atlas_surfaces/frontend-disposition-register.json</code>
- <code>architecture/atlas_surfaces/frontend-disposition-register.schema.json</code>
  (added by the 2026-08-29 (3) amendment above; P39 companion, not a mechanism);
- <code>architecture/atlas_surfaces/test_frontend_disposition_register.py</code>
- mandatory writer-owned report
  <code>docs/reference/frontend/atlas-frontend-disposition-register.md</code>.

**P39 visual companions:**

- add
  <code>apps/runtime-dashboard/e2e/ds17-confidence-ledger-risk-spend.semantic.spec.ts</code>
  for the full raw-source → validator → HTTP → DOM falsifiers;
- add
  <code>apps/runtime-dashboard/e2e/ds17-runtime-dashboard.visual.spec.ts</code>;
- add only snapshots under
  <code>apps/runtime-dashboard/e2e/ds17-runtime-dashboard.visual.spec.ts-snapshots/</code>;
- import the post-DS11 shared visual helper without editing it.

The DS17 visual grep is exactly <code>DS17 confidence risk spend</code>. The
spec contains:

1. a real-owner response visual for refusal/acquisition first, all-zero spent,
   unresolved coverage chip, and honestly empty positive register;
2. a fixture-only over-spend hard-blocker visual;
3. a fixture-only Bayesian-without-coverage hard-blocker visual.

Fixture-only responses are visually deterministic witnesses, never source
authority or capability closure. The real-owner HTTP/service test remains the
substantive proof. The semantic spec uses two owner-grounded scratch states: a
copied raw N11 artifact with marker-constant exact over-spend plus canonically
recomputed numeric displays/dependent hashes, and a real
persisted <code>ConfidenceLedgerSession</code> that attempts the Bayesian
promotion instrument and records the canonical
<code>coverage_argument_missing</code> refusal. It must not mutate a nonexistent
coverage field, use <code>page.route</code>, or hand-author a blocker packet. The
first chain asserts actual spend diagnostics + agreeing negative recomputation
→ validator receipt → typed source blocker → changed DOM. The second asserts
valid registry/profile resolution → available packet with refused row →
changed DOM. C01/C04's focused semantic tests separately prove the
scope-mismatch rejection, witness-shaped-input assessment movement, and
anti-narrowing rule; none is misrepresented as a current owner state or a
fourth visual. All cases keep the positive register at zero.

**Red first:** the register check must report the unregistered DS17 surface
before its surgical writer; the semantic spec must first fail because the raw
mutation does not yet reach a changed DOM; the visual grep must select exactly
3 tests and fail for missing snapshots before the single writer run.

**Acceptance:** one surgical register transaction adds only DS17 bindings; DS11
and DS7 rows are byte/semantic-preserved; corruption that removes the chip or
twin fails. The semantic e2e proves the raw over-spend and canonical
Bayesian-session state changes reach the DOM through the real service path;
focused C01/C04 tests carry the derived-assessment and anti-narrowing
falsifiers. The visual transaction has
exactly one writer followed by two identical no-writer runs, one worker, zero
retries. DS6 and DS11 visual roots are byte-identical before/after.

~~~bash
git rev-parse --show-prefix
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check
git rev-parse --show-prefix
uv run pytest architecture/atlas_surfaces/test_frontend_disposition_register.py -q
~~~

Full-chain semantic command:

~~~bash
git rev-parse --show-prefix
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm \
  --filter @polisyos/runtime-dashboard exec playwright test \
  --config=playwright.config.ts --project=chromium \
  e2e/ds17-confidence-ledger-risk-spend.semantic.spec.ts --workers=1
~~~

Exact visual commands differ only by the first writer flag:

~~~bash
git rev-parse --show-prefix
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm \
  --filter @polisyos/runtime-dashboard exec playwright test \
  --config=playwright.visual.config.ts --project=chromium \
  --grep 'DS17 confidence risk spend' --workers=1 --update-snapshots
git rev-parse --show-prefix
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm \
  --filter @polisyos/runtime-dashboard exec playwright test \
  --config=playwright.visual.config.ts --project=chromium \
  --grep 'DS17 confidence risk spend' --workers=1
git rev-parse --show-prefix
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm \
  --filter @polisyos/runtime-dashboard exec playwright test \
  --config=playwright.visual.config.ts --project=chromium \
  --grep 'DS17 confidence risk spend' --workers=1
~~~

**Commit boundary:** <code>test(atlas): prove DS17 risk-spend surface</code>.

### C06 — freeze, review, targeted verification, and branch readback

**Mechanism cap:** 0. **Widening:** one verification transaction.

Freeze all source after C05. Run independent full-delta review, then batch any
blocking finding before the expensive wave. Cosmetic post-freeze findings are
recorded in this plan's execution journal; the debt register remains out of
scope. Reopen the failure/repair register before closeout.

Verify:

- changed domain modules and all importers;
- real N11 owner validator plus malformed/over-spend/profile falsifiers;
- named reason-algebra/emitter censuses closing C01 at 7/7 and C02/C06 at
  8/8, plus structural and parameterized-reachability derivations closing the
  over-spend allowset at 5/5; record, never normalize, any disagreement;
- route authz, replay, OpenAPI, schema/client drift;
- focused dashboard, a11y, exact-byte/DOM parity, and every closed
  <code>ProjectionSafetyEvaluation</code> failure arm including
  <code>F21-A/B/D/E</code>;
- DS17-only visual transaction;
- Atlas register and corruption probes;
- architecture guardrails and ruff;
- two independent actual mechanism-path derivations against C00;
- no touched DS6/DS11 evidence, no debt-register/deep-import change;
- committed branch contents, not merely the index.

~~~bash
git rev-parse --show-prefix
uv run pytest \
  tests/unit/runtime/quality/test_obligation_coverage.py \
  tests/unit/runtime/quality/test_confidence_ledger_surface.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_contracts.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_projection.py \
  tests/unit/runtime/http/test_confidence_ledger_risk_spend_api.py \
  tests/unit/runtime/http/test_governed_projection_validation_worker.py \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py -q
git rev-parse --show-prefix
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run \
  src/features/runs/api/useConfidenceLedgerRiskSpend.test.tsx \
  src/features/runs/domain/confidenceLedgerRiskSpend.test.ts \
  src/features/runs/components/ConditionalDeltaFigure.test.tsx \
  src/features/runs/components/ConfidenceLedgerRiskSpend.test.tsx \
  src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx \
  src/features/runs/export/confidenceLedgerRiskSpendTwin.test.ts \
  src/features/runs/routes/CycleBoardPage.test.tsx \
  src/features/runs/routes/CycleBoardPage.parity.test.tsx \
  src/features/runs/routes/CycleBoardConsumerCensus.test.ts
git rev-parse --show-prefix
corepack pnpm --filter @polisyos/runtime-dashboard exec tsc -p tsconfig.app.json --noEmit
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
git rev-parse --show-prefix
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm \
  --filter @polisyos/runtime-dashboard exec playwright test \
  --config=playwright.config.ts --project=chromium \
  e2e/ds17-confidence-ledger-risk-spend.semantic.spec.ts --workers=1
git rev-parse --show-prefix
uv run pytest architecture/atlas_surfaces/test_frontend_disposition_register.py -q
git rev-parse --show-prefix
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check
git rev-parse --show-prefix
.venv/bin/python -m ruff check \
  src/polisyos/runtime/quality/obligation_coverage.py \
  src/polisyos/runtime/quality/confidence_ledger_surface.py \
  src/polisyos/runtime/http/services/confidence_ledger_risk_spend_contracts.py \
  src/polisyos/runtime/http/services/confidence_ledger_risk_spend_projection.py \
  src/polisyos/runtime/http/services/governed_projections.py \
  src/polisyos/runtime/http/services/governed_projection_validation_worker.py \
  src/polisyos/runtime/http/routes/governed_projections.py \
  src/polisyos/runtime/http/openapi_contract.py
git diff --check
git status -sb
git symbolic-ref -q HEAD
git rev-parse --show-prefix
~~~

Do not substitute full backend verify or CI parity for the targeted evidence.
Do not run <code>guardrails sync</code>. After the closeout commit, re-read the
plan, source paths, generated operation, tests, and status directly from
<code>HEAD</code>. A clean index is not branch delivery evidence.

**Commit boundary:** <code>docs(atlas): close DS17 confidence risk spend</code>.

## Timed-command and serialized-resource protocol

No timed command may feed a product/status predicate. Timing is operational
resource evidence only.

Before every timed invocation:

1. run <code>git rev-parse --show-prefix</code>;
2. record <code>uptime</code>;
3. run the exact command under <code>/usr/bin/time -p</code>;
4. capture its exit code immediately, before any pipe/filter;
5. record the second <code>uptime</code>;
6. record <code>user</code>, <code>sys</code>, selected-test count, write/no-write,
   and ceiling.

~~~bash
git rev-parse --show-prefix
uptime
git rev-parse --show-prefix
/usr/bin/time -p command-with-no-pipe
rc=$?
uptime
printf 'exit=%s\n' "$rc"
test "$rc" -eq 0
~~~

A killed process, sleeping-laptop interval, missing browser, or missing tool is
a non-receipt and sets no new ceiling. The first completed no-writer run freezes
that exact command at <code>max(30s, 2 × (user + sys))</code>; a writer uses the
same exact-source no-writer measurement. No ceiling widens mid-run.

Serialized resources:

| resource | owner cluster | rule |
| --- | --- | --- |
| N11 generated artifact | read-only throughout | no writer, no re-derivation, hash before/after |
| OpenAPI/client generated family | C02 schema stage; C03 client stage | acquire/release token per stage; schema reproduces twice in C02 and must remain byte-identical in C03; no merge while clients are stale |
| frontend disposition register | C05 | only after DS11, one surgical writer/check/corruption transaction |
| visual lane | C05 | DS17 spec/root only; one writer + two no-writer |
| dashboard dev/browser port | C04/C05 | serialize only the port/browser, not backend lint/tests |

## Behavioral falsifier matrix

| property | markers held constant | underlying mutation | required result |
| --- | --- | --- | --- |
| coverage assessment is derived | δ figures, per-class headroom, assessment/display labels, row/test IDs | inject a test-only content-bound witness-shaped input with the exact DS17 assessment key; separately submit the real cross-scope GY fixture and an unbound same-shaped dict/string/boolean | matching witness input moves <code>open_world_unresolved</code> → <code>known_incomplete</code> with exact ref; cross-scope and shape-only inputs are rejected |
| unresolved/incomplete action cannot be rescued by narrowing | negative envelope, δ figures, per-class headroom, chip and display markers | change only the presented claim/subset after the negative assessment | old action stays NO-GO and cannot render satisfied; only a new prospective scope identity/envelope may be assessed |
| over-spent scope cannot promote | headings, instrument/check IDs, <code>within_budget</code> input marker, conditional chip ID | exact check/total spend crosses δ; duplicated semantic/accounted/N9/N12 dependents, decimals, and hashes are recomputed; coherent-total and stale-total-fraction variants cover every reachable owner diagnostic | complete issue set is a non-empty subset of the exact five-code N11 spend/determinism allowset and independent <code>recomputed_total_spend = Σ current projected check.spend &gt; registry.policy.delta</code> agrees; persisted <code>projection.total_spend</code> cannot turn the gate; typed source blocker changes the DOM and exposes no rejected number |
| Bayesian CI is not a certificate without coverage | “Bayesian credible interval” label, promotion role, caller eligibility, row/test IDs | canonical scratch N11 session attempts the Bayesian instrument and records the registry/profile refusal | available packet gains <code>coverage_argument_missing</code> blocked row; DOM changes; positive register count remains 0 |
| non-anytime certificate is hard blocked | label, certificate ref, role | owner-bound profile resolves non-anytime | hard blocker and <code>not_promoted</code> |
| δ is conditional and scope-local | number, decimal, caption, DOM wrapper, chip marker | remove either disclosure; alter the resolved set/assumptions; swap an otherwise valid B envelope/scope into amount A; or make the aggregate a parent/family/cross-scope number | constructor or semantic/DOM test fails; scope swap/family claim emits <code>DS17-DELTA-FAMILY-CLAIM</code> |
| honest empty is data, not error | zero count, panel location | response changes valid-zero ↔ artifact-missing | governed empty ↔ hard source blocker; never omitted |
| exclusion emptiness is not completeness | empty exclusions array | basis changes <code>not_established</code> ↔ false positive | positive state rejected; disclosure changes |
| provenance is not search coverage | N11 source refs/hashes and conditional chip ID | copy provenance edges into <code>searched_sources</code> while <code>search_basis_state=not_established</code> | envelope construction fails; chip continues to disclose “no governed obligation search established” |
| MACHINE is exact-or-typed-blocked | response bytes, filename, DOM/test markers, and apparent safe copy | one byte is reserialized or one row is reordered/hidden; separately force <code>F21-A/B/D/E</code> timeout, missing input, inconsistent empty model, or sampled-safe approximation | transport mutation fails byte/DOM parity; each evaluator mutation selects its distinct closed blocked reason and cannot inherit exact or conservative parity |
| source validation is behavioral | field names, schema string, top-level hash shape | nested owner/projection binding changes | real validator fails; no available packet |

## Pattern pass and capability state

Reopen the failure/repair register before C00 and again before C06.

| patterns | opening risk | target pattern and acceptance signal |
| --- | --- | --- |
| P01/P02/P03/P12 | real N11 ledger exists but direct HTTP/dashboard surface is missing | existing persisted owner artifact → validated projection → protected HTTP → human/MACHINE consumers |
| P04/P05/P09/P15 | a flat reason enum permits illegal blocker combinations, or zero spend/UI copy/LLM projection launders authority | tagged reason algebra plus weakest-boundary veto; unappointed/both coverage negatives/invalid/over-spent stay <code>not_promoted</code> |
| P07/P08 | source time, observation time, cutoff, and TTL collapse | separate source identity/as-of, cutoff state, request observation, replay pins, and TTL state |
| P10/P14 | credible interval or registry membership is mistaken for coverage/independence | proof-profile resolution plus explicit coverage/independence non-receipt |
| P13/P30 | a general live-ledger/index/coverage institution or slice-named module grows around a small three-row source | two domain-function modules, one existing source, 18 declared mechanisms; live index and positive coverage stay non-closed |
| P27/P28/P31 | second ledger, second route registry, or per-number chip patch | extend canonical N11 and governed-projection owners; one amount constructor; Cycle Board host |
| P29/P32 | δ number, chip text, witness-shaped dict, cross-scope receipt, or raw refusal string stands in for resolved proof | amount type resolves/content-binds envelope; exact-scope test witness moves the assessment while the real GY fixture is rejected; raw refusal maps to catch-all; remove-property-keep-markers fails |
| P33/P34 | tests recognize only named copy or exclude a failing source incompletely | marker-constant numeric/profile mutations; sibling dynamic-route bypass; complete path/error set |
| P35/P36 | 13 definitions, 3 instances, 15 classes, or zero positives generalized from samples/prose | two complete derivations with denominators; cite N11/INT-R1 findings, not adjacent commentary |
| P37/P38 | authored <code>within_budget</code>, assessment label, unscoped “unappointed,” provenance-as-search, raw issue string, or UI badge turns the gate; narrowing tests a proxy for a new action | recomputed arithmetic/profile/source bindings, admitted witness receipts, and configured empty appointment denominator; appointment sufficiency/search basis remain <code>not_established</code>; new scope identity is mandatory; name divergent cases |
| P39 | mechanism cap counts plan/tests/generated/register/snapshots | 18 declared mechanisms + 4 bounded seam reserve = 22; companions excluded and listed |
| P40/P41 | repeated one-case repair or inherited red assigned by proximity | bucket every finding; replay exact pre-slice base and prove changed-path intersection before ownership |

The first planning red-team pass classified eight findings as **NEW** property
classes: provenance-as-search, pre-wait frontend shells, validator-to-DOM
blocker continuity, missing paper-fixture harness input, mandatory README/report
companions, wrong-polarity HTTP red, scoped appointment predicate, and
per-command path-coordinate discipline. The re-review found validator-to-DOM
continuity one level deeper (**SAME** class): payload diagnostics were being
treated as runtime refusal codes and a nonexistent Bayesian field was proposed.
That class was then found a second level deeper (**SAME** class): the initial
incomplete allowset omitted both deterministic-spend invariants. Per P40, the
plan stops instance repair and widens the property once to the complete
five-code structural + parameterized-reachability denominator, guarded by the
independent current-check/event <code>recomputed_total_spend</code> predicate;
execution therefore enters C02 at
round zero against the widened property. Bayesian/non-anytime posture comes
from a valid N11 session/registry projection. The re-review also found one
**NEW** projection-safety class: transport byte equality alone did not close
PV-K06. C04 now uses one shared exact evaluator with a closed exact-or-blocked
result algebra and the ratified <code>F21-A/B/D/E</code> falsifiers. Neither
finding adds a cluster or mechanism path. The re-review also found one **NEW**
ordering class:
scratch schema generation did not satisfy the explicit pre-DS11
<code>schemas/</code> lane. C02 now writes the governed schema and C03 completes
clients after the frontend fence. A later example in any declared class folds
into its falsifier rather than consuming another repair round.

Target DS17 surface state after closure:

<code>typed projection contract + existing persisted N11 artifact + in-slice
projection producer + governed HTTP bridge + reviewer/MACHINE consumers +
owner/source verification + negative/e2e semantic tests</code>.

The positive coverage/certificate and live deployment-wide enumeration
capabilities remain explicitly non-closed.

## Explicit non-closure

These rows are recorded here for scope honesty. The user's explicit scope keeps
the debt register untouched.

| capability | precise state | owner / closure signal |
| --- | --- | --- |
| INT-R1 <code>bounded_complete</code> issuance | <code>producer_missing + artifact_missing + bridge_missing + verification_missing</code>; INT-R1-D-003 says independence is not constructed | future independent coverage/governance lane; closure requires persisted envelope, independent scorer/governance receipt, challenge route, and N9 consumer |
| eligible positive promotion-certificate producer | <code>producer_missing</code>; current two promotion routes are fixed-time-ineligible or owner-theorem-unavailable | N9/N11 owner; closure test must execute an owner-verified, anytime-valid, coverage-bound promotion row |
| institutional authority appointments | out of scope; DS17 recomputes only that the complete configured verified-ref denominator is empty and renders the scoped negative, while appointment sufficiency remains <code>not_established</code> | real-user institution plus independent content-bound resolver, never DS17/UI |
| live deployment-wide ledger scope index | <code>absent/unallocated</code>; N11 can persist per-scope ledger state but no global typed index/HTTP owner was found | team-runtime; closure requires enumerated current scopes, receipt refs, currentness, tenant boundary, and replay |
| persisted semantic-receipt and N12 projection artifacts | <code>artifact_missing + consumer_missing</code>; N12 also says <code>epoch_not_implemented</code> | GY-N12/DS18, not DS17 |
| PUBLIC δ claim and first governed promotion | <code>surface_out_of_scope</code> here and gated by DS12/DS13 | team-design successor slices |
| C05 Bayesian-without-coverage semantic/visual witness | <code>bridge_missing</code>; a real exact-scope session persists <code>coverage_argument_missing</code>, but its <code>promotion</code>-role row cannot enter an owner-admitted <code>available</code> packet: omitting it emits <code>n9_projection_owner_binding_drift</code>, including it emits <code>day_one_positive_promotion_fabricated</code>. Proved structurally and behaviorally; persisted refusal <code>sha256:94d60c54cac8155fa3da2765a65a6c73157876211d92771cd4e85478e864fbf3</code> | GY-N11 confidence-ledger contract/validator; closure requires the validator to distinguish a governed refusal from an issued positive promotion, per ratified <code>INT-K08</code> (negative completion is a valid governed result). Never DS17's Atlas writer |
| closed shadow-root paint observation | <code>verification_missing</code>; the twin refuses every platform-observable paint source including <strong>open</strong> shadow roots (<code>confidenceLedgerRiskSpendTwin.ts:1089</code>), but <code>attachShadow({mode:"closed"})</code> makes "no root" and "a closed root" identical through <code>element.shadowRoot</code>. Creating one requires script privilege equal to the twin's own, which is outside the declared threat model above. Witness retained as an executable boundary test, not deleted | runtime-dashboard/Atlas projection-safety verifier plus the browser paint-observation substrate; closure requires provenance-complete shadow-root tracking installed before any relevant DOM creation, or a compositor paint-containment API. Neither exists |
| C05 <code>over_spend</code> end-to-end semantic/visual witness | <code>producer_missing + artifact_missing</code>; the sole N11 contract writer emits spend <code>0/1</code> deterministically and its validator types spend as <code>Literal[0]</code>, so a real over-spend artifact cannot exist. Two independent walks — 4,951 source/artifact files and 3,043 Python files by AST — found exactly one writer. <strong>The domain-level over-spend gate is implemented and proved against constructed inputs; only the real-artifact end-to-end path is absent</strong> | GY-N11 confidence-ledger contract/producer; closure requires an owner-produced artifact carrying a real non-zero spend, which today its own validator refuses. Never DS17, and never by mutating owner content |
| debt register, other-slice evidence, deep-import baseline | explicitly out of scope | no DS17 edit or closure claim |

An absent future test is <code>artifact_missing</code>, never a green receipt.
None of these non-closures prevents the real negative DS17 surface from being
demonstrated.

## File map

| role | planned home |
| --- | --- |
| derived-negative coverage assessment | <code>runtime/quality/obligation_coverage.py</code> |
| exact class/instrument/good-event calculus | <code>runtime/quality/confidence_ledger_surface.py</code> |
| persisted source | existing N11 generated JSON, unchanged |
| owner validation/catalog | existing governed projection service + isolated worker |
| specialized packet/replay | <code>confidence_ledger_risk_spend_contracts.py</code> and <code>confidence_ledger_risk_spend_projection.py</code> |
| protected HTTP | existing governed-projections router, static reviewer path |
| human host | existing global Cycle Board page, independent DS17 panel |
| conditional amount | <code>ConditionalDeltaFigure.tsx</code> |
| MACHINE/DOM parity | <code>confidenceLedgerRiskSpendTwin.ts</code> |
| visual ownership | DS17-named spec and DS17 snapshot root only |
| governance | this plan/journal plus surgical frontend disposition row; no debt-register edit |

## Issue codes

| code | meaning |
| --- | --- |
| <code>DS17-COVERAGE-OPEN-WORLD</code> | current envelope derives <code>open_world_unresolved</code> because no concrete witness is admitted and closure/remainder stays unresolved |
| <code>DS17-COVERAGE-KNOWN-INCOMPLETE</code> | admitted content-bound witness derives <code>known_incomplete</code>; missing or shaped-only witness is a validation failure |
| <code>DS17-COVERAGE-ENVELOPE-MISSING</code> | δ value lacks its envelope/rider |
| <code>DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED</code> | empty exclusions cannot imply exhaustive none |
| <code>DS17-COVERAGE-SEARCH-NOT-ESTABLISHED</code> | no governed obligation-search basis exists; provenance cannot substitute |
| <code>DS17-COVERAGE-INDEPENDENCE-MISSING</code> | no independent producer/scorer/governance record |
| <code>DS17-LEDGER-OVER-SPENT</code> | exact recomputation exceeds scope δ |
| <code>DS17-DELTA-FAMILY-CLAIM</code> | an amount/envelope/top-level scope binding mismatches, or a local amount is presented as parent, sequence-level, family-wise, cumulative, or cross-scope δ |
| <code>DS17-INSTRUMENT-NON-ANYTIME</code> | proof profile is not anytime-valid |
| <code>DS17-INSTRUMENT-COVERAGE-ARGUMENT-MISSING</code> | Bayesian CI has no admissible coverage argument |
| <code>DS17-INSTRUMENT-OWNER-THEOREM-UNAVAILABLE</code> | registered owner proof is not available |
| <code>DS17-POSITIVE-AUTHORITY-UNAPPOINTED</code> | the complete configured verified-ref denominator is empty in this PolicyOS runtime; no broader institutional fact is inferred |
| <code>DS17-POSITIVE-REGISTER-HIDDEN</code> | zero register was omitted or treated as loading/error |
| <code>DS17-SOURCE-MISSING</code> / <code>DS17-SOURCE-INVALID</code> | governed source absent or owner validation failed |
| <code>DS17-REPLAY-CONFLICT</code> | requested source/projection pins do not match |
| <code>DS17-MACHINE-BYTE-DRIFT</code> | download is not exact captured response bytes |
| <code>DS17-DOM-PARITY-DRIFT</code> | rendered DOM loses/reorders a semantic field, the shared exact evaluator returns or falls through outside its closed algebra, or any typed evaluator non-receipt is presented as safe/parity |
| <code>DS17-DS11-WAIT-VIOLATION</code> | dashboard/Atlas byte written before DS11 merge receipt |
| <code>DS17-VISUAL-OWNER-BYPASS</code> | DS6/DS11 visual spec or snapshot root was touched |

## Commit sequence

| boundary | message |
| --- | --- |
| planning hand-back | <code>docs(atlas): plan DS17 confidence risk spend</code> |
| coverage/rider amendment | <code>docs(atlas): amend DS17 coverage assessment</code> |
| C00 | <code>test(atlas): bind DS17 risk-spend reds</code> |
| C01 | <code>feat(runtime): project conditional confidence risk</code> |
| C02 | <code>feat(api): expose governed confidence risk spend</code> |
| C03 | <code>chore(api): regenerate confidence risk-spend ABI</code> |
| C04 | <code>feat(atlas): render conditional confidence risk spend</code> |
| C05 | <code>test(atlas): prove DS17 risk-spend surface</code> |
| C06 | <code>docs(atlas): close DS17 confidence risk spend</code> |

Before each commit: branch attachment, prefix, exact dirty-path list,
mechanism/round total, and cluster acceptance. No merge, push, rebase, reset,
stash storage, or unrelated cleanup.

## Execution hand-off packet

The executor receives:

- attached planning branch/base and both gate ancestry receipts;
- the N11 durable/projection/HTTP partition, including the three-family and
  zero-direct-route double derivations;
- exact 13-definition / 3-instance / 1-refusal / 2-acquisition / 0-positive
  inventory, role memberships, route counts, and N13b non-admission counts;
- the independently reproduced 15-class rational allocation table;
- the finding that INT-R1 supplies the envelope shape while ratified INT-R9
  fixes its assessment/blocking semantics; no production envelope chain exists;
- the tagged 8-value reason union, unbounded raw refusal carrier, exact
  five-code N11 spend/determinism allowset, and four transport arms;
- the derived two-arm negative-envelope ruling, including empty/not-established
  searched sources, separate N11 provenance, and structurally absent
  <code>bounded_complete</code>;
- the GY-GAP1 five-code census and reachability partition: omission validation
  is executable and its fixture persists a witness for a distinct N9 scope,
  but DS17 must reject that cross-scope receipt; the current N11 artifact has no
  matching witness and derives <code>open_world_unresolved</code>;
- the honest-empty copy/state/population contract;
- the witness-moves-assessment, anti-narrowing, marker-constant over-spend, and
  Bayesian falsifiers;
- DS11's 63-path double derivation and the precise C03 frontend wait point;
- 18 declared mechanisms, 22 hard ceiling, per-cluster rounds, and P39
  companions;
- serialized-resource/timing protocol;
- explicit non-closures and forbidden paths;
- committed-branch readback receipt.

## Non-negotiables

- Refusal and acquisition instruments render first because they are the data
  that exists.
- A positive register with zero rows is always present, explanatory, and
  demonstrable.
- Unappointed is a governed negative state, never a reason to blank a screen.
- Every rendered δ figure visibly says “≤ δ relative to the declared obligation
  set” and, in the same chip, “Local accounting for this exact confidence scope;
  no family or sequence-level claim is asserted”; both resolve to the bound
  coverage disclosures.
- No parent risk scope, cross-scope aggregate, cumulative/family number, or
  after-the-fact narrowed satisfied claim may be constructed.
- A dependency/provenance edge never counts as a searched source; the v1 chip
  visibly reports that no governed obligation search is established.
- <code>open_world_unresolved</code> is the current **derived** result, not a
  constant or loading state; an exact-scope, content-bound witness input moves
  the same derivation to <code>known_incomplete</code>, while the real GY fixture
  is rejected as cross-scope.
- No current code path issues <code>bounded_complete</code>.
- Both negative coverage arms, over-spend, and non-anytime-valid/coverage-missing
  instruments are hard
  blockers and cannot render promotable.
- Registry definitions, actual instances, conformance-only checks, acquisition
  attempts, and positive certificates remain distinct denominators.
- The N11 artifact is the persisted verification/evidence source; the UI and HTTP projection
  mint no authority.
- MACHINE bytes preserve transport exactly. The twin separately evaluates the
  declared finite schema exactly under <code>PV-K06</code>; the human projection
  cannot amplify and proves equal-or-more-conservative protected-query answers
  under <code>PV-K04</code>. Unsupported or incomplete evaluation blocks.
- REVIEWER/EXPERT/MACHINE only; no PUBLIC δ claim before DS12.
- DS11 lands before any dashboard/Atlas write.
- DS17 owns its visual spec/root; DS6/DS11 evidence stays untouched.
- No debt-register, other-slice evidence, deep-import baseline, merge, or push.
