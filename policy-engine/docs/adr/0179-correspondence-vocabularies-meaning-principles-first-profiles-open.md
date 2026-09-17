# ADR-0179: The correspondence vocabularies adopt five meaning principles, and their first profiles stay explicitly open

## Status

Accepted

## Date

2026-09-17

## Decision record

Taken by the principal on 2026-09-17, on the CV-DR series' final decision packages and the architect's reading of them, and recorded in the form required by the identity decision's §9 item 7. It contains a second principal's ruling of the same day — on growth by users — because that ruling explains why the first profiles stay open.

## Context

Backlog Group E commissioned decision research `CV-DR1`–`CV-DR5` on the five questions `CV-Q1`–`CV-Q5` of the correspondence-vocabularies lane. It ran under pipeline §7 (Library-first, n + 1 prompts):

- five researchers;
- a synthesizer;
- five question audits, one supplementary audit of `CV-DR1` and one cross-question audit.

The final packages are published at `docs/research/policy-operations/cv-dr-decisions/` (`README.md` and one package per question). They are `research_only` recommendations. Every audit returned `GO_WITH_REVISIONS` for a bounded research direction, and all 36 source-qualified findings were accepted. Publication was performed by the architect because the commissioned base was not pushed when the synthesizer tried to publish; the synthesizer refused to substitute another base, which was correct.

**The series' own summary:** the evidence supports five different meanings and their use boundaries, not five new adapters. Define the exact claim and its required ground, check what existing owners already establish, and add only a missing function.

**What the packages did not settle:** every question's *first concrete profile* — a jurisdiction and source profile, a consent regime, an assurance application, a physical target representation, and complete effect coverage. Each package states that the missing input is a real first case, not more research.

**The question.** Which parts of the five recommendations become decisions now, and what happens to the first-profile choices the research could not make?

## The principal's ruling on growth by users (2026-09-17)

The system should grow easily in two directions: capability grows with data, and the number and specifics of its users grow too.

**What the ruling requires.**
- **Adding a user should be cheap.** A new user with their own specifics should not require major refactoring. Where reasonably possible their specifics enter as a profile, data or configuration.
- **It is a design requirement, not a promise.** It is not an attempt to solve everything at once; it is pursued within reasonable bounds.
- **Concreteness is not a prerequisite.** The capability is built first, as neutral to user specifics as reasonably possible. An iterative feedback process then refines the needed functions and any essential differences between users, if such differences appear.

**The current state of concreteness.**
- No concrete pilot and no concrete assurance engagement is determined.
- The jurisdiction will be Ukraine, but whose decision it will be, and at which level of government, is not known.
- The ability to demonstrate the system's full potential on different cases is therefore essential.

## Options considered

| option | what it does | cost, and who pays | disposition |
| --- | --- | --- | --- |
| **A. Accept the meaning principles; keep the first profiles explicitly open** | the stable semantic principles become decisions; each first-profile choice is a named, open input | Candidate and demonstration work builds user-neutral machinery now (engineering); first-profile work waits for real cases (the principal supplies them) | **taken** |
| B. Accept each package's whole proposed choice, including its first-profile preferences | adopts preferences such as an ISAE custody application or a single consolidated-text profile | Commits to specifics before any user demands them — the opposite of the growth ruling | not taken |
| C. Defer everything until a concrete pilot exists | nothing is decided | Stops capability behind a missing institution, which identity decision §9 item 5 rejects, and wastes the stable findings | not taken |
| D. Choose first profiles now by assumption — for example, national Ukrainian legislation | fills the open slots with guesses | Invented specifics become refactoring debt when the real decider turns out to be a different level or body | not taken |

## Decision

### Cross-question principles

1. **Exact claim first.** For each use, name the exact proposition and its required ground. Check what existing owners already establish, and add only a demonstrated missing function — not a new layer because the analysis distinguished two functions.
2. **Constitutive and evidential correspondence differ.** An evidence-grounded assessment within existing scope needs no amendment. A relation that exists *because* a competent act constitutes it gets the `W5-K08` §14.7 scope treatment for that exact positive. This is neither a blanket exemption nor a blanket requirement.
3. **Independence has no common shortcut.** For each premise, name the evidence capable of refuting it — evidence the verifier can reach, not only producer-curated material. Separate files, organisations, signatures or reviewers are not that property. No common provenance label, reviewer office or envelope is introduced. `P37` provenance classes are unchanged.
4. **Over-refusal is a defect too.** Every control against a material substitution is paired with a property-preserving control (a harmless source or format change, a clerical protocol edit, the same target with a different estimator, a sufficient native chain) that must not refuse. Refusals carry reasons.

### Per-question principles and the open first profiles

