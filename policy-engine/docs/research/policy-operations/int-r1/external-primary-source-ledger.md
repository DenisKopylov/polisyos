---
title: INT-R1 — External Primary-Source Transfer Ledger
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r1-independent-audit@887bce985e6797c1a94dba24f33c6424ab09c0a5
authoritative_for:
  - audited research-level source baseline for relative completeness, open-world closure, assurance, bounded diligence, audit evidence, test adequacy, and anytime-valid inference
  - explicit transfer and non-transfer limits used by the amended INT-R1 result
  - stable bibliography and source-selection rationale for consolidation
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - authority grant
  - capability claim
  - legal compliance conclusion
  - legal advice
  - benchmark passage
  - certification to any cited standard
  - proof that a cited institutional doctrine governs PolicyOS
  - detailed substantive attribution to Normative Systems beyond the support stated here
research_only: true
---

# INT-R1 — External Primary-Source Transfer Ledger

## 1. Method and audit disposition

For each external source this ledger records four distinct propositions:

1. what the source itself supports;
2. the bounded move that can transfer to INT-R1;
3. the proposition that does **not** transfer; and
4. the resulting constraint on PolicyOS wording.

The independent audit verified the existence, attribution, and transfer limits of the named
sources. It found one material citation problem: the open catalog record for Alchourrón and
Bulygin's *Normative Systems* establishes bibliographic existence, not the report's original
detailed claims about its internal formal apparatus. That section is narrowed below. No detailed
book proposition is now load-bearing without a page-exact primary source.

Canonical references use stable DOI strings or official report/specification identifiers where
available. A landing page is navigation; the DOI/report/standard identifier is the cited identity.
No source is treated as granting PolicyOS legal authority, as proving the external obligation
world complete, or as certifying any current implementation.

## 2. Normative systems — bibliographic orientation only

### 2.1 Alchourrón and Bulygin

**Work identified.** Carlos E. Alchourrón and Eugenio Bulygin, *Normative Systems*, Library of
Exact Philosophy 5, Springer-Verlag, 1971, ISBN `0-387-81019-6`. The UC Berkeley Law Library
catalog and Google Books record establish the authors, title, publisher, date, and edition-level
bibliographic existence.

**Audited support boundary.** The openly cited catalog pages do not expose primary page text
sufficient to verify the original report's detailed attribution concerning universes of cases,
solutions, relevance, closure rules, and normative gaps. Those detailed propositions are not used
as evidence in the amended theorem. A later consolidation pass may add edition/page anchors if it
has lawful access to the primary text; absent that, the attribution remains orientation.

**Narrow transfer retained.** The work belongs to the legal-theory tradition in which normative
systems, gaps, and closure are analyzed relative to a specified formal problem. That orientation
is consistent with—but does not prove—the independently derived INT-R1 requirement that any
formal completeness claim name the universe and closure rule to which it is relative.

**Does not transfer.** The bibliographic existence of the work does not prove that PolicyOS has
selected every actually applicable enactment, decision, norm, exception, factual trigger, or
institutional source. It does not authorize a rule that “not found” means permitted or not
applicable.

**INT-R1 consequence.** The amended result stands on its own definitions, repository facts, and
indistinguishability argument. *Normative Systems* is not a substitute for a per-scope closure
premise.

## 3. Relative completeness in formal methods

### 3.1 Cook's relative completeness theorem

**Primary identity.** Stephen A. Cook, “Soundness and Completeness of an Axiom System for Program
Verification,” *SIAM Journal on Computing* 7(1), 1978, 70–90, DOI
`10.1137/0207005`; corrigendum, *SIAM Journal on Computing* 10(3), 1981, 612, DOI
`10.1137/0210045`.

**Supported proposition.** The publisher describes the proof system as sound and, in a qualified
sense, complete relative to interpretive semantics. The qualification identifies the semantic
strength assumed by the proof.

**Transfer to INT-R1.** The formal shape is legitimate:

```text
if a fixed declared semantics contains the relevant source-to-obligation truth,
and traversal/compiler/validators satisfy their declared semantic properties,
then every obligation derivable under that semantics is included and checked.
```

This is the shape of the amended **Conditional Relative-Inclusion Theorem**.

**Does not transfer.** Cook's theorem does not establish that a PolicyOS obligation language,
compiler, enum, or selected source basis captures every external legal, normative, measurement,
or implementation obligation. Compiler semantic completeness and validator soundness remain
assumptions until separately supported for the declared domain.

