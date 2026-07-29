---
title: "PAO-R0 — Policy Matter Identity and Episode Graph"
status: delivered_requires_amendment
kind: deep-research
research_task: PAO-R0
result_type: research_supported_with_open_owner
repository: "https://github.com/DenisKopylov/polisyos"
repository_branch: main
repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
source_artifact: sources/pao-r0-original.md
source_sha256: f7d100465e869dc75165bd6c1b7e7029bcd5ffbe5514a47df1f5343aecd2b840
source_lines: 1948
source_bytes: 121049
independent_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
consolidation_commit: a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19
amendment_date: 2026-07-29
consolidation_required: true
authoritative_for:
  - research evidence that PolicyOS needs technical custody identity above one case
  - compatibility guidance against silently reinterpreting existing identifiers
  - candidate questions for subject-reference and identity-history research
may_not_use_for:
  - canonical PolicyMatter owner
  - final identifier, namespace, schema, cardinality, or relation model
  - evidence applicability or legal continuity
  - production migration authorization
  - common status or temporal contract
  - production capability claim
  - authority grant
research_only: true
---

# PAO-R0 — Policy Matter Identity and Episode Graph

## Executive Finding

**Result: `research_supported_with_open_owner`.**

The ratified identity/custody decision and repository architecture support the
need for a stable technical custody reference above a single Policy Design
Case. They do not establish a typed `PolicyMatter` capability, canonical
package owner, issuer, namespace, cardinality, split/merge adjudicator, common
support state, temporal schema, migration, or public resolver.

`PolicyMatter` remains a research hypothesis for an opaque accountability and
justification-custody anchor. The safe compatibility guidance is:

1. do not silently reinterpret case, run, job, decision-lineage, policy,
   portfolio, artifact, legal-instrument, or URL identifiers as lifetime
   identity;
2. do not allow similarity, an LLM, projection, or metadata to mint identity
   authority;
3. preserve signed and content-addressed historical bytes;
4. keep future subject associations correctable and replayable;
5. do not infer evidence applicability, legal succession, or competence from
   identity continuity;
6. preserve compatibility with more than one matter per case until cardinality
   is decided.

