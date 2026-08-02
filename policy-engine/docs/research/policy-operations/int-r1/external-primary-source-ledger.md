---
title: INT-R1 — External Primary-Source Transfer Ledger
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-obligation-coverage
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - research-level primary-source baseline for relative completeness, normative gaps, open-world closure, assurance cases, bounded safety diligence, audit evidence, test adequacy, and anytime-valid inference
  - explicit transfer and non-transfer limits for INT-R1
  - bibliography and source-selection rationale for the primary INT-R1 report
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
research_only: true
---

# INT-R1 — External Primary-Source Transfer Ledger

## 1. Method

This ledger asks a narrower question than “what fields have discussed completeness?” For each
source it records:

1. the proposition the source actually supports;
2. the bounded move that can transfer to PolicyOS;
3. the proposition that **does not** transfer; and
4. how the source constrains the INT-R1 result.

Canonical papers, standards, regulator guidance, and author-maintained reports are preferred.
Secondary catalog or table-of-contents pages are used only where a book is not openly available,
and are labelled as bibliographic orientation rather than substantive authority. No source is
treated as granting PolicyOS legal authority or certifying its architecture.

## 2. Normative systems: completeness is relative to a chosen universe

### 2.1 Alchourrón and Bulygin

**Primary work.** Carlos E. Alchourrón and Eugenio Bulygin, *Normative Systems*, Library of
Exact Philosophy 5, Springer-Verlag, 1971, xviii + 208 pages, ISBN 0-387-81019-6.
Bibliographic record: [UC Berkeley Law Library](https://lawcat.berkeley.edu/record/40108) and
[Google Books](https://books.google.com/books/about/Normative_systems.html?id=f-180AEACAAJ).

**Relevant structure.** The work constructs a normative system relative to a factual range,
normative range, universe of properties, universe of cases, universe of actions/solutions, and
normative basis. It then treats relevance and axiological gaps, open and closed systems, rules
of closure, judicial decisions in the presence of normative gaps, and the scope and limits of
completeness as a rational ideal. The chapter-level orientation is independently visible in the
publisher-derived table of contents
([Kriso bibliographic page](https://www.kriso.ee/normative-systems-db-9783211810194.html));
that page is secondary orientation, not the substantive source.

**Transfer to INT-R1.** “Complete” is not meaningful without specifying at least a universe of
cases and a universe of solutions. A closure rule can make a formal system complete relative
to those choices, but the choice of relevant properties/cases and the legitimacy of the closure
rule remain separate questions. This directly supports an envelope that declares scope,
closure basis, exclusions, and remainder.

**Does not transfer.** A formal reconstruction of a legal system does not prove that PolicyOS
has identified every actually applicable enactment, decision, institutional norm, local rule,
contract, exception, factual trigger, or future reinterpretation. Nor does it authorize a
“whatever is not found is permitted” closure rule. INT-R1 therefore rejects any move from
formal closure to universal worldly completeness.

**INT-R1 consequence.** The strongest honest phrase is “complete relative to the declared
universe/closure basis,” not “complete for the world.” A closure basis must itself be
challengeable, versioned, time-bounded, and attributable to a competent owner.

## 3. Relative completeness in formal methods

### 3.1 Cook's relative completeness theorem

**Primary source.** Stephen A. Cook, “Soundness and Completeness of an Axiom System for Program
Verification,” *SIAM Journal on Computing* 7(1), 1978, 70–90,
[doi:10.1137/0207005](https://doi.org/10.1137/0207005), with corrigendum in *SIAM Journal on
Computing* 10(3), 1981, 612,
[doi:10.1137/0210045](https://doi.org/10.1137/0210045).

The paper proves a Hoare-style system sound and, in a qualified sense, complete **relative to
an interpretive semantics**. The qualification is not an embarrassment; it identifies the
oracle or semantic strength on which the proof depends.

**Transfer to INT-R1.** The shape of a theorem may be:

> if the declared obligation language and its source-to-obligation oracle contain the relevant
> semantic truth, and the proof system/validators are sound relative to that language, then all
> obligations derivable in that language are covered.

This is a genuine reduction because it separates mechanical proof obligations from an
external adequacy assumption.

**Does not transfer.** Cook's theorem gives no method for proving that the interpretive
semantics captures every legal, normative, measurement, or implementation obligation in an
open institutional world. Renaming a hand-authored enum “the obligation language” does not
establish its adequacy.

**INT-R1 consequence.** The δ theorem can remain mathematically meaningful, but its public
scope must be explicit: relative to the declared obligation set/language, closure basis,
versions, and maintained assumptions.

## 4. Open-world and closed-world reasoning

### 4.1 W3C RDF Semantics

**Primary standard.** Patrick Hayes, ed., *RDF Semantics*, W3C Recommendation, 10 February
2004, [https://www.w3.org/TR/rdf-mt/](https://www.w3.org/TR/rdf-mt/), especially §0.1,
§1.3, and Appendix B.

RDF's assertional semantics is monotonic and cannot itself express a closed-world assumption.
The specification also makes a crucial distinction: an explicit assertion that a corpus is
complete, with provenance carried into the conclusion, can make the closure assumption
visible; the unsafe move is implicit negation-by-failure.

**Transfer to INT-R1.** Closure must be an explicit, provenance-bearing assertion rather than
an inference from silence. A reader must be able to identify which corpus/snapshot was claimed
complete, by whom, for what scope, and at what cutoff.

**Does not transfer.** Making a closure assertion explicit does not make it true. Provenance
supports accountability and reproducibility, not completeness of the external world.

### 4.2 W3C SHACL

**Primary standard.** Holger Knublauch and Dimitris Kontokostas, eds., *Shapes Constraint
Language (SHACL)*, W3C Recommendation, 20 July 2017,
[https://www.w3.org/TR/shacl/](https://www.w3.org/TR/shacl/), especially §§3–3.6 and the
`sh:ClosedConstraintComponent` definition.

SHACL validation consumes a specified data graph and shapes graph and emits a conformance
report. `sh:closed` closes the declared properties of a shape; it does not claim that the
shapes graph contains every constraint the world could impose.

**Transfer to INT-R1.** Validation results must bind both the evaluated data/source snapshot
and the rule/shape set. A green result means no violation under those inputs and semantics.

**Does not transfer.** Conformance to a shapes graph is not evidence that the shapes graph is
semantically adequate or complete. This is the exact analogue of a promotion receipt that is
total over `PromotionObligationClass` but omits a decisive world obligation.

### 4.3 Circumscription

**Primary source.** John McCarthy, “Circumscription—A Form of Non-Monotonic Reasoning,” 1986
web edition, [Stanford Formal Reasoning Group](https://www-formal.stanford.edu/jmc/circumscription/circumscription.html).
The abstract describes circumscription as formalizing conjectural reasoning that the objects
known to have a property are the only objects that do.

**Transfer to INT-R1.** A closed-world move is a deliberate minimization/default assumption,
not a discovered fact. It should be named, scoped, and defeasible.

**Does not transfer.** Circumscription cannot justify the empirical or institutional truth of
the minimized universe. It explains what an explicit closure rule does, not when PolicyOS is
entitled to use it.

**INT-R1 consequence across all three sources.** Absence from a search result cannot become
“not applicable.” It remains unknown unless an independently justified closure assertion
covers that scope.

## 5. Safety engineering: disciplined adequacy without exhaustiveness

### 5.1 STPA

**Primary practitioner handbook.** Nancy G. Leveson and John P. Thomas, *STPA Handbook*,
MIT Partnership for Systems Approaches to Safety and Security, MIT-STAMP-001, available from
[MIT PSASS Books and Handbooks](https://psas.scripts.mit.edu/home/books-and-handbooks/).

The handbook structures hazard analysis by defining the purpose and losses, modelling control
structures, identifying unsafe control actions, constructing causal scenarios, and deriving
constraints and requirements. It extends beyond component failures to software, humans,
organizations, and social systems.

**Transfer to INT-R1.** A disciplined, reviewable search process can be tested for whether it
covered declared perspectives, control relationships, loss scenarios, and change over time.
The process can produce useful challenger prompts and metamorphic variants.

**Does not transfer.** STPA does not prove that every possible hazard or obligation has been
identified. Its systematic process supports an adequacy argument, not an exhaustive-world
theorem.

### 5.2 IEC 31010:2019

**Primary standard.** IEC 31010:2019, *Risk management — Risk assessment techniques*, second
edition, June 2019, [IEC publication 59809](https://webstore.iec.ch/en/publication/59809) and
[ISO catalogue 72140](https://www.iso.org/standard/72140.html).

The standard guides selection and application of risk-assessment techniques under uncertainty
and explicitly adds detail on planning, implementing, verifying, and validating the use of
those techniques. It catalogs techniques such as FMEA and HAZOP rather than claiming one
universal exhaustive method.

**Transfer to INT-R1.** The search strategy, method selection, assumptions, validation, and
limitations should be declared and reviewable. Different obligation families may require
different source and analysis methods.

**Does not transfer.** A completed risk-assessment technique is not proof that the risk or
obligation universe is exhaustive. Method completion and universe completeness are different
properties.

### 5.3 ALARP/SFAIRP and relevant good practice

**Primary regulator guidance.** UK Health and Safety Executive:

- [Use of pipeline standards and good practice guidance](https://www.hse.gov.uk/pipelines/resources/pipelinestandards.htm);
- [Pipeline design codes and standards for UK CO2 storage and sequestration projects](https://www.hse.gov.uk/pipelines/resources/designcodes.htm);
- [Emergency Isolation](https://www.hse.gov.uk/comah/sragtech/techmeasisolatio.htm).

The guidance treats relevant good practice as a minimum in the contexts it governs, requires a
gap analysis for alternative standards, and warns that good practice alone can be insufficient
in high-risk, complex, or out-of-scope situations. Additional reasonably practicable measures
must be considered where risk remains.

**Transfer to INT-R1.** Bounded diligence may be expressed as a reviewable process tied to
risk, stakes, applicable good practice, gaps, proportional search effort, and documented reasons
for stopping. Higher stakes justify broader sources, stronger independence, and shorter TTLs.

**Does not transfer.** ALARP/SFAIRP is a legal/regulatory doctrine in particular jurisdictions
and domains. It does not govern PolicyOS by analogy, does not produce a probability that no
unknown obligation exists, and does not authorize cost-benefit closure of rights or legal duties.

**INT-R1 consequence.** “We looked enough under a governed stopping rule” is an empirical and
institutional judgment. It may support `bounded_complete` relative to a basis; it cannot support
world completeness or legal compliance.

## 6. Assurance cases: explicit claims, assumptions, evidence, and defeaters

### 6.1 SACM and GSN

**Primary standards.** Object Management Group, *Structured Assurance Case Metamodel (SACM)*
2.3, formally adopted October 2023,
[https://www.omg.org/spec/SACM/2.3/About-SACM](https://www.omg.org/spec/SACM/2.3/About-SACM).
Assurance Case Working Group, *Goal Structuring Notation Community Standard*, Version 3,
4 May 2021, [citation record](https://scsc.uk/resources/citation_r1386.html) and
[standard page](https://scsc.uk/gsn-standard).

SACM supplies a metamodel for structured assurance cases. GSN supplies an authoritative
notation definition and best-practice guidance for argument owners, readers, authors, and
approvers.

**Transfer to INT-R1.** Coverage should be an assurance claim with explicit context, strategy,
evidence, assumptions, justifications, undeveloped elements, defeaters, owners, and review
status. PolicyOS's existing `assurance_case.py` can project these structures without claiming
that the notation discovers obligations.

**Does not transfer.** A well-formed assurance case can still be unsound, incomplete, biased,
or supported by weak evidence. Notation conformance is not obligation completeness.

### 6.2 Eliminative induction and defeaters

**Primary report.** John B. Goodenough, Charles Weinstock, and Ari Z. Klein, *Toward a Theory
of Assurance Case Confidence*, CMU/SEI-2012-TR-002, 2012,
[doi:10.1184/R1/6585362.v1](https://doi.org/10.1184/R1/6585362.v1).

The report frames confidence through defeasible reasoning and eliminative induction: identify
reasons for doubt and eliminate them where evidence permits.

**Transfer to INT-R1.** A challenger process should preserve unresolved defeaters rather than
hide them in a scalar confidence score. A green coverage state requires closure of named
material defeaters within the declared scope, and a new defeater can reopen the claim.

**Does not transfer.** Eliminating identified defeaters does not prove that all possible
defeaters have been identified. The unknown remainder remains load-bearing.

### 6.3 Limits of quantified assurance confidence

**Primary government report.** Patrick J. Graydon and C. Michael Holloway, *An Investigation
of Proposed Techniques for Quantifying Confidence in Assurance Arguments*, NASA/TM-2016-219195,
2016, [NASA NTRS 20160006526](https://ntrs.nasa.gov/citations/20160006526).

The authors find little evidence that proposed quantitative confidence techniques deliver
trustworthy results in practice, demonstrate implausible outputs in some cases, and conclude
that further validation is needed before using such techniques as a basis for fielding a
critical system.

**Transfer to INT-R1.** Keep the world-coverage judgment categorical and evidence-linked; do
not manufacture a numeric “probability of completeness” without a validated model and data.

**Does not transfer.** The report does not prohibit the existing δ theorem for false promotion
under its maintained assumptions. It prohibits conflating that statistical guarantee with a
validated quantitative measure of obligation-universe adequacy.

## 7. Professional audit evidence: reasonable basis, independence, and post-report work

### 7.1 PCAOB AS 1105

**Primary standard.** Public Company Accounting Oversight Board, AS 1105, *Audit Evidence*,
[https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105),
especially paragraphs .01–.10, .17–.20, and .22–.29.

The standard separates sufficiency (quantity) from appropriateness (relevance and reliability),
warns that more evidence of the same poor quality cannot compensate for weakness, generally
rates independent knowledgeable sources above internal-only sources, states that inquiry alone
is insufficient, defines reperformance as independent execution, requires response to
contradictions or reliability doubts, and warns that testing selected specific items does not
support projection to the whole population.

**Transfer to INT-R1.** Search breadth and source quality must be separate. Independent
reperformance and source-to-obligation mutation tests are stronger than a producer attestation.
A source sample cannot be represented as full-population coverage.

**Does not transfer.** Audit evidence supports a reasonable basis for an opinion under an audit
objective; it is not a mathematical proof of every obligation and does not establish which
audit law applies to PolicyOS.

### 7.2 PCAOB AS 1215

**Primary standard.** PCAOB AS 1215, *Audit Documentation*,
[https://pcaobus.org/oversight/standards/auditing-standards/details/AS1215](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1215),
especially paragraphs .02–.10 and .14–.19. At the INT-R1 inspection date, the page notes that
specific amendments to paragraphs .09 and .11 become effective on 15 December 2026; this
research does not prematurely treat those future amendments as effective.

The current standard requires documentation of procedures, evidence, conclusions, performers,
reviewers, dates, and contradictory evidence. If later information suggests procedures or
evidence may have been omitted, the auditor must demonstrate sufficiency with persuasive other
evidence or follow omitted-procedure rules. After the completion date, documentation is not
deleted or discarded; additions identify date, preparer, and reason.

**Transfer to INT-R1.** Preserve the original coverage envelope, challenge, contradictory
evidence, and later additions. A missed obligation after publication triggers append-only
assessment and reissue; it must not rewrite the historical search record.

**Does not transfer.** AS 1215's retention periods and regulated audit roles do not become
PolicyOS rules by analogy. Only the append-only accountability pattern transfers.

### 7.3 GAO Yellow Book

**Primary standard.** U.S. Government Accountability Office, *Government Auditing Standards:
2024 Revision*, GAO-24-106786, 2024,
[report page](https://www.gao.gov/products/gao-24-106786) and
[Yellow Book hub](https://www.gao.gov/yellowbook). The revision is effective for covered
periods/performance audits beginning on or after 15 December 2025, and its quality-management
system implementation deadline was 15 December 2025.

The standards emphasize competence, integrity, objectivity, independence, evidence, engagement
quality, monitoring, and a quality-management system that gives reasonable—not absolute—assurance
that work and reports comply with applicable standards and law.

**Transfer to INT-R1.** Validator governance needs named owners, independence/conflict checks,
review, monitoring, change control, and post-incident learning.

**Does not transfer.** “Reasonable assurance” is an institutional standard of professional
work, not a bound on unknown obligations and not a substitute for the δ theorem.

## 8. Test adequacy: relative to a fault model

### 8.1 Mutation testing

**Primary paper.** Richard A. DeMillo, Richard J. Lipton, and Frederick G. Sayward, “Hints on
Test Data Selection: Help for the Practicing Programmer,” *Computer* 11(4), 1978, 34–41,
[doi:10.1109/C-M.1978.218136](https://doi.org/10.1109/C-M.1978.218136).

Mutation testing evaluates whether tests distinguish a program from defined fault-bearing
variants. The method operationalizes adequacy against a fault model and supports the mandated
INT-R1 “remove the decisive obligation” probe.

**Transfer to INT-R1.** Create mutants that omit, misclassify, duplicate, stale, scope-shift,
or falsely satisfy obligations, and validator mutants that always pass, invert, ignore an
unknown, trust an unresolved reference, or share the same faulty parser. Require the governed
claim to turn red.

**Does not transfer.** Killing every declared mutant does not prove that the mutant model spans
every possible omission or world obligation. Mutation score is benchmark adequacy, not open-world
completeness.

### 8.2 MC/DC

**Primary government tutorial.** Kelly J. Hayhurst, Dan S. Veerhusen, John J. Chilenski, and
Leanna K. Rierson, *A Practical Tutorial on Modified Condition/Decision Coverage*,
NASA/TM-2001-210876, 2001,
[NASA NTRS PDF record](https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20010057789.pdf).

The tutorial presents a five-step method for evaluating MC/DC claims and discusses tool
qualification, lifecycle data, and common structural-coverage pitfalls.

**Transfer to INT-R1.** Each decisive obligation or coverage predicate should be shown to
independently affect the promotion result. A test that merely executes a branch or checks a
marker is inadequate.

**Does not transfer.** Structural coverage says nothing about whether the right obligations or
conditions were specified. One can obtain complete structural coverage of an incomplete model.

**INT-R1 consequence across both methods.** The benchmark can falsify weak implementations and
support a governed adequacy claim. It cannot certify that no unknown obligation exists.

## 9. Anytime-valid inference: what the δ machinery does and does not cover

**Primary paper.** Aaditya Ramdas, Peter Grünwald, Vladimir Vovk, and Glenn Shafer,
“Game-Theoretic Statistics and Safe Anytime-Valid Inference,” *Statistical Science* 38(4),
2023, 576–601, [doi:10.1214/23-STS894](https://doi.org/10.1214/23-STS894); open version
[arXiv:2210.01948](https://arxiv.org/abs/2210.01948).

E-processes and confidence sequences remain valid at all stopping times under their statistical
hypothesis/model, accommodating continuous monitoring and optional stopping or continuation.

**Transfer to INT-R1.** Once an obligation, validator, risk allocation, and eligible evidence
process are correctly specified, an e-process can preserve type-I error control under repeated
looks and adaptive stopping. It is well suited to the ledger's statistical subproblem.

**Does not transfer.** An e-process cannot detect that an obligation was never represented, that
a source was absent, that a validator encodes the wrong semantic property, or that the closure
basis was institutionally incompetent. Optional-stopping validity does not repair model or
obligation omission.

**INT-R1 consequence.** A witnessed coverage or validator fault is a maintained-assumption
breach. The numerical process may remain arithmetically correct for its old model, but its result
is red and unusable for the protected authority action.

## 10. Cross-field synthesis

| Field | Honest bounded claim | Unsafe overclaim rejected by INT-R1 |
| --- | --- | --- |
| Normative systems | Complete relative to a declared universe of cases/solutions and closure rule | The legal/normative world is necessarily complete or has no gaps |
| Formal methods | Complete relative to an oracle/semantics/language | The oracle/language captures every external obligation |
| Open-world reasoning | Closure is explicit, scoped, provenance-bearing, defeasible | Silence or search failure means false/not applicable |
| Safety analysis | A governed method systematically searched declared perspectives and hazards | Every hazard/obligation was found |
| ALARP/SFAIRP | Diligence and stopping can be justified relative to risk and applicable doctrine | A cost judgment proves no obligation remains or governs PolicyOS by analogy |
| Assurance cases | Claims, evidence, assumptions, contexts, and defeaters are explicit and reviewable | A well-formed argument is true or exhaustive |
| Professional audit | Sufficient appropriate evidence provides a reasonable basis for a scoped opinion | Audit sufficiency is mathematical or world completeness |
| Mutation/MC/DC | Tests are adequate relative to declared mutants/structure | The specification or fault model is complete |
| Anytime-valid inference | Error control survives optional stopping under the maintained model | The model discovered every obligation or its validators are semantically sound |

### Result of the external baseline

No inspected field supplies a defensible theorem of global obligation completeness for an open
institutional world. The common successful pattern is instead:

1. declare the universe, source basis, scope, semantics, and fault model;
2. prove or test mechanical coverage relative to them;
3. govern source selection and validator change independently;
4. retain assumptions, exclusions, defeaters, and unknown remainder;
5. set review/expiry triggers proportional to change and stakes;
6. permit challenge and append-only correction/reissue; and
7. refuse to project a relative result as universal.

That pattern supports `accepted_narrow_scope`: a bounded relative-coverage protocol is defensible;
a claim that the open-world obligation universe is complete is refuted.
