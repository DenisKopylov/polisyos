# INT-R6 - Multilingual Authority Equivalence

## 1. Task And Project Fit

### Commission and authority boundary

`INT-R6` is Stage 1 research. It may establish a research result, contract sketch, falsifiers, routing, and evidence requirements. It does not create a runtime capability, appoint a language institution, register a production vocabulary, promote a gate, or amend D4-A1. Only later pipeline stages may do those things.

The commission is wider than catalog translation. It asks how PolicyOS can keep three different kinds of language claim apart:

1. product UI authorship and translation, already governed by D4-A1;
2. the language or languages in which a jurisdiction's legal source is authoritative;
3. PolicyOS governance semantics that must remain identical across jurisdictions even when their rendered labels differ.

The target must run now for one jurisdiction, `en`/`uk` active UI and frozen `ru`, with zero appointed linguistic holders. It must admit jurisdiction N+1, including an RTL or co-authentic jurisdiction, by adding evidence and an admission record rather than changing the model.

### D4-A1 disposition

**D4-A1 composes with the architecture and does not require revisit.** D4-A1 governs the product UI plane: `en` authored/primary, `uk` translated, `ru` `legacy_continuity_frozen`, source-content rendering separate, RTL `not_supported`. INT-R6 specifies the separate source-content, authentic-text, rendering, and governance-semantic planes. None of D4-A1's revisit triggers is activated merely by defining those planes.

Formal finding: `INT-R6-F001` (`repo_fact`) in [the repo baseline](int-r6/repo-baseline-study.md).

### Step 0 delivery receipt

Ordinary Git transport was attempted first and failed before repository mutation:

```text
$ GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/DenisKopylov/polisyos.git dc7bdf79a
fatal: unable to access 'https://github.com/DenisKopylov/polisyos.git/': Could not resolve host: github.com
```

The permitted GitHub connector was then used. This is a connector-based receipt, not a reconstructed terminal transcript:

```text
$ git rev-parse research/int-r6-research
f75259752ca5fe2b181c96097dddfec09d70b807

$ git rev-list --count dc7bdf79a..research/int-r6-research
1

$ git ls-tree -r --name-only research/int-r6-research | grep int-r6
policy-engine/docs/research/policy-operations/int-r6-multilingual-authority-equivalence.md

$ git ls-remote --heads origin research/int-r6-research
f75259752ca5fe2b181c96097dddfec09d70b807	refs/heads/research/int-r6-research
```

The branch was created from full base SHA `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`; the first commit contained only this title and the Unified Deliverable Form's ten empty headings.

### Research method

The pass used four evidence classes and keeps them separate:

- repository facts pinned to the base SHA and named coordinates;
- complete bounded walks with denominators and the commissioned researcher as executing party;
- commission-supplied external surveys, treated as surveyed practice rather than PolicyOS capability or authority;
- architecture inferences, explicitly marked as design results rather than existing implementation.

Formal findings are IDs `INT-R6-F001` onward. Each has one of these research classifications: `repo_fact`, `external_practice`, `architecture_requirement`, `engineering_gap`, `institutional_gap`, `measurement_gap`, `open_question`, or `routed_architect_issue`. These labels do not replace W4-K05 standing.

Supporting package:

- [Repo baseline study](int-r6/repo-baseline-study.md)
- [External evidence register](int-r6/external-evidence-register.md)
- [Protocol and fixtures](int-r6/protocol-and-fixtures.md)
- [Pattern pass and standing](int-r6/pattern-pass-and-standing.md)

## 2. Current Repo Baseline

### Baseline verdict

The current repository has important ingredients but not the commissioned capability:

- D4-A1 and runtime contracts enforce active product locales `en`/`uk`; `ru` is retained but not selectable.
- The selected product UI locale still enters run requests as `locale_preference`, so UI and source-content preferences are not actually independent.
- Catalog parity proves active `en`/`uk` paths and frozen `ru` integrity, not translation meaning.
- ICU/plural/numeric-message controls are material strengths, but generic placeholders and mixed-language outputs expose morphology and fragment-composition risk.
- `stale`, `superseded`, and `withdrawn` already have distinct canonical IDs; `limited` is scoped to more than one owner; `may_not_use_for` members often remain free strings.
- The trust MACHINE twin proves exact artifact-to-DOM projection of raw IDs, not multilingual semantic equivalence.
- Lex/Data Forge can store a document language, but do not model designated-source versus co-authentic authority, translation manifestations, or a content render locale.
- `SPOCandidate` currently hard-codes a Ukrainian-source/English-canonical extraction shape. That is a concrete English-pivot dependency, not a universal authority architecture.
- Source-content rendering exists only as fragments; RTL remains `not_supported`.

### Catalog measurement

The current catalog set was completely walked as 3/3 blobs:

| Catalog | Blob | Bytes |
| --- | --- | ---: |
| `en.json` | `c2e9070927213a5bdf3453165ee6825794e02134` | 137,508 |
| `uk.json` | `ded19bfcfbc65e457f1effc04d4ffb13debd8173` | 174,803 |
| `ru.json` | `07a1b4fadded69fc3435be9eca235eb85c4c24d4` | 136,204 |

`parity.test.ts` currently asserts `PRIMARY_LOCALE == en`, equality of `uk` and authored `en` key paths, and a frozen `ru` set of 2,449 keys plus a fixed leaf-value digest. It does not assert a current active leaf count, identity share, translation completeness, entailment, modality, scope, or status preservation.

D4's 888/2,449 (36.26%) `uk == en` and 1,963/2,449 (80.16%) `ru == en` values remain correctly attributed to the DS0 historical snapshot. This connector-only pass could not transfer the current raw JSON bytes into an executable counter, so it does not relabel those historical percentages as current. That is finding `INT-R6-F008` (`measurement_gap`), with a precise closure measurement in the baseline companion.

### Language-axis baseline

| Axis | Current implementation | Research disposition |
| --- | --- | --- |
| product UI locale | implemented for `en`/`uk`; D4-A1-governed | preserve unchanged |
| legal/source language | one string on a document; Ukraine/English-specific extraction fields | refine into an authority-text regime |
| content render locale | not independently modelled; UI locale crosses launch boundary | add independent read-only render request/admission |
| governance semantic ID | present in some registered owners, absent/free-text in others | reuse existing owner IDs; close gaps owner-by-owner |
| representation kind | implicit (`source_text_only`, catalog translation) | make explicit: verbatim, translation, adaptation, summary |
| script direction | no admitted RTL profile | keep `not_supported`; add evidence-backed admission record |

### Boundary census

| Boundary | Verdict |
| --- | --- |
| D4-A1 product UI posture | `existing` |
| structural catalog parity | `existing` |
| frozen `ru` integrity | `existing` |
| selected status IDs | `existing` |
| multilingual authority equivalence | `partial` |
| source-content render bridge | `missing-bridge` |
| jurisdictional authentic-text authority | `external-institution owner` |
| high-stakes wording adjudication | `external-institution owner`, currently unbound |
| RTL admission | `missing-bridge` |

The detailed coordinates, walk denominators, and findings `INT-R6-F001` through `INT-R6-F019` are in [the repo baseline study](int-r6/repo-baseline-study.md).

## 3. External Research Baseline

## 4. Result

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
