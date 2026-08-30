---
title: INT-R2 — External Primary Source Ledger
status: research_only
research_task: INT-R2
checked_at: 2026-08-29
repository_base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
amended_by: int-r2/amendment-ledger.md
authoritative_for:
  - primary-source coordinates supporting the INT-R2 stage-1 external baseline
  - source-class and non-effect boundaries used by the INT-R2 synthesis
may_not_use_for:
  - capability claim
  - canonical owner appointment
  - institutional signer appointment
  - universal scientific threshold
  - jurisdiction-general legal conclusion
  - production admission
  - runtime contract
---

# INT-R2 — External Primary Source Ledger

## 1. Purpose, method and holder boundary

This ledger makes the external basis of the INT-R2 synthesis independently inspectable from the
research branch. It supplements the five commissioned surveys; it does not replace their detailed
argument or silently convert their cross-disciplinary synthesis into a standard.

The present researcher rechecked the named owner pages or canonical papers on 2026-08-29. The
`recomputed` holder label below applies only to the proposition expressly supported by the named
source. Every cross-domain mapping into `GapAcquisitionCase`, `AuthorityCeiling`, re-entry or
`deeper_terminal` remains **INT-R2 researcher synthesis** until later audit, consolidation and
ratification.

Source classes are deliberately distinct:

- **normative primary** — statute, regulation, regulator standard or professional standard within its
  own jurisdiction or institutional regime;
- **official guidance** — an owner or regulator explains its process, but the guidance may be
  non-binding or narrower than the underlying law;
- **formal primary** — a theorem, definition or complete method within an explicit model class;
- **method primary** — a peer-reviewed framework or measurement proposal;
- **official framework** — an official operational model whose completion is not itself proof of the
  underlying capability.

No row below establishes that PolicyOS has a producer, institutional actor, runtime bridge or
admissible artifact. The aggregate capability standing remains `absent/unallocated`.

## 2. Target definition, causal relation and estimand

