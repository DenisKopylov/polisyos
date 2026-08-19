---
title: INT-R1 — Anchor and Citation Verification
status: delivered
kind: independent-audit
research_task: INT-R1
result_type: accepted_narrow_scope
audit_verdict: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-independent-audit
audited_branch: research/int-r1-obligation-coverage
audited_commit: 82e136a8d528cb24e661973ac1a8ea4fb6f1c80f
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - exhaustive verification of anchors in the INT-R1 repository census ledger
  - declared adversarial sample of anchors in the INT-R1 main deliverable
  - source-existence attribution and transfer audit of the INT-R1 external-source ledger
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - merger or release approval
research_only: true
---

# INT-R1 — Anchor and Citation Verification

## 1. Pass A method

Repository anchors were checked against the exact commit
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`, not against the audited branch tip. Verification had
three tests:

1. the path exists at the pinned commit;
2. the cited range exists; and
3. the content supports the sentence that cites it, not merely a related topic.

The census ledger contains 31 unique path/range groups after repeated anchors are deduplicated.
All 31 were checked. The main report was sampled separately using this deterministic adversarial
rule:

- every anchor supporting the enum count or Rule-12 verdict;
- every anchor supporting current capability labels;
- every anchor supporting the conditional δ premise;
- every anchor supporting one-lattice, custody-kernel, time, or authority-boundary claims;
- every anchor supporting benchmark-red semantics or independent-oracle dependency; and
- the first load-bearing repository claim in each of the ten required report sections.

This produced 40 anchor occurrences. Thirty-nine support their claims. One is only partial: the
`CONTRIBUTING.md` ranges state general architecture, test, and documentation governance but do
not specifically locate all typed authority contracts or runtime integration owners.

## 2. Exhaustive census-ledger anchor verification

| No. | Census claim and anchor | Path/range | Verification result |
| ---: | --- | --- | --- |
| 1 | Current baseline is 121 commits ahead of historical baseline. | Git compare `4813b49f6...d152565dc` | **supported** — ahead 121, behind 0, common merge base is the historical commit. |
| 2 | Enum has 15 members and `VALUE` is present. | `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-235` | **supported exactly**. The docstring also says “Universal N9 obligation-class denominator.” |
| 3 | Kernel binds authority/candidate bands and fail-closed protected use. | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:43-116`, `:164-212` | **supported** — K05/K06/K12/K16 and application notes carry the claimed limits. |
| 4 | CTM separates source/receipt/verification/admission/publication and leaves reaction to claim owner. | `policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-145`, `:146-220` | **supported**. |
| 5 | Repository instructions require boundary discipline and load-bearing time/status/provenance. | `AGENTS.md:5-37`, `:68-96` | **supported**. |
| 6 | Contributor contract “locates typed authority contracts and runtime integration under existing architecture governance.” | `policy-engine/CONTRIBUTING.md:84-139`, `:177-201` | **partially supported** — ranges require architecture checks, ownership boundaries, tests, and documentation discipline; they do not themselves identify the PDC waist or a specific runtime owner. Narrow the sentence to general contribution governance. |
| 7 | Existing obligation statuses provide fail-closed destinations. | `gy_waist.py:218-255` | **supported** — `satisfied`, `failed`, `unknown`, `scope_insufficient`, `not_applicable_data_only` plus refusal reasons are present. |
| 8 | Conditional δ clause and maintained assumptions are explicit. | `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50` | **supported exactly**. |
| 9 | Pools must partition the enum and weights must sum to one. | `confidence_ledger.py:337-369` | **supported exactly**. |
| 10 | Root/receipt classes carry hashes, policy, budget, clause, and assumptions. | `confidence_ledger.py:500-1010` | **supported**. |
| 11 | Durable output binds the split hash and assumptions. | `confidence_ledger.py:2463-2488` | **supported**. |
| 12 | Registry declares the conditionality, schedules, partition, profiles, and owners. | `policy-engine/architecture/production_quality/confidence_ledger.toml:1-89`, `:91-232` | **supported**. |
| 13 | Five-profile breakdown is one e-process, one unavailable theorem, one deterministic, two ineligible. | `confidence_ledger.toml:53-89` | **supported exactly**. |
| 14 | N9 compiles obligations, binds checks, derives refusal reasons, and decides promotion. | `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:760-1320` | **supported**. |
| 15 | Receipt validation reconstructs the denominator and makes mismatch a refusal. | `promotion_sequence.py:1320-1900` | **supported** — expected tuple is `tuple(PromotionObligationClass)` and mismatch propagates into recomputed result. |
| 16 | `scope_insufficient` cannot mint authoritative production promotion. | `promotion_sequence.py:280-340` | **supported**. |
| 17 | Rule 12 bans capability-gating enumerations while exempting governed vocabularies/statuses. | `policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:200-222` | **supported**. The census's categorical conclusion is evaluated separately in finding G-001. |
| 18 | P29 stops mechanical regress at generic traversal over actual owned source. | `policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75`; `AGENTS.md:39-49` | **supported**. |
| 19 | Formal-invariant machinery carries named properties, owners, evidence, revisit triggers, and negatives. | `policy-engine/src/polisyos/runtime/quality/formal_invariants.py:23-105`, `:145-158` | **supported**. |
| 20 | Assurance case carries claim/evidence/assumption/defeater/blocker/confidence structures and projections. | `policy-engine/src/polisyos/runtime/quality/assurance_case.py:1-60`, `:120-173` | **supported**. |
| 21 | Candidate firewall prevents candidate material from filling protected authority slots. | `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-73` | **supported**. |
| 22 | Evidence spine carries requirement/owner/ref/revision/authority information. | `policy-engine/src/polisyos/runtime/quality/evidence_spine.py:1-125` | **supported**. |
| 23 | Claim registry binds claims to evidence, norms, limitations, deficits, blockers, and uncertainty. | `policy-engine/src/polisyos/runtime/quality/claim_registry.py:1-107` | **supported**. |
| 24 | Grounding bind revalidates live references and blocks local open obligations. | `policy-engine/src/polisyos/runtime/quality/grounding_bind.py:1-121` | **supported**. The census correctly distinguishes this from world discovery. |
| 25 | Acquisition planner routes typed gaps and contains legal-corpus/competence families. | `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:1-190` | **supported**. |
| 26 | Atlas laws preserve one lattice and deny UI-minted authority. | `policy-engine/docs/system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md:130-260` | **supported**. |
| 27 | Atlas plan has INT-R1-dependent DS12/DS17/DS18 consumers. | `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` | **supported**, though the line is oversized prose and invalid as YAML frontmatter. |
| 28 | Backlog names research outputs but no implemented canonical contracts. | `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:260-500` | **supported**. |
| 29 | Identity/custody decision supports OWN/INTEGRATE/OBSERVE/OUT_OF_SCOPE verdict. | `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:52-145` | **supported**. |
| 30 | First governed/public use remains gated by INT-R1/INT-R9 and independent-oracle work. | `policy-operations-and-real-world-runtime-backlog.md:500-760`; Atlas plan `:7` | **supported**. |
| 31 | No current empirical profile population supports a miss-rate estimate. | `confidence_ledger.toml:53-89` plus G5 pinned artifacts | **supported as a negative evidence conclusion** — profile kinds are not observations of missed obligations, and the pinned proving ground has zero governed conversion/useful-design credit. |

