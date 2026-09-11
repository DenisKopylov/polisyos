# Group A / 04 — Ceiling vocabulary ownership and demand

## 1. Discrepancy: the totals reproduce; the ownership inference does not

**Row claim.** `int-r2-ceiling-vocabulary-owners` distinguishes comparison owner,
value authority and terms registrar, says every crosswalk vocabulary names a
comparison owner, and uses 169 estimand files versus 132 normative files across
six packages to distinguish a vocabulary from an adjective. It allocates estimand
terms, splits legal/normative/write operations, says a normative vocabulary would
violate FM-OPS-17, and treats assurance levels as having zero consumers. Claim
baseline: `policy-engine/docs/plans/active/DEBT-REGISTER.md@63bdb9640`; the row is
not evidence for any of the measurements below.

**Measured.** The case-sensitive source-file counts reproduce **169, 132, 0, 0**.
But the six reported normative package counts sum to **122**, not 132. The complete
132-file distribution spans **twelve packages**, and its structural AST usage is
far from an even spread. Runtime alone holds 493 of 1,007 matching identifier
occurrences; a concrete `NormativeValueScheduleOwner` is the largest individual
structural concentration. Normative is used for several things, including real
typed value authorization/arbitration, not only prose. This does not establish
that the requested normative ceiling vocabulary already exists.

Estimand has a real compiler and an IR type owner, but the compiler is not the
highest-density file by either of this audit's exact-text or identifier measures.
The sound part of the inference is concentration in Foundry and IR, supported by
reading those owners. Density by itself establishes neither exclusive ownership
nor the requested binding-strength order.

The crosswalk has **two comparison-owner keys / five vocabulary entries**, not
five. All five have `semantic_owner: null` and empty registered terms. The eight
software relation fields are a different, complete set. Their presence cannot
fill the other three vocabulary entries by changing the denominator.

FM-OPS-17 specifically prohibits **another cause vocabulary** and imports SMDV-1.
INT-R2's normative authorization asks about consent/waiver/approval and scoped
institutional determinations, not movement-source diagnosis. The inference that
registering any such ceiling creates a second cause vocabulary needs an additional
equivalence premise that the cited text does not supply.

Finally, zero `assurance_level` occurrences in source is not zero demand: the
active Atlas plan expressly routes assurance levels to a DS16 grammar successor,
the published crosswalk retains an assurance-level obligation, and INT-R2 names
an assurance/closeout consumer and audit/public-verification projection. These are
planned or declared consumers, not proof of a currently deployed professional
assurance-level reader. The broader “nobody reads it” premise is not established.

**Agreement.** Separating comparison, value authority and term registration is
consistent with the delivered artifacts. The package arithmetic, universal
comparison-owner claim, adjective-only inference, FM-OPS-17 application and
unqualified consumer-zero claim do not agree with the measured scope. No
allocation, build/refusal ruling or status change is made here.

## 2. Measurements, denominators and receipts

Pin: `63bdb9640e7b76b49356cba940bab6067f1be512`. These separate invocations
from the analysis worktree returned **0**:

```sh
python3 policy-engine/docs/superpowers/journals/group-a/04-vocabularies/ast_census.py
```

```sh
python3 policy-engine/docs/superpowers/journals/group-a/04-vocabularies/exact_case_density.py
```

```sh
python3 policy-engine/docs/superpowers/journals/group-a/03-phase5/measure.py
```

```sh
python3 policy-engine/docs/superpowers/journals/group-a/04-vocabularies/distribution.py
```

The complete Python denominator is **6,178 tracked `.py` files**; the density
denominator is all **2,653 tracked `.py` files under `policy-engine/src/`**, all
inside `src/polisyos/`. Tree and index enumerations agree; no unreadable or AST
parse-error Python members. The independent duplicate visitor additionally
verified every Python input against its pinned Git blob. Full source membership,
per-file densities, definition and call identities are retained in
`policy-engine/docs/superpowers/journals/group-a/04-vocabularies/raw/census.json@sha256:cc1512b3574b1ff4c80024186dd2161dd61b2b56ceee87ef9b56dc2ee9385f2e`.