**INT-R1 consequence.** “Relative to declared semantics” is a necessary limitation, not a
solution to semantic adequacy. Independent review and mutation testing provide evidence about the
assumptions; they do not make them true by theorem.

## 4. Open-world and closed-world reasoning

### 4.1 W3C RDF Semantics

**Primary standard.** Patrick Hayes, ed., *RDF Semantics*, W3C Recommendation, 10 February 2004,
official identifier `W3C-rdf-mt-20040210` / Recommendation URL `https://www.w3.org/TR/rdf-mt/`.

**Supported proposition.** RDF's assertional semantics is monotonic; absence of a statement does
not by itself establish its negation. The specification also distinguishes ordinary assertions
from an explicit assertion that a corpus is complete, with provenance carried into conclusions.

**Transfer.** A closure premise must be explicit, scoped, attributable, and provenance-bearing.
Silence or an empty search result cannot become `not_applicable` by default.

**Non-transfer.** Making closure explicit does not establish that the assertion is true or that
the declaring owner is competent for the exact PolicyOS scope.

### 4.2 W3C SHACL

**Primary standard.** Holger Knublauch and Dimitris Kontokostas, eds., *Shapes Constraint
Language (SHACL)*, W3C Recommendation, 20 July 2017, official Recommendation URL
`https://www.w3.org/TR/shacl/`; the closed-shape component is §4.8.1.

**Supported proposition.** Validation is performed against a supplied data graph and shapes
graph. `sh:closed` restricts properties relative to the declared shape; it does not say the
shapes graph contains every constraint that the world may impose.

**Transfer.** A conformance result must bind both evaluated source/data and rule/shape versions.
A green result means no declared violation under those inputs.

**Non-transfer.** Conformance does not prove semantic adequacy or world completeness. This is the
same boundary as exact totality over a declared PolicyOS denominator.

### 4.3 Circumscription

**Primary source.** John McCarthy, “Circumscription—A Form of Non-Monotonic Reasoning,” Stanford
Formal Reasoning Group author-hosted text.

**Supported proposition.** Circumscription formalizes a deliberate minimization/default move in
which known instances are treated as the only instances satisfying a predicate.

**Transfer.** Closed-world treatment is an assumption or rule, not a fact discovered from
absence. It must be named, scoped, defeasible, and attributed.

**Non-transfer.** Circumscription does not tell PolicyOS when a minimization is institutionally or
legally warranted, and it does not prove the minimized universe matches the world.

### 4.4 Combined constraint

These sources support the rule that absence is not falsity and closure must be explicit. They do
not establish a closure premise for any actual PolicyOS scope. The amended protocol therefore
requires one of `closed_by_competent_basis`, `open_under_unseen_extension`, or
`closure_not_established` for every protected use.

## 5. Safety and risk-analysis discipline

### 5.1 STPA

**Primary identity.** Nancy G. Leveson and John P. Thomas, *STPA Handbook*, MIT Partnership for
Systems Approaches to Safety and Security, report identifier `MIT-STAMP-001`.

**Supported proposition.** STPA structures analysis around losses, control structures, unsafe
control actions, causal scenarios, and derived constraints, including organizational and social
components.

**Transfer.** A source/obligation search can be systematic, perspective-complete relative to a
method, independently reviewable, and capable of generating challenger and metamorphic cases.

**Non-transfer.** Completing STPA is not a theorem that every hazard or obligation has been found.
It supports a disciplined adequacy argument only.

### 5.2 IEC 31010:2019

**Primary identity.** IEC 31010:2019, *Risk management — Risk assessment techniques*, second
edition, official IEC publication `59809` / ISO catalogue `72140`.

**Supported proposition.** The standard guides selection, application, verification, and
validation of risk-assessment techniques under uncertainty. It catalogs multiple techniques
rather than making one universal.

**Transfer.** Method choice, assumptions, validation, source coverage, and limitations should be
explicit and proportionate to the problem. Different obligation families may need different
methods.

**Non-transfer.** Method completion does not prove universe exhaustiveness.

### 5.3 HSE ALARP/SFAIRP and relevant good practice

**Primary source family.** UK Health and Safety Executive official guidance on pipeline standards,
design codes, and emergency isolation.

**Supported proposition.** In the contexts it governs, relevant good practice is a minimum;
alternative practice requires gap analysis, and complex/high-risk/out-of-scope situations may
require more.

