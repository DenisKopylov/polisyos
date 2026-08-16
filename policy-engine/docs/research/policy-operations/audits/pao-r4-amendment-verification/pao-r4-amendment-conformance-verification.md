---
title: PAO-R4 Amendment — Independent Conformance Verification
verification_id: PAO-R4-AMV
status: delivered_independent_verification
verdict: CONFORMS_WITH_GAPS
blocking_findings: 0
material_gaps: 1
minor_findings: 0
verified_amendment_commit: 0df03f35e9b6403b7f54fd8bd45373a951851d8c
verified_substantive_payload_commit: 04ff572baa38aa405acdb29cfaf3c46388aae30e
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
independent_audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
verification_branch: research/pao-r4-amendment-verification
research_only: true
authoritative_for:
  - pao_r4_amendment_independent_conformance_verdict
  - pao_r4_audit_finding_closure_assessment
  - pao_r4_ratified_kernel_conformance_assessment
  - exact amendment branch geometry and package readback recorded below
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, authority, consumer, or case-system appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - repair or mutation of the amendment branch
  - automatic amendment of any plan, backlog, audit, or system-design decision
---

# PAO-R4 amendment independent conformance verification

## 1. Verdict — classified before stopping

**`CONFORMS_WITH_GAPS` — 0 blocking findings, 1 material verification gap, 0 minor findings.**