Complete compact outputs are `summary.json`, `exact-case-density.json` and
`distribution.json` in that journal directory. The last gives all package
denominators and AST definitions for nine selected delivered-owner files.
The broad query's full trace and 62 undecodable members are retained by debt 3.
No claim about a definition or call is based on text search.

### Four terms under distinct, declared instruments

“Exact text” counts a source file containing the original case-sensitive
substring, including comments and docstrings. “AST identifiers” counts matching
identifier strings case-insensitively: names, attributes, arguments, definitions,
imports and keyword names. One identifier string is counted once even if it
contains the term more than once. String constants and docstrings have separate
AST distributions in the receipt. These are different instruments, not competing
answers to an undeclared count.

| Term | Exact-text files / 2,653 | AST identifier files / 2,653 | Matching identifier occurrences | Non-docstring string files | Docstring files |
| --- | ---: | ---: | ---: | ---: | ---: |
| `estimand` | 169 | 141 | 1,813 | 117 | 55 |
| `normative` | 132 | 81 | 1,007 | 120 | 25 |
| `write_operation` | 0 | 0 | 0 | 0 | 0 |
| `assurance_level` | 0 | 0 | 0 | 0 | 0 |

The last two zeroes are **name-density results**, not mechanism or consumer
absence. Case-folded raw text gives 176 estimand files and 141 normative files;
those are also retained so capitalization cannot silently change the instrument.

### Complete package distribution

Each count below is matching files within the package's complete `.py`
denominator. `exact / AST` uses the two instruments just defined. Both
`write_operation` and `assurance_level` are 0 exact / 0 AST in **every listed
package**. All 26 buckets, including the root module, are enumerated; they sum to
2,653. Package names are directories, not institutional owner appointments.

| Package under `src/polisyos/` | All Python files | Estimand exact / AST | Normative exact / AST |
| --- | ---: | ---: | ---: |
| root module | 1 | 0 / 0 | 0 / 0 |
| berl | 31 | 0 / 0 | 0 / 0 |
| calibration | 8 | 0 / 0 | 0 / 0 |
| common | 11 | 0 / 0 | 0 / 0 |
| core | 204 | 0 / 0 | 6 / 4 |
| corpus | 5 | 0 / 0 | 0 / 0 |
| data_forge | 274 | 2 / 1 | 34 / 22 |
| data_requirement | 4 | 0 / 0 | 1 / 0 |
| ddm | 17 | 0 / 0 | 0 / 0 |
| evidence | 6 | 0 / 0 | 2 / 2 |
| fabric | 302 | 2 / 1 | 2 / 1 |
| foundry | 601 | 101 / 90 | 2 / 0 |
| ir | 191 | 33 / 29 | 5 / 4 |
| legal_requirement | 4 | 0 / 0 | 1 / 0 |
| lex | 45 | 0 / 0 | 9 / 2 |
| method_requirement | 4 | 0 / 0 | 0 / 0 |
| obligation_graph | 4 | 0 / 0 | 0 / 0 |
| obligation_rules | 2 | 0 / 0 | 0 / 0 |
| participation_requirement | 1 | 0 / 0 | 0 / 0 |
| pdc | 8 | 0 / 0 | 2 / 2 |
| policy_grammar | 9 | 0 / 0 | 0 / 1 |
| runtime | 301 | 19 / 12 | 37 / 23 |
| schemas | 2 | 0 / 0 | 0 / 0 |
| scholar | 28 | 0 / 0 | 0 / 0 |
| scholar_requirement | 3 | 0 / 0 | 0 / 0 |
| scientist | 587 | 12 / 8 | 31 / 20 |
| **Total** | **2,653** | **169 / 141** | **132 / 81** |

The ten omitted exact-text normative files are in `data_requirement` (1),
`evidence` (2), `fabric` (2), `foundry` (2), `legal_requirement` (1) and `pdc` (2).
The raw row's three largest packages already hold **102/132 = 77.3%** of its files.
Calling that distribution even is not justified. Package-relative densities also
differ: Lex 9/45 versus Scientist 31/587, for example.