### Census integrity result

- Paths/ranges resolved: **31/31**.
- Fully supportive: **30/31**.
- Partially supportive: **1/31**.
- Broken anchors: **0**.
- Core-code anchors contradicted by source: **0**.

## 3. Main-deliverable adversarial sample

| Sample | Audited report claim | Audited anchor | Result |
| ---: | --- | --- | --- |
| 1 | Baseline moved by 121 commits. | main report `:88-104`; Git comparison | **supported**. |
| 2 | Enum is 15, not 14. | `:177-205`; `gy_waist.py:218-235` | **supported**. |
| 3 | Conditionality is explicit. | `:206-249`; `confidence_ledger.py:37-50` | **supported**. |
| 4 | Pool totality is exact. | `:206-249`; `confidence_ledger.py:337-369` | **supported**. |
| 5 | Registry has two Basel schedules. | `:240-266`; TOML `:1-52` | **supported**. |
| 6 | Profile-kind distribution supplies no real miss-rate population. | `:250-266`; TOML `:53-89` | **supported**, with the conclusion correctly limited to unavailable calibration. |
| 7 | N9 makes denominator mismatch affect promotion. | `:267-300`; `promotion_sequence.py:1320-1900` | **supported**. |
| 8 | Rule 12 has both prohibition and exemption. | `:280-310`; organizing rules `:200-222` | **supported**. |
| 9 | P29 applies to actual owned source traversal. | `:311-350`; P29 `:70-75` | **supported**. |
| 10 | P29 does not prove selection of external world sources. | `:330-350`; P29 plus boundary reasoning | **supported as inference**, clearly labeled argument rather than repository fact. |
| 11 | Formal-invariant machinery is adjacent but not INT-R1 implementation. | `:351-408`; `formal_invariants.py:23-105`, `:145-158` | **supported**. |
| 12 | Assurance case structures but does not discover obligations. | `:351-408`; `assurance_case.py:1-60`, `:120-173` | **supported**. |
| 13 | Candidate firewall blocks authority substitution. | `:351-408`; `candidate_firewall.py:1-73` | **supported**. |
| 14 | Claim/evidence owners lack an INT-R1 envelope binding. | `:351-408`; `claim_registry.py:1-107`; `evidence_spine.py:1-125` | **supported by absence and field census**. |
| 15 | Acquisition planner is partial and not a world-discovery producer. | `:351-408`; `acquisition_planner.py:1-190` | **supported**. |
| 16 | Aggregate current INT-R1 capability is contract-only. | `:409-444`; census plus backlog | **supported as composite capability label**, not a code symbol. |
| 17 | No standalone obligation authority service is justified. | `:445-472`; reuse map | **supported as reuse-first recommendation**, not a theorem. |
| 18 | RDF does not infer falsity from absence. | `:473-527`; W3C RDF Semantics | **supported**. |
| 19 | SHACL closed shapes close enumerated properties, not world constraints. | `:473-527`; W3C SHACL §4.8.1 | **supported**. |
| 20 | E-processes do not discover omitted obligations. | `:520-547`; Ramdas et al. plus model-bound inference logic | **supported transfer limit**. |
| 21 | Impossibility theorem is explicitly premise-relative. | `:549-586` | **supported**; formal validity audited separately. |
| 22 | More search is not proof of absence by quantity alone. | `:575-586` | **supported under the report's extension-closure premise**. |
| 23 | Relative theorem denies `C_v(B)=U(W)`. | `:592-647` | **supported exactly**. |
| 24 | `bounded_complete` is relative and not auto-satisfied. | `:648-676` | **supported**. |
| 25 | `known_incomplete` blocks affected protected action. | `:677-699` | **supported as proposed rule**, not implemented behavior. |
| 26 | `open_world_unresolved` maps to unknown/scope-insufficient. | `:680-706` | **supported as proposed one-lattice mapping**. |
| 27 | Public δ phrase remains relative. | `:707-729` | **supported and consistent with Atlas waiting consumer**. |
| 28 | Stopping table separates mechanical, empirical, governance, and impossible claims. | `:700-759` | **supported as reasoned taxonomy**. |
| 29 | Independence requires more than a second function name. | `:730-759` | **supported design principle**; capability not constructed. |
| 30 | Counterexample against class-counting uses two obligations in one class. | `:760-835` | **conceptually supported**, but not directly executable against current one-record-per-class N9 representation; finding H-002. |
| 31 | Frozen benchmark must not derive expectations from primary compiler. | `:842-874` | **supported and consistent with S0-K14/S0-GAP-02**. |
| 32 | S0-GAP-02 remains independent-scorer dependency. | `:850-874`; kernel `:188-212` | **supported**. |
| 33 | OM-01 keeps class totality green while instance deletion turns proof red. | `:875-918` | **under-specified against current representation**; material finding H-002. |
| 34 | VM-01 makes validator-soundness assumption red. | `:900-930` | **specified as expected benchmark behavior**, not executed evidence. |
| 35 | Red disables protected action and current public claim. | `:900-915` | **supported exactly**. |
| 36 | Benchmark is unimplemented and `semantic_test_missing`. | `:960-980` | **supported; no contradictory passage found**. |
| 37 | Envelope contains scope, sources, exclusions, remainder, and TTL. | `:981-1100` | **supported**. |
| 38 | Envelope never sets promotion. | `:1080-1110` | **supported**. |
| 39 | One-lattice map never auto-satisfies `bounded_complete`. | `:1160-1215`; organizing rules `:184-186` | **supported**, subject to keeping `NO_COVERAGE_BLOCKER` a derived predicate. |
| 40 | State machine preserves immutable supersession/reissue. | `:1216-1290`; CTM `:146-220` | **supported as design sketch**, not implemented capability. |