The amendment at `0df03f35e9b6403b7f54fd8bd45373a951851d8c` conforms substantively to all
three blocking findings in the hostile independent audit and to the ratified kernels inspected at
`109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.

The one gap is the complete literal source census. The amendment correctly labels the
`106 files / 794 matching lines / 903 occurrences` result as architecture-supplied and states both
path and file-type denominators. This verifier independently established source-tree equivalence,
the named seventh CSV fixture, the partition construction, and the internal arithmetic, but could not
freshly walk every immutable source blob with `git grep`: ordinary clone/archive egress was blocked
and the GitHub connector exposes exact file reads rather than a bulk source-tree materialization.
Under registered `P35`, an index or ranked connector result is not a complete denominator. Therefore
the literal totals are not promoted here from architecture-supplied to independently recomputed.

That gap is material because audit finding `PAO-R4-I-002` expressly required reproducible raw-tree
execution. It is not blocking to the corrected semantic contract: the E/G/X/S boundary, authority-
scoped refusal, predicate-provenance rule, four-location detection model, voluntary-channel
impossibility, mandatory consumer-use gate, and no-capability/no-owner posture all close independently
of the unrerun token totals.

No amendment file was repaired or changed by this verification. The only delivery is this Markdown
verification record on the requested output branch.

## 2. Verification basis and anti-ratchet method

The controlling inputs were read at exact commits:

| Input | Exact object |
|---|---|
| amended final head | `0df03f35e9b6403b7f54fd8bd45373a951851d8c` |
| substantive payload head | `04ff572baa38aa405acdb29cfaf3c46388aae30e` |
| audited parent | `a27c3da9942b03881dbee1005a8a1e44e5ac44b4` |
| independent audit | `69182c079fb5dc99808d7cd27874d50433efd5a4` |
| documentation / ratification pin | `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` |

The audit's 30-finding register and recommended revisions were treated as the questions. The
amendment ledger and delivery receipt were treated only as claims to test. Kernel conformance was
checked against the ratification records themselves:

- `stage0-custody-kernel-ratification.md` — authority-band/candidate-band lens and binding K06 note;
- `int-r7-r8-public-verification-and-disclosure-ratification.md` — `PV-K04`;
- `int-wave-claim-semantics-ratification.md` — `INT-K02` and `INT-K08`;
- `policyos-identity-and-custody-boundary.md` — PolicyOS owns the firewall, not the individual act.

Repository geometry came from exact compare objects and post-read file objects. Semantic findings
came from complete ranged reads of the amended primary report and all 556 lines of the falsifier
suite, cross-checked against the comparative model and integration handoff.

## 3. Orientation audit

### 3.1 Branch geometry

Comparing the audited parent to the final amendment head gives:

- merge base exactly `a27c3da9942b03881dbee1005a8a1e44e5ac44b4`;
- **14 commits ahead / 0 behind**;
- **6 modified + 2 added Markdown paths**;
- **0 deleted paths**;
- **0 source paths**;
- **0 independent-audit-branch paths**;
- **1,732 additions / 1,090 deletions**.

The substantive payload head is separately **13 ahead / 0 behind**, with six modified Markdown paths
and one added Markdown path. The final commit adds only the 149-line amendment delivery readback.

### 3.2 Eight amended paths — exact counts and blobs

Each final line count was checked at its last line with the next line absent. The compare arithmetic
and exact post-read blobs are:

| Path | Status | Additions | Deletions | Final lines | Git blob at `0df03f35` |
|---|---|---:|---:|---:|---|
| `policy-engine/docs/research/policy-operations/pao-r4-individual-decision-firewall.md` | modified | 448 | 304 | 541 | `8e063c819a02757135bca89cbd6a3523f350fc11` |
| `policy-engine/docs/research/policy-operations/pao-r4/amendment-delivery-readback.md` | added | 149 | 0 | 149 | `c82c309518353d5f68211e9e9218f3701f7c6f5a` |
| `policy-engine/docs/research/policy-operations/pao-r4/amendment-ledger.md` | added | 130 | 0 | 130 | `61c511541a31a3ad6886189ee3c9e157a1f1835a` |
| `policy-engine/docs/research/policy-operations/pao-r4/comparative-models.md` | modified | 149 | 119 | 212 | `8fa1fd269607a75745ca3eea5b5bc51f78b6ccac` |
| `policy-engine/docs/research/policy-operations/pao-r4/external-primary-source-and-transfer-ledger.md` | modified | 91 | 50 | 139 | `6cf08f5ccada5132bfe5b20a9fb3b8c92651fe88` |
| `policy-engine/docs/research/policy-operations/pao-r4/falsifier-suite.md` | modified | 421 | 292 | 556 | `a31c2d12548126fbf54f93f081218e829a36d8e9` |
| `policy-engine/docs/research/policy-operations/pao-r4/orientation-ledger.md` | modified | 149 | 207 | 203 | `ba71120333ea8e529f488138d85783fab72ba803` |
| `policy-engine/docs/research/policy-operations/pao-r4/repository-integration-handoff.md` | modified | 195 | 118 | 266 | `eb0c9846cd0d66640077fbe5d2bcf475e3c11c41` |
| **total** | **6 modified + 2 added** | **1,732** | **1,090** | **2,196** | — |

The line sum is exact:

```text
541 + 149 + 130 + 212 + 139 + 556 + 203 + 266 = 2,196
```

### 3.3 Two unchanged delivery-accountability files and 10-file package

The original delivery-accountability files are byte-identical between the audited parent and final
amendment head:

| Path | Lines | Blob at audited parent and amendment head |
|---|---:|---|
| `policy-engine/docs/research/policy-operations/pao-r4/delivery-incident-ledger.md` | 94 | `b5eb046cda91f6ff5479e2f7fc3ab6e379627fa5` |
| `policy-engine/docs/research/policy-operations/pao-r4/delivery-readback.md` | 107 | `a69ba9eed464c1417b64546b79c4ee1d47b749a2` |

Therefore the complete PAO-R4 package is exactly **10 files / 2,397 lines**:

```text
2,196 amended-path lines + 94 + 107 = 2,397
```

### 3.4 Source pin identity

Comparing `1a7a2d05ebba22fae80e9934329e4b880806588e` to the documentation pin
`109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` changes only:

- `AGENTS.md`; and
- `policy-engine/docs/reference/policy-design-case-failure-patterns.md`.

No `policy-engine/src` path changes. The amendment's source-equivalence premise is therefore
confirmed.

### 3.5 Census — two denominators, partition, named fixture, and gap

The amended ledger states the two required denominators:

- path denominator: `policy-engine/src`;
- file-type denominator: Python only or all non-binary source files.

It records:

| Query | File-type denominator | Files | Matching lines | Occurrences |
|---|---|---:|---:|---:|
| exact `may_not_use_for` | Python | 106 | 794 | 903 |
| exact `may_not_use_for` | all non-binary source files | 106 | not separately supplied | not separately supplied |
| case-insensitive `anonymi` | all non-binary source files | 7 | not separately supplied | not separately supplied |
| case-insensitive `anonymi` | Python | 6 | not separately supplied | not separately supplied |
| exact `individual_decision` | all non-binary source files | 0 | 0 | 0 |
| exact `export_gate` | all non-binary source files | 0 | 0 | 0 |
| exact `prohibited_use` | all non-binary source files | 0 | 0 | 0 |

The `may_not_use_for` partition is structurally disjoint and exhaustive **conditional on the complete
106-file hit set**:

- `runtime` is the prefix set below `policy-engine/src/polisyos/runtime/` — 67;
- `scientist` is the distinct prefix set below `policy-engine/src/polisyos/scientist/` — 12;
- `remainder` is defined as the Python hit set minus both prefixes — 27;
- the prefix sets do not overlap, the remainder is a set difference, and
  `67 + 12 + 27 = 106`.

This is more than an arithmetic sum: the predicates are mutually exclusive and their union is the
stated hit set.

The seventh all-source `anonymi` path was fetched directly at the pin:

`policy-engine/src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_block_context_sociocultural.csv`

It contains `anonymity`, confirming why a Python-only six-file denominator omitted it.

**Material gap `PAO-R4-AMV-I-001`:** this verifier could not independently rerun the complete raw-tree
walk. Consequently the package's literal totals, including the settled zeroes, remain corroborated
and internally reconciled but not freshly recomputed here. This is the sole reason the verdict is not
`CONFORMS`.

## 4. Complete audit-finding closure register

The hostile audit contains 30 findings: 3 blocking, 13 material, 1 minor, and 13 commendations. The
following register is derived from the audit findings, not from the amendment's disposition summary.

| Audit finding | Independent result | Conformance evidence |
|---|---|---|
| `PAO-R4-I-001` | closed | Seven all-source / six Python `anonymi`; seventh CSV named and directly read. |
| `PAO-R4-I-002` | **material verification gap** | Amendment supplies 106/794/903 with both denominators; fresh complete-tree execution unavailable here. |
| `PAO-R4-I-003` | preserved, subject to the same census gap | Disjoint 67/12/27 construction, seven `aggregate_only`, and stated zero concepts retained. |
| `PAO-R4-II-001` | closed | Comparison narrowed to “not narrower on the material-reliance/formal-finality trigger”; no global dominance claim. |
| `PAO-R4-II-002` | closed | Canada instrument/tool versioned; M-25-21 current in the ledger and M-24-10 marked historical/replaced. |
| `PAO-R4-II-003` | preserved | Non-transfer and non-compliance limits remain explicit. |
| `PAO-R4-II-004` | preserved | Legal/statistical sources remain tied to bounded propositions. |
| `PAO-R4-III-001` | closed with justified variation | Empirical tuple diagnosis narrowed; E/G/X/S added; refusal binds authority effect, not executability. |
| `PAO-R4-III-002` | closed | Five-way frozen predicate provenance; asserted/supplied/unestablished predicates cannot green an authority gate; consultation replaces operator counterfactual. |
| `PAO-R4-III-003` | closed | `individualizable(a,H)` deterministically catches singleton and complete pointwise empirical artifacts. |
| `PAO-R4-III-004` | preserved | Empirical non-entailment remains exactly for non-pointwise E. |
| `PAO-R4-IV-001` | closed | Four detection locations, each with required inputs and incomplete-input result. |
| `PAO-R4-IV-002` | closed | Positive claim bounded to named governed boundary; institution-wide non-use unavailable. |
| `PAO-R4-IV-003` | closed with justified variation | R11 incident/lower-bound/sampled recovery added without weakening complete non-use impossibility. |
| `PAO-R4-IV-004` | preserved | Detection location remains the organizing principle. |
| `PAO-R4-IV-005` | preserved | Voluntary-silence observational equivalence remains verbatim in substance. |
| `PAO-R4-V-001` | closed with justified variation | G may travel as candidate rule input; identical-syntax empirical decision surface remains refused. |
| `PAO-R4-V-002` | preserved | Candidate computation and safe population planning remain allowed. |
| `PAO-R4-VI-001` | closed | Manual/cognitive/off-ledger routes are outside the positive and can force refusal. |
| `PAO-R4-VI-002` | closed | Complete logs do not prove materiality; consultation itself turns the conservative gate. |
| `PAO-R4-VI-003` | preserved | Returning evidence remains semantic, denominator-reconciled, and fail-closed on absence. |
| `PAO-R4-VII-001` | closed | F-01 admits planning, then requires the mandatory consumer-use gate to return `BLOCK_PURPOSE`. |
| `PAO-R4-VII-002` | closed | 26 one-world cases; counterfactual laundering, class shopping, purpose synonym, and multi-hop relay added. |
| `PAO-R4-VII-003` | preserved | Join, pointwise rule, projection narrowing, and query reconstruction attacks remain substantive. |
| `PAO-R4-VIII-001` | preserved | `PV-K04` inherited rather than re-ratified; denied uses cannot shrink. |
| `PAO-R4-VIII-002` | preserved | Stage-0, INT, identity, anti-role, and correction-interface boundaries remain within their findings. |
| `PAO-R4-IX-001` | closed | `public_export.py` no longer appointed by adjacency; emission placement is open. |
| `PAO-R4-IX-002` | preserved | PAO-R4-specific chain remains `absent/unallocated`. |
| `PAO-R4-X-001` | closed by durable independent record | Amendment receipt names the substantive head and blobs; this separate verification record names and verifies final amendment head `0df03f35`. |
| `PAO-R4-X-002` | preserved | Markdown-only isolation, frontmatter prohibitions, and no capability/compliance upgrade hold. |

No audit blocking finding remains open.

## 5. The architect's narrowing — decisive conformance test

### 5.1 Diagnosis

`PAO-R4-III-001` is correctly treated as `accepted_with_variation`.

The audit was right that the delivered contract refused a class it had not justified refusing. The
amendment is also right about where the formal defect lived: the empirical expression
`theta = Phi(D_B)` is a functional over a data-generating or causal object. It did not itself admit a
normative universal rule. The contradiction arose when the crossing/refusal sections treated general
rules as empirical estimates and used executability as a refusal predicate.

The repair is kernel-conformant:

| Class | Meaning | Protected-crossing result |
|---|---|---|
| E | empirical population summary/probability/effect | allowed only when non-individualizable under reconciled `H`, with basis and denied uses; otherwise X/refuse |
| G | normative general rule under external authority/procedure | candidate rule-level transport may remain unblocked; PolicyOS authority/applicability/determination remain `NOT_ESTABLISHED` |
| X | individual or pointwise-recoverable artifact | no governed protected-action crossing |
| S | synthetic non-case example | allowed only while non-resolvable; a real-subject match becomes X |
| unknown/mixed | unresolved class or decisive predicate | `NOT_ESTABLISHED` and refuse protected crossing |

Non-entailment applies only to E. Refusal applies to authority-to-determine, empirical
individualization, denied use, and unobservable prohibited use—not to executability as such.

### 5.2 Audit Artifacts A/B/C

| Artifact | Independent test | Required result | Amended result |
|---|---|---|---|
| A — singleton empirical cell | resolves one person and reveals the empirical outcome | X / refuse | `REFUSE_EXPORT` in primary §3.3 and F-05 |
| B — complete deterministic empirical partition | total feature-to-action mapping is a pointwise decision surface | X / refuse | `REFUSE_EXPORT` in primary §3.3 and F-06 |
| C — competent normative universal rule | executable rule syntax is expected; authority remains external | G; no executability-only refusal | candidate transport not blocked; authority/applicability `NOT_ESTABLISHED`; F-07 forbids `REFUSE_EXPORT` solely for executability |

F-08 supplies the required control: an executable empirical decision tree with the same surface
syntax is refused because semantic class and pointwise authority effect differ.

### 5.3 Laundering attacks against G

The following adversarial variants were applied to the package's general rules rather than to its
labels:

| Attack artifact | Attempted laundering route | Package result |
|---|---|---|
| executable vendor threshold `if risk_score(x) > .7 then deny`, labelled “general rule” | use G syntax to carry an empirical model into a case | content/source classification finds empirical coefficients and a pointwise protected-action output: E becomes X or class is mixed; F-08/F-26 refuse or return `NOT_ESTABLISHED` |
| executable subject-keyed schedule labelled “rule” | hide a list of named or resolvable subjects behind normative syntax | `individualizable(a,H)=1`; subject resolution or pointwise mapping makes it X and refuses crossing |
| pure universal rule from a real but non-competent private source | reconcile source identity and exploit missing authority | candidate transport may remain unblocked, but competence/authority is only `institutionally_supplied`; no authority-grade positive is available, applicability remains `NOT_ESTABLISHED`, and protected use cannot proceed green |
| executable G plus an asserted “competent authority” marker | make a declaration substitute for authority | P37 freezes the predicate as `institutionally_supplied` or `not_established`; marker presence cannot green the authority gate |
| G candidate later represented as PolicyOS's own determination or reason | exploit the permitted transport after issue | primary §4.4 and the consumer-use rule block the authority effect; G explicitly denies representation as PolicyOS determination, fact finding, reason, or authority grant |

A true G object can pass only as candidate-band rule-level input with **no authority to determine**.
That is not laundering: the package prevents the same object from producing an authority-grade
protected action. No constructed artifact passed both candidate transport and the downstream
authority/use gates. A pass through the latter would be blocking; none was found.

## 6. `individualizable(a,H)` and the four detection locations

### 6.1 Predicate tests

The amended predicate holds exactly when there exists a resolvable subject for whom the artifact plus
named permitted history/auxiliary model reveals an individual fact or supplies a pointwise mapping
that determines or materially constrains a protected action.

| Variant | Result |
|---|---|
| singleton empirical cell plus directory resolution | true — reveals a subject fact; E becomes X |
| complete mutually exclusive empirical partition plus total case-feature mapping | true — pointwise mapping; E becomes X |
| two otherwise safe aggregates whose join resolves one subject | true under complete `H`; composition blocks |
| ranking/threshold table consulted for a resolved protected action | true or denied-use consultation; protected crossing/use blocks |
| synthetic row that uniquely matches a real subject under `H` | true; S becomes X |
| incomplete release/query inventory or auxiliary model | `NOT_ESTABLISHED`; no protected-crossing positive |
| genuine G applied by an external competent procedure | individual applicability alone does not make it empirical X; authority/applicability remain external and unavailable to PolicyOS |

### 6.2 Four locations

| Location | Required inputs | Incomplete-input result |
|---|---|---|
| artifact-local | artifact bytes, parser, artifact semantics, registered basis obligations, resolved controlled lineage | explicit individual form/refusal; unresolved artifact/lineage `NOT_ESTABLISHED`; artifact inspection cannot prove omitted assumptions absent |
| export-context under named `H` | complete release/query history, auxiliary/linkage model, population inventory, behavioral interpreter, source identity and authority provenance | unsafe composition blocks; incomplete/unknown `H` or class returns `NOT_ESTABLISHED` and refuses protected crossing |
| downstream use-context | resolved subject, protected-action effect, exact artifact/derivative digest, instrumented consultation, mandatory gate, reconciled action totals | denied consultation `BLOCK_PURPOSE`; bypass `FIREWALL_VIOLATION`; incomplete instrumentation/denominator yields no complete positive |
| outside declared boundary / not observable | explicit boundary exclusions and residual-channel analysis | `NOT_DETECTABLE` is not permission; an actionable artifact with a material unobservable route is refused |

The package states the limiting proposition in all load-bearing locations: complete in-boundary
evidence cannot establish institution-wide non-use.

## 7. Voluntary-channel result and R11 recovery

The observational-equivalence proof survives intact:

```text
world A: no prohibited use; no report
world B: prohibited use; no report
observation: identical
```

Therefore a voluntary channel cannot establish complete non-use. The amendment does not soften that
result in the primary report, comparative model, integration handoff, or F-12/F-13.

R11 recovers only narrower values:

| Evidence | Maximum claim |
|---|---|
| content-bound report | that report establishes its own incident |
| known denominator with incomplete participation | lower bound on observed prohibited uses |
| valid predeclared sampled audit | sampled estimate/rate/interval for that frame |
| mandatory complete independently reconciled boundary | bounded in-boundary complete-use/non-use statement, still subject to residual channels |

None establishes complete institution-wide non-use. F-12 and F-13 both keep the complete firewall
claim at `FIREWALL_CLAIM_NOT_ESTABLISHED`.

## 8. P37, conservative use, F-01, and fixture shape

### 8.1 P37 provenance and exact labels

The registered labels are exactly:

```text
recomputed
independently_reconciled
consumer_asserted
institutionally_supplied
not_established
```

The amendment uses only those five. The last three cannot yield an authority-grade positive.

The branch-timing claim requires one qualification. In Git ancestry, the amendment line is cut from a
pre-P37 branch: its audited-parent copy of the failure-pattern register stops at P36, and
`109ba3f44` is not an ancestor; the merge base is `1a7a2d05`. In wall-clock time, the P37 registration
commit at 2026-08-08 09:04:53 UTC precedes the first amendment commit at 09:28:49 UTC. Thus “predates”
is true as branch ancestry, not as amendment-authoring time. The substantive provenance conclusion
still holds: commit `109ba3f44` explicitly records P37 as the four-audit wave's cross-task result,
and the amendment imports that external commission result rather than inventing a sixth label.

### 8.2 Conservative use rule and S-1/S-2

During a resolved protected action, consultation, display, query/invocation, supply, thresholding,
ranking, recommendation, evidence weighting, explanation, or routing by the artifact/derivative
counts as use. A consumer statement that the action “would not have changed” is only
`consumer_asserted` and cannot keep the gate green.

- S-1 is explicitly outside the positive boundary: reconciled in-boundary records do not cover later
  remembered/off-ledger reliance.
- S-2 stays blocked because instrumented consultation occurred; the asserted counterfactual is not the
  gate predicate.

### 8.3 F-01 and 26 single-world cases

F-01 is one exact world:

1. an E artifact is truthfully requested and exported for programme-capacity planning;
2. a later resolved subject faces benefit-eligibility denial;
3. the consumer thresholds the population rate;
4. the mandatory `consumer_consultation_gate` returns exactly `BLOCK_PURPOSE` before action.

The file expressly says the red signal must not come from request or exporter. Its
remove-property/keep-markers probe requires F-01 to fail if real consumer-gate behavior is deleted
while labels and fields remain.

A complete 556-line read establishes:

- cases exactly F-01 through F-26;
- exactly one `detector` and one `expected_verdict` per case;
- **26 `expected_verdict` fields**;
- no `if_*` expected field;
- no `with_*`/`without_*` world split;
- no “at least one” gate;
- no disjunctive or multi-verdict expected field;
- no new product outcome vocabulary.

## 9. Ratified-kernel conformance

### 9.1 Stage-0 authority-band lens

The Stage-0 ratification asks whether a rule binds only the authority band or leaks into the candidate
band. Its binding K06 application note allows candidate computation under declared uncertainty while
failing closed for protected actions, published claims, and custody facts.

The amendment follows that lens. It does not forbid executable candidate computation or transport;
it blocks authority-to-determine, empirical individualization, denied use, and unobservable protected
use. A firewall over executability would indeed forbid PolicyOS's own rule-based obligation and
admissibility outputs, so the narrowing is required rather than permissive drift.

### 9.2 Identity boundary

The ratified identity decision says PolicyOS **owns the individual-decision firewall** while the
individual decision remains external. The amendment owns semantic crossing, denied-use survival,
consultation visibility, evidence return, and refusal. It does not own case facts, external authority,
procedure, reasons, review, remedy, or final act.

### 9.3 PV-K04

`PV-K04` permits detail reduction but forbids amplification of truth, certainty, authority, currency,
or permission; denied uses do not shrink. The amendment preserves the source/derivation denial union
and blocks narrowing through projection, correction, derivative, or relay. F-09, F-16, and F-25
exercise that invariant.

### 9.4 INT-K02 / INT-K08

`INT-K02` keeps a numerical claim inseparable from its declared basis and assumptions. PAO-R4 uses
that bounded lesson without re-ratifying it: an E artifact missing basis obligations cannot carry an
authority-grade crossing.

`INT-K08` preserves negative completion. PAO-R4 likewise treats refusal, `NOT_ESTABLISHED`, and
`FIREWALL_CLAIM_NOT_ESTABLISHED` as valid bounded outcomes rather than permission to weaken a gate.
The R11 claim lattice adds no status-vocabulary element.

No kernel contradiction was found.

## 10. Standing shape — exact, not normalized

The amended research files carry exactly:

| Axis | Field | Value |
|---|---|---|
| research | `result_standing` | `GO_WITH_REVISIONS` |
| adoption | `adoption_status` | `NO_GO_pending_independent_conformance` |

This verification does not replace those fields with a sibling package's standing vocabulary. Its
separate result is `verdict: CONFORMS_WITH_GAPS`. Research remains
`GO_WITH_REVISIONS`; adoption remains the amendment's recorded
`NO_GO_pending_independent_conformance` until the competent consolidation/adoption authority acts.

## 11. Final conformance judgment

The decisive semantic question is answered **yes**: the amended package conforms to the independent
audit's three blocking repairs and to the ratified kernels.

The bounded final classification is:

| Class | Count / result |
|---|---|
| blocking findings | **0** |
| material verification gaps | **1** — complete raw-tree literal census not freshly executable |
| minor findings | **0** |
| verdict | **`CONFORMS_WITH_GAPS`** |

The gap must not be rewritten as an independently reproduced census. It does not authorize repair of
the amendment, implementation, adoption, a case-system workflow, an external authority appointment,
or an operating firewall claim.

## 12. Delivery boundary

This verification adds one Markdown file only:

`policy-engine/docs/research/policy-operations/audits/pao-r4-amendment-verification/pao-r4-amendment-conformance-verification.md`

It adds no source, workflow, binary, transport artifact, staging directory, CI automation, or
self-executing upload mechanism. The verification branch's post-write head, exact delta file set, and
blob identity are established by connector readback after the write and reported separately, avoiding
self-reference in this file.