At identifier level, Foundry holds **1,278/1,813 = 70.5%** of estimand occurrences
and IR another 358/1,813. Normative has Runtime **493/1,007 = 49.0%**, Scientist
246/1,007 and DataForge 139/1,007; the remaining 129/1,007 occur in the other
seven nonzero packages. Normative has an internal concentration even though its
word spans more purposes and packages.

### Delivered owners, not predicted names

For estimand, AST locates a compiler with `EstimandShape`, strategy selection and
compilation into method DAG nodes in
`policy-engine/src/polisyos/foundry/methods/catalog/causal/estimand_compiler.py@63bdb9640`.
Its input algebra is defined in
`policy-engine/src/polisyos/ir/analytics/estimand.py@63bdb9640`. The former has
95 matching identifier occurrences, the latter 101. The largest two structural
files are
`policy-engine/src/polisyos/foundry/methods/catalog/network/missingness.py@63bdb9640`
(126) and
`policy-engine/src/polisyos/foundry/methods/components/consensus.py@63bdb9640`
(108), out of the complete 141-file AST-positive denominator. The compiler's
semantic role is real; literal maximum density is not what proves it. None of
these observations by itself defines the requested partial order between
estimand **binding strengths** or appoints the accountable question owner.

For normative, the largest structural file is
`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py@63bdb9640`
(167 identifier occurrences / 1,007), with `NormativeValueScheduleOwner`, typed
authorization, separate trust, signature resolution and bounded ranked emission.
The AST call trace reaches it from Runtime's generation/lifecycle bridge.
Other high-density files include the Scientist normative-arbitration node (86),
Runtime generation-cycle bridge (85), and lifecycle (82). AST and source locate
`NormativeModelCompleteness`, `NormativeAuditStatus`, rights/constraint audit
records and arbitration logic in
`policy-engine/src/polisyos/ir/analytics/normative_arbitration.py@63bdb9640`,
consumed by
`policy-engine/src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py@63bdb9640`.

Those owners are counterexamples to “only an adjective.” They are **not proof of
one universal normative owner**: value-schedule authorization, legal classification,
consent/waiver and normative arbitration have distinct authority objects. The
missing comparison is whether any existing owner supplies the exact ceiling
semantics INT-R2 requires, not whether the substring appears somewhere.

For write operations, delivered vocabulary includes `ArtifactWriteOptions` in
`policy-engine/src/polisyos/core/artifacts/write_contract.py@63bdb9640` and
`ArtifactOwnershipIndex` in
`policy-engine/src/polisyos/core/artifacts/ownership.py@63bdb9640`. The former is
manifest-write metadata; the latter records/checks tenant ownership. This is
positive evidence of writing/ownership machinery despite the zero substring.
It does not, alone, implement INT-R2's substantive right over an arbitrary
external owner's operation/object/field. That would require the actual mutation
admission path and delegation evidence, not a renamed metadata class.

### Five vocabulary entries versus eight software fields

`policy-engine/docs/reference/canonical-vocabulary-crosswalk.v1.json@63bdb9640`
has this complete five-entry `ceiling_vocabulary_rulings` object:

| Vocabulary | `comparison_owner` | `semantic_owner` | Registered terms |
| --- | --- | --- | --- |
| relation_claim_strength | `CeilingVocabulary.strength_order` | null | [] |
| capacity_stages | `CeilingVocabulary.stage_order` | null | [] |
| estimand_binding_strength | **key absent** | null | [] |
| legal_normative_write_operations | **key absent** | null | [] |
| assurance_levels | **key absent** | null | [] |

The eight fields in
`policy-engine/src/polisyos/fabric/evidence/ceiling_vocabulary.json@63bdb9640`
are population, jurisdiction, purpose_audience, source_target_context,
evidence_class, maintained_assumptions, maximum_claim_strength and
maximum_commitment_stage. All eight name `polisyos.fabric.evidence.ceiling_relations`
as software owner and an explicit relation; the top-level institutional signer is
null. This agrees with the distinction between comparison and authorization.
It does not give every one of the five vocabularies a comparison owner, and it
does not itself establish a separate populated registrar slot for each.