**Transfer.** A bounded diligence protocol may relate methods, stakes, source gaps, review effort,
and reasons for stopping. A governed stopping rule is evidence about process and judgment.

**Non-transfer.** ALARP/SFAIRP does not govern PolicyOS merely by analogy, does not yield a
probability that no obligation exists, and cannot erase non-derogable duties through cost-benefit
reasoning. Applicable legal standards remain for competent owners.

**INT-R1 consequence.** “Looked enough under a governed rule” is an institutional judgment, not
a world-completeness theorem. It cannot currently produce `bounded_complete` without the rest of
the admitted capability chain.

## 6. Assurance cases and defeaters

### 6.1 SACM and GSN

**Primary identities.** Object Management Group, *Structured Assurance Case Metamodel (SACM)*
2.3, official specification `SACM/2.3`; Assurance Case Working Group, *Goal Structuring Notation
Community Standard*, Version 3, 4 May 2021.

**Supported proposition.** These standards provide structures/notation for claims, context,
argument, evidence, assumptions, justifications, and undeveloped elements.

**Transfer.** INT-R1 coverage should be represented as an assurance claim with visible basis,
assumptions, evidence, defeaters, limitations, owners, review, and lifecycle standing. Existing
PolicyOS assurance-case structures are adjacent reusable machinery.

**Non-transfer.** A well-formed assurance case may be false or incomplete. Notation conformance is
not obligation completeness.

### 6.2 Eliminative induction and defeaters

**Primary identity.** John B. Goodenough, Charles Weinstock, and Ari Z. Klein, *Toward a Theory of
Assurance Case Confidence*, `CMU/SEI-2012-TR-002`, DOI `10.1184/R1/6585362.v1`.

**Supported proposition.** The report develops defeasible reasoning and eliminative induction over
identified reasons for doubt.

**Transfer.** A challenger process should retain and resolve named material defeaters rather than
hide them in a scalar. New evidence can reopen current reliance.

**Non-transfer.** Eliminating every identified defeater does not prove that no unidentified
defeater exists. The public remainder remains explicit.

### 6.3 Quantified confidence limits

**Primary identity.** Patrick J. Graydon and C. Michael Holloway, *An Investigation of Proposed
Techniques for Quantifying Confidence in Assurance Arguments*, `NASA/TM-2016-219195`, NTRS record
`20160006526`.

**Supported proposition.** The report found insufficient validation and implausible behavior in
some proposed quantitative assurance-confidence methods.

**Transfer.** Do not invent a scalar probability for the unknown obligation remainder without a
validated model and data.

**Non-transfer.** This does not invalidate the existing conditional δ arithmetic inside its
specified statistical model.

## 7. Professional audit evidence

### 7.1 PCAOB AS 1105

**Primary identity.** Public Company Accounting Oversight Board, AS 1105, *Audit Evidence*.

**Supported proposition.** The standard distinguishes sufficiency/quantity from
appropriateness/quality; stronger independent evidence and reperformance can outweigh inquiry;
contradictions/reliability doubts require response; selected-item testing does not automatically
support projection to a population.

**Transfer.** Source quantity and quality must be separate. Producer inquiry or self-attestation
is insufficient. Reperformance and independent evidence are stronger, and contradictions must
remain visible.

**Non-transfer.** Audit sufficiency is not a mathematical completeness proof, and this standard
does not automatically apply as PolicyOS law.

### 7.2 PCAOB AS 1215

**Primary identity.** PCAOB AS 1215, *Audit Documentation*.

**Supported proposition.** The standard requires retained documentation of procedures, evidence,
conclusions, performers/reviewers, dates, and contradictions. Later additions are attributable
and reasoned; completed documentation is not silently rewritten.

**Transfer.** A missed obligation after publication triggers append-only challenge, additional
work, suspension, and reissue. The original coverage record remains inspectable.

**Non-transfer.** PCAOB roles and retention periods do not become PolicyOS duties by analogy.

### 7.3 GAO Yellow Book

**Primary identity.** U.S. Government Accountability Office, *Government Auditing Standards: 2024
Revision*, official report `GAO-24-106786`.

**Supported proposition.** The standards emphasize competence, integrity, objectivity,
independence, evidence, engagement quality, monitoring, quality management, and reasonable rather
than absolute assurance.