| question | accepted principle | explicitly open |
| --- | --- | --- |
| `CV-Q1` legal-subject correspondence | A positive is PolicyOS's own **defeasible, purpose-scoped semantic assessment**: for a named purpose, jurisdiction, context and period, this provision version and this lever version concern the same required normative subject, on grounds open to substantive review. External binding determinations stay distinct acts, integrated as evidence within their actual reach. Wrong-making grounds exist at assessment time; a later change of source ends current reuse without falsifying a correctly qualified history. **Implementation breadth is the minimum sufficient source profile**: an adequate single profile may win, and broader profiles must earn their cost. | the first jurisdictional decision level and issuer, the source profile, the first provision–lever pair, who performs the non-producer review |
| `CV-Q2` consent, waiver, ethics | The unit is a **requirement-specific implication of a specific act for a specific requirement and use**. Consent, waiver or alteration, waiver of documentation only, and ethics determinations with their actual outcomes are different acts. Jointly authorised combinations of protocol, site, population, risk and version are preserved and never re-assembled from independent lists. Intake uses the existing `GY-AQ1` and Fabric route, registration uses `GY-VC1`, and **ranking is an intake pattern here, never consent evidence**. Requirement-level satisfaction and applicability completeness are separate claims. | the first regime, the first consumer proposition, whether a single-regime profile suffices or a bounded concurrent profile is needed |
| `CV-Q3` assurance level | `engagement.level` is interpreted **only inside an explicitly named native profile, with no implicit default**, together with its subject, criteria, period, scope and exclusions, the exact assertion and its polarity and quantifier, and the intended use. An integrity PASS or agreed-upon procedures never becomes limited or reasonable assurance. Material or aggregate assurance is not an every-record guarantee. An unqualified opinion on an accurate disclosure of a defect never supports "no defect". Recognising what a report says does not establish the subject's truth. **The start is a reusable case-specific report–demand dossier**, not a predetermined engagement. | the first named application and its criteria; the ISAE custody-attestation candidate stays a candidate |
| `CV-Q4` estimand target binding | **One versioned semantic definition per intended target**, independent of the chosen analysis, addressed from the problem context, with its quantity-defining referents bound. Identity, justified equivalence, directional derivation and transport are distinct relations. `BOUND`, `IDENTIFIED`, `ESTIMABLE` and `ESTIMATED` remain distinct properties. Target history and live evidential support are revised separately. **No second independently editable source of truth.** | the physical representation: a factored target core in the AST with generated views, or a distinct profile where it adds a necessary property |
| `CV-Q5` write operations | The first concrete operation is the served `OperationClass.ACQUIRE` action, `runtime.evidence.acquisition.execute`, bound to its actual effect and governed resource, not "a write to CAS". A protected effect needs **both** an applicable substantive right **and** an applicable technical grant for the same effect, resource, principal, purpose and time. This is necessary and not sufficient. **Native reuse of the existing chain (`execute_bound_effect`) is the implementation presumption**: extend an existing owner only where a missing function is demonstrated. Denied uses of the native dispatch decision stay denied. | the complete effect coverage, phase-specific grant and recovery semantics, and a native end-to-end witness |

### How the open profiles are handled

- **Open means named, not absent.** Each open item is recorded as an input awaiting a real case, with the owner of the question named in its register row.
- **Nothing waits on them.** The machinery that interprets a profile is built now and user-neutrally: profile-qualified interpretation, act and outcome separation, the target core, and native right-and-grant binding. Candidates, demonstrations on varied cases and truthful refusals remain fully buildable (identity decision §9 item 5).
- **A protected positive that depends on an open profile stays unestablished** until that profile is chosen by dated record. The refusal names the missing profile.
- **Ukraine without a known deciding level.** The machinery must not assume a single decision level or issuer inside a jurisdiction. National, regional and municipal deciders, or different bodies at one level, are profiles of one capability, not forks of the design.

## Premises

1. **The packages' stated support.** Their premises tables (§4.3 in each package) and the audits' scoped verification — static source reads at `5494feda2`, and no fresh runtime tests.
2. **Native machinery exists.** `execute_bound_effect` and the denied dispatch uses exist in `runtime/quality/agent_action_authority.py`; the architect re-checked this on 2026-09-17.
3. **Demonstrability is the path to real cases.** Real first cases will come from demonstrating the system on varied cases (identity decision §9 item 5), not from waiting for them.

## Consequences

**Positive.**
- Stable semantics are fixed once.
- New users and jurisdictions arrive as profiles.
- The research's warnings against premature architecture become binding.

**Negative, and accepted.**
- No protected positive in these five domains can be established until a first profile is chosen.
- Demonstrations must be honest about which profile they stipulate.

## What this does not decide

- Any first profile listed above.
- Any appointment or reviewer office, or any external determination.
- Any `§14.7` amendment for a constitutive case.
- Empirical adequacy of review, source profiles or transport.
- Physical schemas.

## Revisit triggers

- **The per-question falsifiers** `Q1-F01`–`Q5-F07` in the published packages.
- **The growth trigger:** adding a user, jurisdiction level or case with new specifics requires refactoring beyond a new profile, data or configuration. Reopen the generic design for that capability — the ruling's target has been missed.
- **The over-refusal trigger:** a demonstration on a new case is refused only because a profile field is unset where the claim did not need it.

## Concrete impact

- **Register rows** (dated appends):
  - `s3-law-to-lever-correspondence-is-unverified`;
  - `corr-wave-unowned-destinations` (`CORR-B1`);
  - `int-r2-ceiling-vocabulary-owners` (normative, assurance and write legs);
  - `estimand-binding-strength-terms-unregistered`;
  - `ds15-int-r2-gap-acquisition-case-union`.
- **ADR-0178**, whose D6 now takes its per-row requirements from this record (see its amendment of 2026-09-17).
- **Backlog Group E** — Completion Ledger entries for `CV-DR1`–`CV-DR5`.

## Related Decisions

- ADR-0178.
- `W5-K07` and `W5-K08`, especially §14.7.
- Identity decision §9 items 5–7.
- `S0-K06`.