### FM-OPS-17 at its actual referent

The exact failure-mode row in
`policy-engine/docs/research/policy-operations/ops-r5-monitoring-diagnosis-and-adaptation.md@63bdb9640`,
**FM-OPS-17**, reads:

> OPS may define another cause vocabulary. | Import SMDV-1; fork blocks.

`policy-engine/docs/system-design-decisions/withheld-propositions-register.md@63bdb9640`,
**WP-03**, identifies SMDV-1's movement-source vocabulary: prediction_error,
implementation_failure, observation_process_change, intervention_delivery_or_version,
behavioral_response, context_or_interference, diagnosis_unresolved. Its distinction
is source of movement versus S13's accountable destination, and WP-03 itself is
withheld. A forbidden competing cause taxonomy is a specific object.

By contrast,
`policy-engine/docs/research/policy-operations/int-r2-gap-acquisition-cases.md@63bdb9640`,
**§4.7 normative_authorization**, says its ceiling is:

> Approved purpose, protocol/version, procedures, population, sites, consent/risk
> conditions and review triggers. No legal competence, execution, write or
> effectiveness follows.

The object is scoped permission/consent, with a regime-specific issuer. These
texts do not identify it with movement-source diagnosis. A proposed vocabulary
which actually reclassifies causes would engage FM-OPS-17; a vocabulary limiting
consent or permitted use does not become such a fork merely by being normative.
Whether an existing scope/permission algebra already suffices is a separate
reuse question. No new vocabulary is proposed or authorized by this report.

The legal half has the same necessary plane distinction: INT-R2 §4.6 says
PolicyOS cannot issue the mandate, but asks PolicyOS to resolve its scope and
limit uses. Debt 1 quotes the ratified anti-role and appointment rule in full.
Sovereign grant creation and a typed ceiling on evidence about that grant cannot
be classified together just from the word “legal.”

### Assurance levels beyond source names

The broad query traversed all **12,838 readable text files / 12,900 tracked paths**,
covering projections, schemas, published references, plans and withheld/research
propositions as well as source. Both register and ledger were excluded from
evidence matches. The query includes underscore/space/hyphen/adjacent spellings,
limited/reasonable assurance, ISAE and SSAE. Its output is navigation evidence,
not an exhaustive semantic consumer census; 62 undecodable files remain ambiguous.

| Surface or consumer evidence at `@63bdb9640` | What it establishes, and its limit |
| --- | --- |
| `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`, GY-AQ1 surface row | Explicitly includes assurance levels in DS16's deferred grammar successor, gated on DS7. This is active-plan demand; it is not a shipped reader. The adjacent AS1/AS3 row says their assurance level is carried here, which still needs semantic correspondence to what those batteries actually measure. |
| `policy-engine/docs/reference/canonical-vocabulary-crosswalk.md` and `policy-engine/docs/reference/canonical-vocabulary-crosswalk.v1.json` | Published reference carries the unallocated assurance-level entry and the needed engagement/subject/criteria/period, order, exclusions and issuer-independence semantics. Not zero published demand and not registered professional levels. |
| `policy-engine/tools/quality/validation/check_canonical_vocabulary_crosswalk.py` and `policy-engine/tests/repo_quality/tools/test_canonical_vocabulary_crosswalk.py` | Generated reference construction and its checks consume the vocabulary identity outside src. That is a documentation/compiler consumer, not runtime comparison of level values. |
| `policy-engine/docs/research/policy-operations/int-r2/integration-handoff-and-finding-register.md`, §1.2 independent_audit | Names assurance/closeout gate and audit/public-verification projection within report ceiling. This is the research demand and proposed chain, not an appointed provider or current chain. |
| `policy-engine/docs/research/policy-operations/int-r2-gap-acquisition-cases.md`, §4.10 | The ceiling binds subject, criteria, period/version, assurance level, scope and limitations; AUP remains distinct. External standards citations do not register recognized local terms. |
| `policy-engine/docs/research/policy-operations/consolidation/wave5/wave5-open-questions-and-next-research.md`, R2-Q03 | Retains the owner/vocabulary question with unknowns preserved. It has not disappeared because the source substring is zero. |