### Main-report sample result

- Sample size: **40 anchor occurrences**.
- Fully supportive: **39**.
- Materially under-specified rather than false: **1** (`OM-01` representation bridge).
- Broken path/range: **0**.
- Unsupported repository capability assertion: **0**.

## 4. Pass B method

Every named source in
`policy-engine/docs/research/policy-operations/int-r1/external-primary-source-ledger.md` was
checked for:

1. bibliographic/source existence;
2. accuracy of the attributed proposition; and
3. validity of the transfer to INT-R1.

The audit distinguishes a source being real from the source proving the proposition attributed
to it. A transfer is accepted only when the report also states what the source does **not**
solve.

## 5. External-source verification ledger

| No. | Source | Existence and attribution | Transfer audit | Verdict |
| ---: | --- | --- | --- | --- |
| 1 | Alchourrón & Bulygin, *Normative Systems* (Springer, 1971) | Berkeley Law catalog confirms authors, title, publisher, year, 208 pages, ISBN 0387810196: <https://lawcat.berkeley.edu/record/40108>. The audited ledger does not provide page-exact primary text for the detailed claims about case universes, solutions, closure rules, and gaps. | The high-level transfer—completeness is relative to a declared universe—is plausible and canonical. The detailed doctrinal attribution is not independently checkable from the cited bibliographic record alone. | **exists; attribution partially verified; transfer plausible but citation must be narrowed/page-anchored**. Finding B-001. |
| 2 | Cook, “Soundness and Completeness of an Axiom System for Program Verification,” SIAM J. Comput. 7(1), 1978, 70-90, DOI 10.1137/0207005 | SIAM publisher page states that the system is sound and “in a certain sense complete, relative to the interpretive semantics”: <https://doi.org/10.1137/0207005>. | Strong transfer for the **shape** of relative completeness. It does not establish adequacy of PolicyOS's declared language or world basis. | **verified; transfer survives with stated limit**. |
| 3 | Cook corrigendum, SIAM J. Comput. 10(3), 1981, p. 612 | SIAM links a correction from the article; DOI metadata is consistent with 10.1137/0210045. | Bibliographic correction has no independent load-bearing transfer beyond accurate citation. | **verified; non-load-bearing**. |
| 4 | W3C *RDF Semantics* | W3C Recommendation explicitly says RDF is monotonic and cannot express closed-world assumptions, and its glossary explains that an explicit complete-corpus/provenance assertion can make closure visible: <https://www.w3.org/TR/rdf-mt/>. | Strong support for “absence is not falsity” and “closure must be explicit.” It does not prove an explicit closure assertion true. | **verified; transfer survives**. |
| 5 | W3C *Shapes Constraint Language (SHACL)* | Official Recommendation §4.8.1 defines `sh:closed` over predicates enumerated by property shapes: <https://www.w3.org/TR/shacl/#ClosedConstraintComponent>. | Strong support for conformance relative to a supplied shapes graph, not completeness of the constraint universe. | **verified; transfer survives**. |
| 6 | McCarthy, “Circumscription—A Form of Non-Monotonic Reasoning” | Stanford-hosted primary text states that circumscription formalizes conjectural reasoning that known objects are the only objects satisfying a predicate: <https://www-formal.stanford.edu/jmc/circumscription/circumscription.html>. | Supports treating closure/defaults as explicit nonmonotonic assumptions. Does not prove that the minimized predicate matches the institutional world. | **verified; transfer survives with limit**. |
| 7 | Leveson & Thomas, *STPA Handbook* | MIT PSASS official books/handbooks page provides the handbook and describes STPA/CAST as detailed current guidance: <https://psas.scripts.mit.edu/home/books-and-handbooks/>. | Supports systematic hazard/constraint search across technical and organizational systems. It is not an exhaustiveness theorem for obligations. | **verified; transfer survives as method discipline only**. |
| 8 | IEC 31010:2019 | Official IEC page describes guidance on selecting/applying risk-assessment techniques and added planning, implementation, verification, and validation detail: <https://webstore.iec.ch/en/publication/59809>. | Supports method selection and validation proportional to the problem. Does not establish that any selected set is exhaustive. | **verified; transfer survives**. |
| 9 | UK HSE good-practice/ALARP guidance | Official HSE pipeline page requires relevant current good practice as a minimum and equivalent safety where alternatives are used: <https://www.hse.gov.uk/pipelines/resources/pipelinestandards.htm>. | Supports bounded, stakes-sensitive diligence and gap analysis. The report correctly denies that this makes ALARP/SFAIRP legally applicable to PolicyOS or permits cost to erase non-derogable duties. | **verified; transfer survives only as institutional analogy**. |
| 10 | OMG SACM 2.3 | Official OMG specification endpoint exists: <https://www.omg.org/spec/SACM/2.3/About-SACM>. SACM is a metamodel for structured assurance-case claims, evidence, argumentation, and artifacts. | Supports typed assurance representation and links. It does not establish truth, completeness, or soundness of supplied evidence. | **verified; transfer survives with limit**. |
| 11 | GSN Community Standard v3 | SCSC official citation gives version 3, 4 May 2021, and describes authoritative notation/guidance: <https://scsc.uk/resources/citation_r1386.html>. | Supports visible claim/context/argument/evidence structure and challenge-oriented extensions. It is not a proof that all defeaters were found. | **verified; transfer survives**. |
| 12 | Goodenough, Weinstock & Klein, CMU/SEI-2012-TR-002 | Official SEI page confirms report number, authors, DOI 10.1184/R1/6585362.v1, and eliminative induction over identified defeaters: <https://www.sei.cmu.edu/library/toward-a-theory-of-assurance-case-confidence/>. | Supports challenger/defeater discipline and the distinction between identified reasons for doubt and unidentified ones. | **verified; transfer survives**. |
| 13 | Graydon & Holloway, NASA/TM-2016-219195 | NASA NTRS record states that proposed quantitative assurance-confidence techniques lacked validation and could produce implausible results: <https://ntrs.nasa.gov/citations/20160006526>. | Strong caution against inventing an uncalibrated scalar probability for unknown obligation remainder. It does not invalidate the ledger's conditional δ process. | **verified; transfer survives**. |
| 14 | PCAOB AS 1105, *Audit Evidence* | Official standard distinguishes sufficiency/quantity from appropriateness/quality and states that more poor-quality evidence cannot compensate; independent evidence is generally more reliable: <https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105>. | Strong analogy for evidence quantity/quality, independence, reperformance, and contradictions. It is not automatically a legal standard for PolicyOS. | **verified; transfer survives with legal-scope disclaimer**. |
| 15 | PCAOB AS 1215, *Audit Documentation* | Official standard requires retained documentation and, after completion, dated/attributed/reasoned additions rather than deletion: <https://pcaobus.org/oversight/standards/auditing-standards/details/AS1215>. | Supports append-only post-publication challenge/correction documentation. Does not define PolicyOS's legal record duties. | **verified; transfer survives**. |
| 16 | GAO, *Government Auditing Standards: 2024 Revision*, GAO-24-106786 | Official GAO page confirms 2024 revision, risk-based quality management, leadership responsibility, monitoring, and reasonable assurance: <https://www.gao.gov/products/gao-24-106786>. | Supports competence, independence, quality management, and reasonable-not-absolute assurance. It does not prove obligation completeness. | **verified; transfer survives**. |
| 17 | DeMillo, Lipton & Sayward, “Hints on Test Data Selection,” *Computer* 11(4), 1978, 34-41, DOI 10.1109/C-M.1978.218136 | DOI and bibliographic metadata are consistent across publisher-linked indexes; the work introduces mutation and the coupling-effect rationale. | Supports mutation adequacy against a chosen fault model. The report correctly denies transfer to completeness of the world obligation set. | **verified metadata; transfer survives with fault-model limit**. |
| 18 | NASA/TM-2001-210876, *A Practical Tutorial on Modified Condition/Decision Coverage* | NASA NTRS record confirms authors, report number, and a five-step MC/DC evaluation approach: <https://ntrs.nasa.gov/citations/20010057789>. | Supports structural coverage as a declared criterion and illustrates tool/claim qualification. It does not establish semantic adequacy of requirements. | **verified; transfer survives**. |
| 19 | Ramdas, Grünwald, Vovk & Shafer, “Game-theoretic statistics and safe anytime-valid inference,” *Statistical Science* 38(4), 2023, DOI 10.1214/23-STS894 | Author manuscript and DOI metadata confirm e-processes remain valid at arbitrary stopping times under the modeled process: <https://arxiv.org/abs/2210.01948>. | Strong transfer to optional-stopping-safe statistical evidence after obligations/nulls/filtration are specified. No transfer to obligation discovery, source competence, or validator semantics. | **verified; transfer survives**. |