**Transfer.** Validator governance needs named owners, independence/conflict evidence, review,
monitoring, change control, and post-incident learning.

**Non-transfer.** Reasonable assurance is not a probability of unknown-obligation absence and is
not a substitute for the conditional δ theorem.

## 8. Test adequacy

### 8.1 Mutation testing

**Primary identity.** Richard A. DeMillo, Richard J. Lipton, and Frederick G. Sayward, “Hints on
Test Data Selection: Help for the Practicing Programmer,” *Computer* 11(4), 1978, 34–41, DOI
`10.1109/C-M.1978.218136`.

**Supported proposition.** Mutation testing evaluates whether tests distinguish an implementation
from variants bearing faults in a declared mutation model.

**Transfer.** INT-R1 must include omission, mis-scope, stale-rule, unknown-to-satisfied,
always-pass, common-mode, and projection faults, and require authority behavior—not a marker—to
turn red.

**Non-transfer.** Killing all declared mutants does not prove that the fault model or world
obligation set is exhaustive. OM-01 itself remains blocked on GY-GAP1 until an instance layer
exists.

### 8.2 MC/DC

**Primary identity.** Kelly J. Hayhurst, Dan S. Veerhusen, John J. Chilenski, and Leanna K.
Rierson, *A Practical Tutorial on Modified Condition/Decision Coverage*, official report
`NASA/TM-2001-210876`, NTRS record `20010057789`.

**Supported proposition.** The tutorial presents a method for evaluating whether individual
conditions independently affect a decision and discusses tool/structural-coverage limitations.

**Transfer.** A decisive obligation or coverage predicate must independently affect the protected
decision. Branch execution or marker presence alone is insufficient.

**Non-transfer.** Complete structural coverage of an incomplete model remains incomplete.

## 9. Anytime-valid inference

**Primary identity.** Aaditya Ramdas, Peter Grünwald, Vladimir Vovk, and Glenn Shafer,
“Game-Theoretic Statistics and Safe Anytime-Valid Inference,” *Statistical Science* 38(4), 2023,
576–601, DOI `10.1214/23-STS894`; author manuscript `arXiv:2210.01948`.

**Supported proposition.** E-processes and related anytime-valid methods preserve their stated
error control at stopping times under the specified model/process.

**Transfer.** Once obligation, validator, allocation, filtration, and evidence process are
correctly specified, repeated monitoring and optional stopping need not invalidate the bound.

**Non-transfer.** An e-process cannot discover an obligation absent from the model, establish
source competence, prove compiler semantic completeness, or make a validator semantically sound.

**INT-R1 consequence.** A later witnessed omission may leave historical arithmetic correct for the
old model while making current authority use red.

## 10. Cross-field transfer table

| Field | Bounded transferable claim | Overclaim explicitly rejected |
| --- | --- | --- |
| Normative systems | bibliographic orientation to relative formal closure/gaps | the cited catalog proves detailed doctrine or PolicyOS world closure |
| Formal methods | inclusion/completeness relative to assumed semantics | the semantics capture every external obligation |
| Open-world reasoning | closure is explicit, scoped, attributable, and defeasible | silence or failed search means false/not applicable |
| Safety/risk analysis | methods and stopping can be systematic and reviewable | every hazard/obligation was found |
| Assurance cases | assumptions, evidence, defeaters, and limitations are visible | a well-formed argument is true or exhaustive |
| Professional audit | sufficient appropriate evidence and independence support a scoped opinion | audit evidence is mathematical/world completeness |
| Mutation/MC/DC | adequacy relative to declared faults/structure | the specification/fault model is complete |
| Anytime-valid inference | optional-stopping safety within a specified model | the model discovered all obligations or proves validator semantics |

## 11. External-baseline result

No audited source supplies a theorem of global obligation completeness for an open institutional
world. The convergent safe pattern is:

1. declare scope, basis, semantics, versions, and fault model;
2. prove mechanical traversal/inclusion relative to them under explicit semantic assumptions;
3. keep source adequacy, compiler completeness, and validator soundness visible as premises;
4. require actual independent evidence before protected reliance;
5. retain exclusions, conflicts, defeaters, and unknown remainder;
6. expire, challenge, suspend, and reissue append-only; and
7. forbid relative passage from being projected as universal.

That pattern supports `accepted_narrow_scope`. It does not establish a current
`bounded_complete` capability, benchmark passage, legal compliance, or absence of world
obligations outside the declared basis.