The delivered mechanisms use other names too. AST/source inspection of
`policy-engine/src/polisyos/lex/knowledge/multilingual_assurance.py@63bdb9640`
finds `AssurancePacket`, `CandidateAssuranceResult`, receipts and a public
`projection` carrying explicit limits, empty holders and withheld WP-11/WP-12.
This is candidate multilingual equivalence assurance; its own properties refuse
equivalence establishment. It is not an ISAE/SSAE level ordering. Likewise
`policy-engine/src/polisyos/fabric/evidence/acquisition_assurance.py@63bdb9640`
is a synthetic contract-testing adapter for eight acquisition shapes, including
independent_audit and normative_authorization. Its measured authority/terminal/
ceiling fields are not professional assurance levels. Neither an identical word
nor a different symbol family establishes equivalence.

No current runtime reader of an appointed professional assurance-level ordering
was established. The stronger claim **zero consumers/demand anywhere** is not
supported by this source-only zero and the enumerated counterexamples above.

## 3. Competing readings, costs and permissions

| Reading | What it would license | Cost / remaining evidence |
| --- | --- | --- |
| Three owner roles describe distinct responsibilities | Separate comparison implementation, external value authority and local recognized terms | Concrete per-vocabulary mapping; two of five comparison slots exist, three are absent, all five term lists empty |
| Three roles imply three different organizations | Organizational separation for every vocabulary | A further authority/independence requirement; distinct slots alone do not establish distinct people or teams |
| Foundry's estimand compiler makes it the natural software home | Reuse of existing IR/Foundry machinery | Question-owner input, semantic attribute binding, ordering/incomparability and transport evidence remain distinct from estimator selection |
| Normative means another movement-source cause taxonomy | Apply FM-OPS-17's no-fork condition | Must show the proposed terms classify the same causes as SMDV-1 |
| Normative means scoped consent/value/institutional authorization | Represent and check bounds without issuing the outside determination | Identify the correct existing owner or explicit gap; show scope, provenance/currentness and no cross-authority promotion. The concrete value owner is relevant but not automatically complete for INT-R2 |
| Assurance trigger requires a ready runtime reader of professional level values | Defer local registration until a specific reader needs it | Establish that operational trigger and preserve current plan/reference unknowns; a source name zero does not establish consumer absence |
| Assurance trigger includes active-plan projection and declared demanding gates | Treat the cited DS16/INT-R2 requirements as present demand | Resolve which levels/scope are needed and the external authority/local-recognition mapping; no appointment is supplied by a standards citation |
| Eight relation fields fully discharge five vocabulary families | Reuse those relations as the complete vocabulary answer | Requires explicit semantic mappings for the missing three, which the crosswalk does not currently contain |

## 4. What a decision would rest on

The deciding fact is the **referent of each ceiling**, its demanding consumer and
the allowed comparison/authority/registration act. Density locates candidate
owners; reading their actual contracts determines whether they own that referent.
For normative, the settlement is whether the proposed terms classify movement
causes or bound consent/value/permission. FM-OPS-17 answers the first; it does not
answer the second by adjacency. For assurance, the settlement is the intended
consumer trigger and whether the cited active-plan/public-reference demand counts
for it. For estimand, the existing compiler is evidence for reuse, while an actual
binding-strength order and justified equivalence/transport rules settle the
missing vocabulary semantics.

Pattern pass: P27/P35/P36/P38. The measured gaps are explicit comparison slots,
empty term sets and unestablished semantic mappings. No organizational owner,
registered term, institution or closure rule is created in this research lane.

## 5. What was not established

No external standards were adopted, no authority appointments checked against an
outside institution, and no deployed professional assurance consumer observed.
The broader query is not semantic proof of absence, especially for alternative
vocabularies, dynamic readers or the 62 undecodable files. The software owners
were inspected statically, not rerun as a full acquisition capability. A real
normative value owner is not proof that it handles every consent/waiver regime.
The old 24-test result was not replayed or used to discharge the five vocabulary
families. This report does not decide whether a new vocabulary is owed.