| ID | Primary source | Class | Proposition retained | Explicit non-effect / limit | Holder label |
| --- | --- | --- | --- | --- | --- |
| `INT-R2-S01` | [JCGM 200:2012 — International Vocabulary of Metrology (VIM)](https://www.bipm.org/en/doi/10.59161/jcgm200-2012) | normative metrology vocabulary | Measurement has an explicitly specified target concept; the commissioned survey uses the VIM measurand discipline as a target-before-data anchor. | A metrology vocabulary does not choose the policy question, identify a causal effect or confer authority. | `recomputed` for document identity and vocabulary role. |
| `INT-R2-S02` | [FDA E9(R1) — Estimands and Sensitivity Analysis in Clinical Trials](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/e9r1-statistical-principles-clinical-trials-addendum-estimands-and-sensitivity-analysis-clinical) | normative regulatory guidance | The treatment effect of interest must be made clear and linked coherently to objective, design, conduct, analysis and interpretation. This supports separating `estimand_binding` from estimator and estimate. | FDA/ICH guidance is scoped to clinical-trial regulation; it is not a universal policy estimand law and does not itself prove identification. | `recomputed`. |
| `INT-R2-S03` | [Shpitser and Pearl, Complete Identification Methods for the Causal Hierarchy](https://jmlr.org/papers/v9/shpitser08a.html) | formal primary | Within the covered graphical-model classes, causal queries can be characterised as computable or not computable from lower-level information; failure of a complete procedure is stronger than failure of an arbitrary estimator. | The result is relative to the causal model, query, assumptions and available information. It is not a model-free declaration that a relation is false or unknowable forever. | `recomputed`. |
| `INT-R2-S04` | [IARC, *Preamble to the IARC Monographs on the Identification of Carcinogenic Hazards to Humans*, amended January 2019, 44-page owner PDF](https://monographs.iarc.who.int/wp-content/uploads/2019/07/Preamble-2019.pdf), pinned to Part A §§4–7 and Part B §§2–6 | normative institutional procedure | The pinned Preamble binds Working Group constitution and conflicts, working procedures, systematic evidence identification and appraisal, separate evidence streams, overall evaluation and rationale. This is a strong pattern for a versioned relation dossier. | IARC classifications are institution- and subject-specific hazard conclusions, not a universal causal threshold, quantitative risk estimate or policy recommendation. | `recomputed` for exact PDF identity, edition, page denominator and cited parts; category semantics remain source-scoped. |

### 2.1 Source-derived result

These sources support two non-substitutable objects:

```text
grounding relation = warrant about causal structure under a declared regime
estimand binding    = warrant that the target quantity is defined
```

The further INT-R2 rule — that each object becomes a separate discriminated acquisition case with a
consumer-enforced ceiling — is synthesis, not text taken from any one source.

## 3. Legal mandate, normative authorization and owner writability

| ID | Primary source | Class | Proposition retained | Explicit non-effect / limit | Holder label |
| --- | --- | --- | --- | --- | --- |
| `INT-R2-S05` | [5 U.S.C. §706 — scope of judicial review](https://www.govinfo.gov/link/uscode/5/706) | normative primary law | U.S. federal review distinguishes action within statutory authority from action in excess of jurisdiction, authority or limitations. This supports exact-action and exact-scope mandate checks. | One U.S. provision is not a universal delegation model and does not resolve another jurisdiction’s competence rules. | `recomputed` for the statutory proposition used. |
| `INT-R2-S06` | [HHS/FDA — Minutes of Institutional Review Board Meetings](https://www.hhs.gov/ohrp/minutes-institutional-review-board-irb-meetings-guidance-institutions-and-irbs.html-0) | official guidance citing regulation | IRBs have bounded actions — approve, require modifications or disapprove — and records must preserve attendance, votes, reasons and controverted issues; quorum must persist for voting. This supports a reasoned, version-bound normative determination rather than `approved=true`. | The document is U.S. human-subject-research guidance and explicitly distinguishes non-binding guidance from cited regulatory requirements. It does not define all normative authorization regimes. | `recomputed`. |
| `INT-R2-S07` | [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) | normative technical standard | Verification can establish conformance, proof/status and issuer statement integrity; it does not by itself evaluate the truth of the encoded claims. | A valid credential does not prove issuer competence, substantive mandate, independent work or downstream suitability. | `recomputed`. |
| `INT-R2-S08` | [ICO — Data sharing agreements](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/data-sharing-a-code-of-practice/data-sharing-agreements/) | official regulatory guidance | A data-sharing agreement records parties, purposes, roles and lifecycle controls and can help demonstrate compliance. The ICO expressly says it does not provide immunity from breaching the law. | The agreement is proof of an arrangement, not self-creating legal power or universal write authority. UK data-protection scope only. | `recomputed`. |
| `INT-R2-S09` | [GOV.UK — Data ownership model](https://www.gov.uk/government/publications/data-ownership-in-government/data-ownership-model) | official framework | Government data owners and data stewards have distinct accountability and operational-governance responsibilities. This supports separating policy/meaning authority from delegated stewardship and technical custody. | Role names in guidance do not automatically establish legal title or permission to perform a particular mutation in every organisation. | `recomputed`. |
| `INT-R2-S10` | [HM Land Registry Practice Guide 39 — rectification and indemnity](https://www.gov.uk/government/publications/rectification-and-indemnity-pg39/practice-guide-39-rectification-and-indemnity) | official legal-process guidance | Anyone may apply for alteration, while alteration/rectification authority and evidentiary sufficiency remain with the statutory court/registrar process. This cleanly separates submission, adjudication and execution capability. | England-and-Wales land registration only. It does not supply a generic register-write ontology. | `recomputed`. |
| `INT-R2-S11` | [W3C PROV-O](https://www.w3.org/TR/prov-o/) | normative technical standard | Provenance can identify entities, activities and agents and bind who did what to which object. | Provenance of an activity is not proof that the agent was authorised to perform it. The authority inference is an INT-R2 boundary rule, not a PROV-O claim. | `recomputed` for the provenance vocabulary; authority non-effect is synthesis. |

### 3.1 Source-derived result

The sources support keeping three different acquisition objects:

```text
legal mandate           = lawful competence for the exact act
normative authorization = regime-specific sanction/consent/determination
owner writability       = substantive right to change canonical state,
                          plus a separately valid technical execution grant
```

A signature, credential, ACL, provenance trail, consultation or agreement can be necessary evidence
without being sufficient for any of these objects.

## 4. Competent human decision and independent audit

| ID | Primary source | Class | Proposition retained | Explicit non-effect / limit | Holder label |
| --- | --- | --- | --- | --- | --- |
| `INT-R2-S12` | [PCAOB AS 1215 — Audit Documentation](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1215) | normative professional standard | Documentation must show procedures, evidence, conclusions, performer, reviewer and dates, and enable an experienced auditor with no prior connection to understand the work. Contradictory significant information must be retained; oral explanation alone is insufficient. | PCAOB scope is specified audit/attestation work. INT-R2 generalises reconstructability as a benchmark pattern, not as a universal legal duty for all decisions. | `recomputed`. |
| `INT-R2-S13` | [IESBA, *2025 Handbook of the International Code of Ethics for Professional Accountants (including International Independence Standards)*, Volume 1](https://www.ethicsboard.org/publications/2025-handbook-international-code-ethics-professional-accountants), published 7 October 2025, ISBN 978-1-60815-606-1; pinned to Part 1 §120 and Part 4A §400 | normative professional standard | The pinned Code supplies a conceptual framework to identify, evaluate and address threats to fundamental principles and, where applicable, independence. This supports relationship-specific independence assessment rather than a permanent person flag. | Formal safeguards and a completed threat form do not prove substantive independence or the truth of an assurance conclusion. Later material in the 2025 volumes with a future effective date is not imported as current authority. | `recomputed` for edition, volume, publication date, ISBN and cited sections. |
| `INT-R2-S14` | [IAASB, *ISAE 3000 (Revised), Assurance Engagements Other than Audits or Reviews of Historical Financial Information*](https://www.iaasb.org/publications/international-standard-assurance-engagements-isae-3000-revised-assurance-engagements-other-audits-or), issued 9 December 2013, ISBN 978-1-60815-167-7, effective for reports dated on or after 15 December 2015; pinned to ¶12, ¶¶24–26 and ¶¶64–77 | normative professional standard | The pinned standard distinguishes reasonable and limited assurance and binds an engagement to subject matter, suitable criteria, sufficient appropriate evidence, conclusion and report scope. | `assured=true` is not an adequate cross-domain state. The standard does not turn agreed-upon procedures or any external review into assurance over the whole subject. | `recomputed` for standard identity, issue date, ISBN, effective date and cited paragraph bands. |
| `INT-R2-S15` | [GMC Good medical practice — competence](https://www.gmc-uk.org/professional-standards/the-professional-standards/good-medical-practice/domain-1-knowledge--skills-and-development) | normative professional standard | A practitioner must be competent in the work and recognise and work within the limits of competence, with supervision appropriate to role, knowledge, skills, training and task. | Registration is an entry condition, not proof that this exact case fell inside the person’s competence or that required work was performed. | `recomputed`. |
| `INT-R2-S16` | [GMC — What is revalidation?](https://www.gmc-uk.org/registration-and-licensing/managing-your-registration/revalidation/what-is-revalidation) | official regulator process | Annual appraisal and a usual five-year recommendation/decision cycle maintain professional standing through evidence and regulator action rather than self-assertion. | Revalidation of the person does not prove the correctness or current validity of a particular decision. | `recomputed`. |
| `INT-R2-S17` | [Engineering Council — UK-SPEC](https://www.engc.org.uk/ukspec.aspx) | normative professional standard | Professional registration requires demonstrated competence and commitment across multiple areas rather than a credential name alone. | A broad professional title does not supply universal case-specific scope, mandate or direction-and-control evidence. | `recomputed`. |

### 4.1 Source-derived result

A competent decision and an independent audit share reconstructability but do not collapse:

- the decision requires standing, role, task competence, actual work, exact subject/version and an
  attributable conclusion;
- audit additionally requires a defined subject, criteria, procedures, assurance level and a
  relationship/threat assessment independent of the auditee’s preferred outcome.

`provider_unavailable` and `adverse_conclusion` remain distinct because only the latter contains a
valid provider’s substantive finding about the subject.

## 5. Implementation-capacity evidence

| ID | Primary source | Class | Proposition retained | Explicit non-effect / limit | Holder label |
| --- | --- | --- | --- | --- | --- |
| `INT-R2-S18` | [HM Treasury — Treasury Approvals Process for projects and programmes](https://www.gov.uk/government/publications/treasury-approvals-process-for-programmes-and-projects/treasury-approvals-process-for-projects-and-programmes) | normative operational guidance | NISTA reviews advise readiness for the next approval stage; a Red Delivery Confidence Assessment means not ready to proceed and triggers a Response-to-Red process rather than automatic termination. | DCA is an ordinal, intervention-sensitive snapshot, not a calibrated probability that the whole policy will be delivered. UK central-government project scope only. | `recomputed`. |
| `INT-R2-S19` | [GAO-20-48G — Technology Readiness Assessment Guide](https://www.gao.gov/products/gao-20-48g) | official framework | Readiness should be assessed against demonstrated maturity and integration evidence through a documented, objective process; immature technologies create material acquisition risk. | Technology readiness is one component of delivery capacity, not proof of workforce, suppliers, legal authority, adoption, fidelity or full-system operation. | `recomputed`. |
| `INT-R2-S20` | [Proctor et al. — Outcomes for implementation research](https://doi.org/10.1007/s10488-010-0319-7) | method primary | Implementation outcomes such as acceptability, adoption, appropriateness, feasibility, fidelity, cost, penetration and sustainability are distinct measurement targets. | The framework does not provide a universal pre-commitment threshold or calibrated probability of delivery. | `recomputed` for the published framework identity and outcome distinction. |
| `INT-R2-S21` | [Damschroder et al. — updated CFIR](https://doi.org/10.1186/s13012-022-01245-0) | method primary | Implementation determinants span the innovation, outer setting, inner setting, individuals and implementation process; resources and capability are not one scalar. | A completed CFIR assessment is a map of determinants, not direct proof that critical prerequisites exist or that rollout will succeed. | `recomputed` for the framework identity and scope. |
| `INT-R2-S22` | [RE-AIM framework](https://re-aim.org/learn/what-is-re-aim/) | method/official framework | Reach, Effectiveness, Adoption, Implementation and Maintenance are separate dimensions, preventing delivery among recipients from being confused with population reach or organisational adoption. | RE-AIM is not a universal authority certificate or probability model for a future delivery system. | `recomputed` for the framework identity and dimension set. |

### 5.1 Source-derived result

Implementation-capacity evidence is evidence about a concrete delivery system at a declared scale,
environment, load and time. The strongest common pattern is stage-bounded authority:

```text
evidence demonstrated in scope S
=> at most the next commitment supported inside S
!= automatic broad rollout authority
```

The INT-R2 horizon-terminal test — no credible maturation path, narrower valuable scope or alternative
channel inside the decision horizon — is a conservative synthesis. No source above publishes it as a
universal theorem or calibrated classifier.

## 6. Cross-source boundary propositions

The following are the stable propositions retained across source classes. The first column names what
the sources directly establish; the second names the INT-R2 synthesis built over them.

| Source-supported boundary | INT-R2 synthesis | What remains prohibited |
| --- | --- | --- |
| Target definition, causal identification and estimation are separate operations. | `grounding_relation` and `estimand_binding` are separate acquisition cases; same-stream rows do not close either object by count alone. | `rows_added => target_or_relation_closed`. |
| Statutory competence, ethics/consent determination and register mutation follow different owner regimes. | `legal_mandate`, `normative_authorization` and `owner_writability` stay separate, possibly ordered cases. | One `authorized=true` flag or one signature/credential closing all three. |
| Cryptographic verification and provenance bind statements and activities, not the truth or authority behind them. | Admission requires resolve + content-bind + current issuer standing + non-producer verification + consumer ceiling enforcement. | Trust by field presence, shape, signature, self-verifier or provenance alone. |
| Professional standing, work documentation and assurance independence are distinct. | `competent_human_decision` and `independent_audit` share a reconstructable envelope but have different producer and ceiling predicates. | `qualified=true`, `external=true` or countersignature as automatic acquisition. |
| Readiness regimes permit, condition or block the next stage and can trigger corrective action. | `implementation_capacity_evidence` authorises only the next demonstrated commitment; Red/not-ready is provisional unless the stronger horizon-terminal proof exists. | Composite maturity score or pilot automatically authorising full-scale rollout. |
| Updated or corrected evidence opens another owner review. | Re-entry invalidates currentness, rebinds scope/time/rules and reruns the demanding gate; it never directly converts a refusal into approval. | `closure_event_received => approved`. |

## 7. Primary-source falsifiers retained for implementation

Any later implementation is unsafe if one of these near-variants passes:

1. a million extra observational rows close a relation or estimand while the defining/identifying
   object is unchanged;
2. a valid credential from an issuer with no competent authority closes a mandate;
3. an API token closes substantive owner writability;
4. IRB/consent evidence for one protocol or purpose is reused for a materially changed version;
5. a professional licence plus signature closes a decision with no reconstructable work;
6. `external=true` closes independence despite self-review, fee, appointment or network threats;
7. a Red/not-ready capacity assessment is rendered as terminal, or a Green/pilot is rendered as full
   rollout authority;
8. a provenance record is consumed as proof that the recorded actor was entitled to act;
9. receipt of a corrected artifact skips the demanding owner’s re-entry computation;
10. a framework/checklist is consumed as if it were direct evidence of the property it lists.

These falsifiers feed the 63-case public regression denominator and the 16 sealed near-variants in
`operational-closure-and-fixtures.md`.

## 8. Unresolved external questions

The primary sources do **not** settle:

- a universal calibrated threshold for admitting an arbitrary causal relation;
- a model-free classifier for structural versus data-shaped gaps;
- a universal cross-jurisdiction legal/normative/write authority vocabulary;
- a canonical issuer or grant threshold for informal social licence;
- a calibrated probability scale for whole-policy delivery capacity;
- a universal rule proving substantive independence from formal safeguards;
- the completeness of the eight-case union beyond the eight commissioned objects;
- the canonical PolicyOS owner, institutional producers or runtime integration.

These remain `deferred_open_problem`, `not_established` or `absent/unallocated` as classified in the
main report and finding register. External-source maturity does not change repository capability
standing.

## 9. Standing

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

This ledger strengthens source traceability only. It appoints no owner, moves no capability, creates
no production-eligible predicate and opens no gate.