PDC is a plausible integration neighborhood, runtime quality a possible
validation bridge, artifacts and audit existing custody primitives, and H2 a
future consumer. None is thereby the canonical semantic owner. The owner and
minimum subject-reference ABI require
[S0-GAP-01](../consolidation/stage0/stage0-additional-research-register.md#s0-gap-01).

This revision compresses the original report. The exact supplied source remains
available at [sources/pao-r0-original.md](sources/pao-r0-original.md); this
document supersedes its accepted conclusions but does not erase its research
history.

# 1. Task And Project Fit

## 1.1 Narrow research question

What minimum identity property must remain possible so PolicyOS can keep its
own claims, cases, corrections, supersessions, withdrawals, and historical
replay connected across a policy lifetime without becoming an administrative
master-data system or claiming sovereign identity authority?

The answer is narrower than a production data model:

> PolicyOS needs an above-case custody reference whose historical associations
> can be corrected without rewriting signed history.

The report does not decide what package issues the reference, how many subjects
a case may concern, or whether two real-world initiatives are legally the same.

## 1.2 Boundary verdict

The functional need is **OWN**: without an above-case reference, PolicyOS can
lose custody of its own continuing justification. The evidence used to assert
legal continuity, institutional succession, split, merger, or replacement is
generally **INTEGRATE** because competent external bodies produce those facts.
Similarity, naming, political context, and unadmitted public signals are at
most **OBSERVE**. Administrative case management and institutional master-data
operation remain **OUT_OF_SCOPE**.

Each verdict applies to one declared plane. It does not make PolicyOS the
operator of an external institution.

## 1.3 Relationship to the other Stage-0 anchors

- PAO-R1 supplies the act/evidence/admission/reaction/projection decomposition.
- OPS-R15 may use fixture-local opaque subjects but cannot assume a final
  `PolicyMatter` contract.
- OPS-R2 owns later authority-dependency and evidence-applicability semantics.
- OPS-R4 owns temporal vocabulary and correction algebra.
- INT-R5 and real institutional evidence constrain competence and succession.
- PAO-R36 and INT-R7/INT-R8 own public correction and verification questions.

## 1.4 Standing

This is compatibility guidance for later research. It is not an immediately
binding freeze, a canonical schema, or migration authorization.
`team-architecture` and affected package owners must accept or amend the
subject-reference decision before implementation.

# 2. Current Repository Baseline

## 2.1 Inspection record

| Item | Finding |
|---|---|
| Repository | `DenisKopylov/polisyos` |
| Historical and current `main` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Independent audit | `258aa740efcfb9e6771bfe52d4fdabc6b74f93a7` |
| Consolidation input | `a55d33c7a2ed160fd609b1a9e07d95e0bbb04e19` |
| Source preservation | Exact 121,049-byte supplied artifact, SHA-256 `f7d100…b840` |
| Runtime `PolicyMatter` symbol/capability | Not present |
| Repository evolution between research and audit | None at the pinned baseline |

The repository baseline proves local contracts and absences at the recorded
revision. It cannot prove external institutional competence, legal identity,
or future package ownership.

## 2.2 Identifier census

| Existing identifier | Current bounded meaning | Why it is not silently lifetime matter identity |
|---|---|---|
| `case_id` | Policy Design Case identity in its domain | One matter may have many design, revalidation, or correction cases |
| `run_id` / `job_id` | Execution or control identity | Runs are computational episodes |
| `decision_lineage_key` | Decision-scoped validity lineage | It is not a global, tenant-qualified matter registry |
| `policy_id` | Owner-local policy identifier | Its semantics vary by subsystem |
| `portfolio_id` | Candidate portfolio-analysis identity | `PolicyPortfolio` is not deployed policy stock |
| `ArtifactID` | SHA-256 content identity | Stable bytes are not a mutable real-world intervention |
| legal instrument ID | Identity of a legal work/version | Instruments and matters can be many-to-many |
| release or epoch ID | World/configuration version | A release may affect many subjects |
| URL or public-record ID | Representation/location identity | Locations and records can be corrected or superseded |

An accepted future mapping may bind one of these identifiers to a subject, but
the mapping must be explicit, scoped, replayable, and migration-reviewed.

## 2.3 Reusable repository primitives

| Primitive | Current role | Safe reuse | Limitation |
|---|---|---|---|
| `polisyos.pdc` | Typed graph structure and purpose-scoped authority boundary | Integration neighborhood | Does not own matter semantics or public currentness |
| Runtime quality | Validation/admission patterns | Possible bridge after owner acceptance | No matter producer or generic identity adapter |
| Core artifacts | Content-addressed immutable artifacts | Preserve historical bytes and references | Content identity is not subject identity |
| Core audit | Package assembly and offline verification | Package canonical events produced elsewhere | Does not own event semantics or independent audit opinions |
| Decision validity | Decision-scoped dependency/lifecycle events | Candidate downstream reaction patterns | No complete matter-wide, tenant-qualified chain |
| Scientist lifecycle/reissue | Append-oriented correction and partial reissue | Preserve unaffected scope and historical linkage | Public cross-surface fan-out remains incomplete |
| Data Forge legal → Lex | Offline legal production → runtime selection/evaluation | Legal evidence/version references | Neither establishes policy-matter continuity by itself |
| Atlas | Renderer of governed projections | Display upstream identity/currentness | Must not produce or resolve authority |

## 2.4 Capability reality

No complete `PolicyMatter` capability exists. There is no accepted typed
contract, producer, persisted matter registry, orchestration bridge, consumer
closure, semantic verifier, or governed surface. Existing components are
evidence for reuse, not proof of the missing chain.

The following repository defects remain separate engineering work:

- decision-validity local storage keys are not tenant-qualified;
- checkpoint/control-job forms do not close the full tenant/cell/authority
  custody binding;
- unknown jurisdiction currently falls back to Ukraine;
- a public-export redaction assertion has a reproducible failing test;
- some Atlas readiness projections compute authority-looking state locally.

These defects constrain future work but do not decide the identity model.

# 3. External Research Baseline

## 3.1 What external standards support

External standards support separations useful to this inquiry:

- [W3C PROV-O](https://www.w3.org/TR/prov-o/) distinguishes entities,
  activities, agents, attribution, and derivation;
- [Akoma Ntoso](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/)
  distinguishes legal works, expressions, and manifestations;
- the [European Legislation Identifier](https://op.europa.eu/en/web/eu-vocabularies/eli)
  supplies legislation identifiers and metadata;
- [Records in Contexts](https://ica-egad.github.io/RiC-O/) and
  [PREMIS](https://www.loc.gov/standards/premis/v3/) separate records,
  contextual relations, preservation events, agents, and rights;
- [DataCite relations](https://support.datacite.org/docs/connecting-to-works),
  [ARK](https://arks.org/about/ark-overview/), and the
  [DOI Handbook](https://www.doi.org/doi-handbook/html/) illustrate persistent
  identifier governance and typed relations;
- [Memento](https://www.rfc-editor.org/rfc/rfc7089.html) distinguishes current
  and historical web representations.

These sources do not select PolicyOS's owner, matter granularity, legal
continuity rule, namespace, or migration.

## 3.2 Research conclusions versus design hypotheses

| Standing | Conclusion |
|---|---|
| Repository/decision-supported | Above-case custody identity is functionally needed |
| Repository/decision-supported | Existing identifiers must not be silently repurposed |
| Repository/decision-supported | Correction must preserve prior signed/content-addressed bytes |
| Repository/decision-supported | Identity continuity does not grant authority or evidence applicability |
| Research hypothesis | `PolicyMatter` is a useful name for an opaque accountability reference |
| Open design | Owner, issuer, namespace, wire format, cardinality, relation vocabulary |
| Open institutional question | Who is competent to establish legal continuation, split, merger, or succession |
| Open implementation question | Storage, resolver, migration, public correction, and impact fan-out |

# 4. Result

## 4.1 Accepted identity hypothesis

A candidate `PolicyMatter` is an opaque, non-semantic reference used to attach
PolicyOS custody history concerning a continuing public-authority intervention
commitment. Its identifier should not encode mutable names, agencies,
objectives, populations, mechanisms, territories, dates, legal citations, or
URLs.

This is a research hypothesis, not a contract. “Opaque” does not settle whether
the identifier is globally unique, federated, tenant-local, externally issued,
or internally issued.

## 4.2 Minimum compatibility guidance

| Property to preserve | Required research posture | Not decided here |
|---|---|---|
| Above-case attachability | Future artifacts can refer to an opaque subject | Field name, type, package |
| No silent reinterpretation | Existing IDs retain their historical meaning | Later governed mappings |
| Explicit scope | Authority use remains tenant/jurisdiction/purpose bound | Namespace/federation design |
| Correctable association | Subject links can be superseded without byte rewrite | Sidecar versus canonical event shape |
| Historical replay | A cutoff view excludes later associations/corrections | Exact clocks and storage |
| Open cardinality | One-to-many and many-to-many cases remain representable | Final cardinality |
| No automatic inheritance | Identity continuity grants no evidence applicability | Transportability certificates |
| Projection discipline | Current views derive from canonical upstream facts | Public resolver and cache protocol |

## 4.3 Identity, evidence, authority, and lifecycle stay separate

The following questions must not be collapsed into one state:

1. **Identity relation:** are two subjects or episodes asserted to be related?
2. **Resolution posture:** is that assertion unresolved, disputed, corrected, or
   accepted by a competent process?
3. **Evidence support:** what evidence supports the assertion for a purpose?
4. **Claim authority:** may a PolicyOS claim rely on it now?
5. **Record lifecycle:** which representation is current, stale, corrected,
   superseded, withdrawn, or historical?

PAO-R0 introduces no common `support_status` or parallel authority lattice.
Canonical domain owners must supply their own state and references.

## 4.4 Relations remain research questions

Rename, continuation, successor, split, merge, derivation, expansion,
contraction, suspension, and reinstatement are useful candidate relation
families. They are not accepted enums or automatic decisions.

For any authority-bearing relation, later work must answer:

- which source and target are related;
- which competent actor may assert the relation;
- for which jurisdiction, purpose, scope, and effective interval;
- whether the assertion concerns technical custody, legal continuity,
  institutional responsibility, or public representation;
- what contradictory evidence exists;
- how correction and historical replay behave;
- which evidence items require a separate applicability review.

Similarity may rank candidates. It cannot establish the relation.

## 4.5 Temporal invariant without a clock schema

PAO-R0 requires historical non-rewrite and the ability to distinguish these
roles when their collapse would change meaning:

| Role | Question |
|---|---|
| Source occurrence/effect | When did the external fact occur or take effect? |
| PolicyOS custody/admission | When did PolicyOS receive and accept evidence for a declared use? |
| Transaction/history | When was a representation recorded in the repository history? |
| Correction/replay | Which later fact supersedes which earlier assertion, and what was visible at cutoff? |

OPS-R4 owns canonical names, optionality, ordering, intervals, late-event
categories, and family placement. PAO-R0 does not mandate nine common
timestamps.

## 4.6 Correction invariant

Existing signed and CAS bytes must not be rewritten. A corrected association
or interpretation appends a new custody fact linked to the old one. A separate
sidecar is one candidate technique, not proof of a complete semantic,
authority-impact, cache, or public-correction chain.

## 4.7 Fail-closed posture

When identity evidence is absent, contradictory, wrongly scoped, or produced
without demonstrated competence:

- keep cases and artifacts separately addressable;
- do not pool evidence, incidents, evaluations, or performance history;
- do not issue a matter-level authority claim;
- preserve the candidate relation as non-authoritative research if useful;
- acquire evidence or route to an accepted human/competent process;
- retain prior current and historical views until an append-only correction is
  admitted.

# 5. Counterexamples And Failure Modes

| Scenario | Unsafe conclusion | Required safe result |
|---|---|---|
| Same public name, different mandate and population | Merge | Keep separate absent competent continuity evidence |
| New name and agency, formal continuation | New matter solely from description change | Preserve candidate continuity and recheck authority/evidence scope |
| Pilot scaled nationally | All pilot evidence transports | Identity may continue; every applicability claim is re-evaluated |
| Repeal and similar reenactment | Automatic sameness | Successor/new/unresolved pending competent evidence |
| Matter split | Copy all evidence and incidents to each child as authority | Preserve parent history; review each child scope |
| Matter merge | Delete parent identities | Preserve parents and create a separately justified result |
| Identical external IDs in two tenants | Cross-tenant equality | Keep scoped references separate absent admitted federation evidence |
| Valid signature, wrong subject association | Signature proves semantic correctness | Integrity remains valid; authority/public currentness is blocked or corrected |
| Late correction | Rewrite historical artifacts | Append correction; historical cutoff still reproduces prior view |
| Malicious split to evade incident history | Accept new identity from metadata | Block, retain predecessor links, require independent review |
| Similarity score crosses a threshold | Upgrade candidate to authority | No authority change |
| One case concerns two subjects | Force one relation and lose scope | Preserve scoped multi-subject compatibility |

Core falsifiers are a silent false merge, continuity loss, historical rewrite,
cross-tenant collision, parent-provenance loss, evidence-scope leakage, or
projection-created identity authority.

# 6. Benchmark Or Fixture Proposal

The original synthetic corpus remains useful only as a proposed fixture
catalogue. No executable PAO-R0 benchmark is claimed.

## 6.1 Required fixture profiles

| Profile | Minimum adversarial cases | Observable property |
|---|---|---|
| Non-merge | Same name/text/URL, different authority or population | No authoritative union |
| Continuity | Rename, transfer, instrument change, scale | No history loss solely from descriptive change |
| Split/merge | Parent and child/result histories | Parent provenance preserved |
| Scope transport | Changed population/mechanism/jurisdiction | No automatic evidence inheritance |
| Tenant isolation | Colliding external IDs | No unqualified cross-tenant association |
| Correction | Wrong historical association | Append-only current correction and cutoff replay |
| Integrity versus semantics | Correct signature, wrong subject | Integrity pass cannot grant semantic authority |
| Cardinality | One case with scoped links to multiple subjects | No forced single-subject collapse |
| Adversarial authority | LLM/similarity/metadata assertion | Candidate-only output |
| Public currentness | Old URL/record after correction | Old record remains resolvable but not falsely current |

Expected outcomes must later be independently authored and sealed under
S0-GAP-02 if these fixtures enter the custody capstone.

## 6.2 Metrics

Critical metrics require closed, independently labelled populations:

- false merge;
- forced resolution of an unresolved case;
- historical rewrite;
- wrong-subject publication;
- cross-tenant collision;
- unauthorized identity upgrade;
- parent-provenance loss;
- evidence-scope leakage.

No Stage-0 numerical threshold is set. A future evaluator must publish the
denominator, ambiguity policy, oracle version, and raw disputed labels.

# 7. Artifact Contract Sketch

No production artifact contract is accepted. The safe research deliverable is
a **subject-reference compatibility questionnaire**:

| Question group | Required answer before a contract freeze |
|---|---|
| Semantic owner | Which owner issues and governs the reference, and why does this avoid P27 duplication? |
| Scope | How are tenant, jurisdiction, purpose, and security boundaries closed? |
| Cardinality | Can one case concern several subjects and one subject contain several cases? |
| Creation/non-reassignment | What prevents reuse while avoiding mutable semantics in the ID? |
| Association | How are case/artifact/record links represented and corrected? |
| Competence | Which external evidence may establish legal or institutional continuity? |
| Authority | How is identity kept distinct from evidence applicability and claim authority? |
| Time/replay | How are source/effect, custody/history, and correction roles preserved? |
| Migration | Can legacy bytes remain unchanged and legacy IDs keep their original meaning? |
| Projection | Can current and historical public views coexist without Atlas minting state? |
| Verification | Which negative and cross-tenant tests prove the properties? |

Candidate artifacts such as a subject reference, relation assertion, or
resolution receipt remain alternatives for S0-GAP-01. Their field lists in the
original report are not Stage-0 contracts.

# 8. Later Integration Handoff

| Destination | PAO-R0 handoff |
|---|---|
| S0-GAP-01 | Decide semantic owner and minimum implementation-neutral ABI |
| OPS-R1/OPS-R3 | Preserve subject-bound suspension and migration without assuming final identity shape |
| OPS-R2 | Model authority/applicability dependencies separately from identity |
| OPS-R4 | Define temporal and correction algebra |
| INT-R5 | Verify competence/delegation for external continuity evidence |
| PAO-R36/INT-R7/INT-R8 | Define public correction, verification, and projection parity |
| OPS-R15/S0-GAP-02 | Use fixture-local subjects until owner decision; seal expected identity outcomes |
| Future H2 | Consume the accepted subject contract; do not become its semantic owner by orchestration |

# 9. Promotion And Kill Rules

## 9.1 Research-only

Current standing. It remains research-only while the owner, ABI, cardinality,
relations, temporal model, migration, and public correction chain are
unresolved.

## 9.2 Prototype allowed

A synthetic prototype may use opaque fixture-local subjects if:

- outputs are explicitly non-authoritative;
- unresolved and disputed relations remain representable;
- no existing ID is reinterpreted;
- original signed/CAS bytes remain unchanged;
- identity does not transport evidence authority;
- cross-tenant and multi-subject negative cases are present.

## 9.3 Governed work

Governed implementation requires an accepted S0-GAP-01 owner/ABI decision,
package-owner review, tenant/jurisdiction closure, authority composition,
OPS-R4 time semantics, correction/public fan-out design, semantic tests, and a
migration rehearsal over representative historical artifacts.

## 9.4 Blocked

Block any proposal that:

1. treats an existing local identifier as lifetime identity without an
   accepted mapping;
2. allows similarity, metadata, an LLM, or a UI to mint identity authority;
3. cannot represent unresolved, contested, split, merge, or multi-subject
   cases;
4. rewrites a signed or content-addressed historical artifact;
5. grants evidence applicability or legal continuity from identity sameness;
6. drops tenant/jurisdiction scope;
7. erases parent history;
8. creates a parallel owner, support lattice, universal envelope, or clock
   schema;
9. presents a sidecar as a complete correction capability without the
   consumer and public chain.

# 10. Open Questions For Consolidation

1. Which semantic owner can govern the minimum subject reference without
   duplicating PDC, core contracts, runtime quality, artifacts, or audit?
2. What is the minimum ABI that preserves attachability but leaves cardinality
   and relation adjudication open?
3. Is the namespace global, federated, issuer-qualified, tenant-local, or a
   composition of those concepts?
4. Which body is competent to assert technical continuity, legal succession,
   split, merger, or replacement for each purpose?
5. Can one PDC contain claim-scoped links to several subjects?
6. How does OPS-R2 express evidence applicability after a split, expansion, or
   successor event?
7. How does OPS-R4 represent retroactive correction without later knowledge
   entering a historical cutoff?
8. Which correction and verification facts may appear on public surfaces?
9. How are old public references kept resolvable without appearing current?
10. What migration evidence proves no byte rewrite, scope leak, or identity
    collision?

Recommended next action: accept or amend the Stage-0 consensus kernel, then run
S0-GAP-01 before freezing a mandatory subject reference or beginning H2
architecture.

## Pattern pass

Relevant repository patterns are:

- **P04 — Status enum proliferation:** no common identity/support/authority
  lattice is introduced;
- **P05 — Authority dilution:** identity and projection cannot create
  authority;
- **P07 — Schema versioning without rule evolution:** historical replay keeps
  original rule and association views;
- **P08 — Time semantics fragmentation:** temporal roles remain distinct while
  OPS-R4 owns the algebra;
- **P10 — Structural-only validation:** schema presence or signature integrity
  cannot prove identity adequacy;
- **P14 — Raw evidence count inflation:** split/merge never duplicates evidence
  authority;
- **P27 — Parallel implementation/canonical-owner bypass:** the package owner
  remains open;
- **P29 — Authorial proof/self-attested artifact:** proposed fixtures are not
  called an executable benchmark;
- **P32 — Trust-by-form:** similarity, labels, IDs, and signatures do not grant
  semantic authority;
- **P33 — Witness-as-spec:** fixtures test general properties under renamed,
  reordered, cross-tenant, and adjacent variants.