The table has 19 rows because Cook's corrigendum is verified separately; the audited ledger's
literature families are all covered.

## 6. Citation-transfer findings

### INT-R1-B-001 — *Normative Systems* claim needs a page-exact primary anchor

- **Severity:** material
- **Disposition:** revise citation, not the overall conclusion.
- **Finding:** the cited Berkeley record proves the book exists. It does not expose the primary
  passages needed to verify the report's detailed attribution concerning universes of cases and
  solutions, closure, relevance, and normative gaps.
- **Required revision:** provide edition/page anchors to the primary book, or narrow the prose to
  bibliographic orientation and rely on the independently established logical argument.

### INT-R1-B-002 — transfer discipline is unusually strong

- **Severity:** commendation
- **Disposition:** preserve.
- **Finding:** for Cook, RDF/SHACL, safety analysis, assurance cases, audit standards, mutation,
  MC/DC, and e-processes, the ledger states the non-transfer explicitly. No source is imported as
  a theorem of world-level obligation completeness.

### INT-R1-B-003 — normalize bibliographic precision

- **Severity:** minor
- **Disposition:** correct during consolidation.
- **Finding:** use stable DOI/official-report identifiers as canonical references, especially for
  the Cook corrigendum, DeMillo et al., NASA MC/DC, and Ramdas et al.; do not make a page-range
  detail load-bearing where the official landing page or author manuscript is the evidence.

## 7. Pass-A findings

### INT-R1-A-001 — core repository evidence base is intact

- **Severity:** commendation
- **Disposition:** verified.
- **Finding:** all 31 unique census anchor groups resolve at the pinned baseline, and all core
  code anchors support their attributed facts.

### INT-R1-A-002 — contributor-contract anchor is over-specific

- **Severity:** minor
- **Disposition:** reword/re-anchor.
- **Finding:** `CONTRIBUTING.md:84-139`, `:177-201` supports general governance, checks, and
  documentation discipline, not the specific claim that it locates the typed authority waist or
  runtime integration owner.

### INT-R1-A-003 — no broken or deceptive core anchor found

- **Severity:** commendation
- **Disposition:** verified.
- **Finding:** no resolvable anchor was found that points to content contradicting the sentence
  citing it. The one partial anchor is adjacent and over-broad, not fabricated.

## 8. Verification conclusion

The report's repository grounding is strong enough for consolidation after the stated
narrowing. External transfers are mostly well-argued and self-limiting. The audit does not clear
the formal theorem or benchmark merely because their citations exist; those are evaluated in
`int-r1-formal-argument-audit.md` and the main audit.