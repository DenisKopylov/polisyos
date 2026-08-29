---
task_id: INT-R3
stage: 4
artifact_role: amendment_verification
verification_target: 32cfebd02354b4d70fbf8beaca168aea6f2e72ee
research_head: 819a83a88315a90320fdd4b25fcb328b434c77de
audit_head: 8e9be1e5e737312f92579b57a7f011b9b14d3a46
branch: research/int-r3-amendment-verification
verdict: CONFORMS_WITH_GAPS
status: complete
finding_total: 23
verification_results:
  satisfied: 19
  satisfied_with_gap: 4
  not_satisfied: 0
package_gaps:
  - G1_same_pin_factual_supersession_locality
  - G2_external_claim_traceability_incomplete
---

# INT-R3 amendment verification

## Verification scope and method

This pass measures the amendment against the stage-2 audit findings and their closure conditions,
not against the stage-3 ledger's account of itself and not against the commissioning prompt's factual
summary. The controlling inputs are:

- audit finding register: `int-r3-independent-audit.md#finding-register`;
- closure predicates: `int-r3-recommended-revision.md#finding-by-finding-closure-conditions`;
- anchor evidence: `int-r3-anchor-and-citation-verification.md`;
- registered patterns at the pin, especially `P35`–`P38`;
- the amendment bytes at `32cfebd02354b4d70fbf8beaca168aea6f2e72ee`.

The amendment branch was read as a single append-only history containing research, audit and response.
No package, audit or amendment artifact is changed by this verification stage.

### Containment

The verification branch began at the amendment head. The remote graph and an exact-object local Git
readback both establish:

```yaml
contains_amendment_32cfebd02: true
contains_audit_8e9be1e5e: true
contains_research_819a83a88: true
```

All three `merge-base --is-ancestor` checks return `0`.

### Independent measurements

The verifier performed the following bounded checks:

- complete read of all 23 audit rows and all 23 amendment dispositions;
- complete read of the effective package index, amendment specification, baseline amendment and
  source ledger;
- comparison of the research head with the amendment head;
- verification that the audit artifacts retain their stage-2 blob identities;
- direct read of the unchanged stage-1 baseline, finding register, main deliverable and benchmark
  specification where the audit finding concerns text that still stands;
- complete read of all 16 `EXT-*` source-map rows;
- SHA-256 and byte-count recomputation over all five supplied survey files;
- direct resolution of the two source identifiers the amendment reports self-correcting;
- independent classification of all twelve `AUI-R*` predicates;
- invariant checks over verdict, standing, appointments and preserved commendations.

## Step 0 channel proof

The headings-only artifact was committed before substantive verification at:

```text
1992f6c44d1e8a7e461d161b05b828d7160b2eb9
```

The command outputs at that point were:

`git rev-parse research/int-r3-amendment-verification`

```text
1992f6c44d1e8a7e461d161b05b828d7160b2eb9
```

`git rev-list --count dc7bdf79a..research/int-r3-amendment-verification`

```text
19
```

`git merge-base --is-ancestor 32cfebd02 research/int-r3-amendment-verification; echo $?`

```text
0
```

`git merge-base --is-ancestor 8e9be1e5e research/int-r3-amendment-verification; echo $?`

```text
0
```

`git merge-base --is-ancestor 819a83a88 research/int-r3-amendment-verification; echo $?`

```text
0
```

`git ls-remote --heads origin research/int-r3-amendment-verification`

```text
fatal: unable to access 'https://github.com/DenisKopylov/polisyos.git/': Could not resolve host: github.com
```

The last command is a non-receipt. The connected GitHub API independently showed the remote ref at the
scaffold commit; that connector observation is not substituted for the failed terminal command.

## Additive-discharge criterion

The pipeline makes history append-only and specifically requires a standing change to be an appended
record. It does not make every later sentence capable of curing every earlier false fact.

This verifier applies the following criterion per finding.

### Additive discharge is sufficient when

1. the later file names the audited clause or finding it supersedes;
2. the current package index makes the precedence relation explicit;
3. the subject is a versioned standing, protocol rule, measurement contract, ownership state or other
   proposition whose effective state can legitimately change through a later record; and
4. the later record fully supplies the audit's closure predicate without upgrading an invariant.

Under this rule, the field split for `gate_standing`, the feasibility split, the predicate partition,
the exclusion guard, the novel-construct resolution table, the transfer bridges and the blocker-event
rule may be discharged additively. In particular, `F010` is correctly discharged by an appended
standing record: the pipeline expressly says a standing changes by appended record rather than by
rewriting its historical artifact.

### Additive discharge is insufficient by itself when

1. the original assertion was factually false at the same pinned revision rather than later becoming
   stale;
2. the original file still declares itself authoritative for that fact or classification;
3. a direct reader of that canonical file receives the false assertion without a local tombstone or
   supersession marker; and
4. the correction repairs narrative elsewhere but leaves the original binding live.

That is the `P36` correction-binding rider applied to research artifacts. The effective package index
reduces the severity, but it does not erase the artifact-local conflict.

### Resulting split

Additive form is adequate for `F004`–`F012` except where a separate substantive gap is named, and for
`O01`–`O04` and `O06`. It is only partially adequate for the same-pin factual claims in `F001` and
`F002`; `O05` inherits the `F002` result. `F003` uses a valid additive source-ledger form, but the
ledger's content does not yet meet the audit's repository-only reconstruction signal.

## Per-finding verification

### Package findings

| Audit ID | Amendment disposition | Verification result | Evidence-based ruling |
| --- | --- | --- | --- |
| `INT-R3-AUD-F001` | `accepted` | `SATISFIED_WITH_GAP` | The baseline amendment correctly withdraws `TrustPostureContent` and gives the actual `TimeSemanticsLabel` contract. However, `repo-baseline.md` remains byte-identical, still declares `authoritative_for: int_r3_repo_baseline`, and still contains both false same-pin assertions with no local tombstone. Package-level truth is corrected; artifact-local authority is not. Gap `G1`. |
| `INT-R3-AUD-F002` | `accepted` | `SATISFIED_WITH_GAP` | The amendment discloses the sampled search and downgrades the human-evidence and canonical-contract zeroes to `not_established`. The effective result is safe. But the unchanged authoritative finding register still marks `INT-R3-F003` `confirmed` and the main deliverable still states the repository-wide zero. The later index resolves current use but leaves a same-pin factual conflict. Gap `G1`. |
| `INT-R3-AUD-F003` | `accepted_with_variation` | `SATISFIED_WITH_GAP` | All five survey digests/byte counts reproduce and every `EXT-*` row has a map entry. The two self-caught identifiers resolve. The audit's repository-only acceptance signal is still not met for rows that rely on “the survey's ... studies” or a negative review result whose survey body is not committed: visibly `EXT-01`, `EXT-03`, `EXT-04`, `EXT-06` and `EXT-07`. The ledger fails those claims closed, so this is a traceability gap rather than a blocker. Gap `G2`. |
| `INT-R3-AUD-F004` | `accepted_with_variation` | `SATISFIED` | The amendment names candidate operators, surfaces, workflow, deadline/interruption mechanism and a non-transfer case for time pressure. It separately types probabilistic conjunction, Boolean all-must-pass, ordinal governance minimum and intervention allocation, and narrows `F007` to a hypothesis generator. The variation concedes the defect rather than renaming it. |
| `INT-R3-AUD-F005` | `accepted` | `SATISFIED` | The four-row resolution table supplies comparator, target population/condition, behavioral endpoint, eligible denominator, precision dependency, transport boundary, refuting result and layer-specific exit from `deferred_open_problem`. No threshold is invented. |
| `INT-R3-AUD-F006` | `accepted_with_variation` | `SATISFIED` | Full item flow and per-stratum counts are required; total absorption produces `coverage_insufficient`; an aggregate score is suppressed when a mandatory stratum disappears; main-study use additionally requires a preregistered per-stratum opportunity target. This closes the audit's logical 100% escape while preserving set-valued truth. The absent numeric threshold is an explicit institutional dependency, not a disguised decline. |
| `INT-R3-AUD-F007` | `accepted` | `SATISFIED` | The effective result now separates protocol coherence, technical implementation readiness, programme execution feasibility and actual study execution. No recruitment frame or precision plan is manufactured, and a stronger infeasibility result requires a sponsor-side feasibility receipt. |
| `INT-R3-AUD-F008` | `accepted` | `SATISFIED` | `AUI-R06` is narrowed to a currentness-dependent action with the stale item in the admitted basis, no independently current substitute and no governed override. One positive and three safe identical-affordance negative-control classes are supplied. |
| `INT-R3-AUD-F009` | `accepted` | `SATISFIED` | The twelve predicates are partitioned as 6 surface-semantic + 3 enforcement + 3 instrument-integrity + 0 behavioral. A `12/12` report must print that composition and `human_comprehension_established: false`. No pre-build green can be reported as human evidence. |
| `INT-R3-AUD-F010` | `accepted` | `SATISFIED` | The appended effective standing retains `gate_standing: NO_GO` with the DS12 first-public basis and adds `comprehension_claim_use: NO_GO` plus `int_r3_is_ds12_gate_input: false`. The global gate and local claim-use restriction can now vary independently. The unchanged historical text does not defeat this standing correction because append-only standing supersession is the pipeline rule. |
| `INT-R3-AUD-F011` | `accepted` | `SATISFIED` | `Bhat_primary_i` is pre-terminal or constitutive of the terminal event; `Bhat_posthoc_i` is diagnostic only; the schema distinguishes viewed, selected, action-triggering and retrospectively named; and the requested wrong-action/late-recognition negative is present. |
| `INT-R3-AUD-F012` | `accepted_with_variation` | `SATISFIED` | The prior DS6 allocation is classified `stale`, its closure commit and consequence are recorded, current ownership is `unowned`, and allocation is routed to the human principal. No successor is appointed and capability remains `absent/unallocated`. This is the audit's requested ownership adjudication, not an evasion. |
| `INT-R3-AUD-C001` | `accepted` | `SATISFIED` | The amendment repeatedly retains no-human-result and `not_established`; the additive preservation statement is new even though the commended substance remains unchanged. |
| `INT-R3-AUD-C002` | `accepted` | `SATISFIED` | Eligible-opportunity denominators, attempt/commit separation, censored/competing latency and direct confident-and-wrong cells remain unchanged and are explicitly protected by the amendment. |
| `INT-R3-AUD-C003` | `accepted` | `SATISFIED` | Accessible relation parity, real AT users and modality-specific timing remain core instrument requirements, not an annex. |
| `INT-R3-AUD-C004` | `accepted` | `SATISFIED` | Three-layer truth, set-valued `A_i*`, retained disagreement and explicit missing adjudicators survive; the exclusion repair does not force consensus. |
| `INT-R3-AUD-C005` | `accepted` | `SATISFIED` | No source-domain rate is imported, and the NDM-versus-heuristics disagreement remains unresolved. The new transfer bridges narrow rather than erase that boundary. |

### Orientation findings

| Audit ID | Amendment disposition | Verification result | Propagation and response |
| --- | --- | --- | --- |
| `INT-R3-AUD-O01` | `accepted` | `SATISFIED` | The topology defect did not alter stage-1 semantics. The two-parent union and all three containment checks repair its repository consequence. |
| `INT-R3-AUD-O02` | `accepted_with_variation` | `SATISFIED` | The amendment follows the audit's row denominator: `F001`–`F018`, with seven `accepted_narrow_scope` finding rows. Nine literal occurrences include the separate package-standing declaration and rationale. This is denominator discipline, not evasion. |
| `INT-R3-AUD-O03` | `accepted` | `SATISFIED` | No material stage-1 conclusion depended on the erroneous Wave-8 comparison. The amendment handoff identifies INT-R3 as Wave 5. |
| `INT-R3-AUD-O04` | `accepted` | `SATISFIED` | The detailed amendment census now separates current rendered targets, a current partial time primitive, and DS15–DS18 planned/in-flight targets. The broad inherited premise no longer controls effective target status. |
| `INT-R3-AUD-O05` | `accepted` | `SATISFIED_WITH_GAP` | The supplied `20/24` remains institutionally supplied and the effective package downgrades the sampled zero. Because the propagated zero remains in the unchanged authoritative stage-1 finding register/main text, this carries the same artifact-local gap as `F002`; no additional defect is counted. Gap `G1`. |
| `INT-R3-AUD-O06` | `accepted` | `SATISFIED` | The amendment states that the benchmark can close only the behavioral-comprehension evidence claim; page a11y, external countersign and arbitrary-copy checking remain separate obligations. |

### Reconciliation

```yaml
finding_total: 23
satisfied: 19
satisfied_with_gap: 4
not_satisfied: 0
sum: 19 + 4 + 0 = 23
```

The four `SATISFIED_WITH_GAP` rows are `F001`, `F002`, `F003` and `O05`. `O05` shares `G1`; it does
not create a third package gap.

## Accepted-with-variation verification

| Finding | Audit asked | Amendment substituted | Verification |
| --- | --- | --- | --- |
| `F003` | repository-only exact claim-to-source reconstruction | survey digests/windows plus stable source ledger, with unresolved anchors failing closed | Legitimate partial concession, but not full closure because several rows still require uncommitted surveys. `SATISFIED_WITH_GAP`. |
| `F004` | construct the target bridges for `F005`/`F007` | explicit time-pressure bridge and typed weakest-link source-task partition; `F007` narrowed | Fully addresses the defect. `SATISFIED`. |
| `F006` | bound exclusion without forcing consensus | nonnumeric fail-closed coverage state, full item flow and required preregistered main-study targets | Fully addresses the 100%-absorption defect without borrowing a threshold. `SATISFIED`. |
| `F012` | adjudicate live/stale/superseded/unresolved owner seam | stale DS6 allocation, current unowned state, principal route, no appointment | Fully addresses the seam. `SATISFIED`. |
| `O02` | correct the false finding denominator | distinguishes seven finding rows from nine literal token occurrences | The distinction is the exact correction demanded by `P35`. `SATISFIED`. |

## Zero-decline review

Zero declines is not itself evidence of deference. The only plausible candidate for decline was
`F006`, but the audit's 100% bound is a logical construction: without a coverage rule, an entire hard
stratum could be excluded. No empirical estimate is needed for that possibility. The amendment was
right not to claim a tighter realistic bound without an item bank. Its nonnumeric fail-closed rule is
a concession and repair, not a decline in disguise.

No other audit finding had an evidentiary basis for rejection. The five commendations were findings to
preserve, and the orientation errors were either accepted by the principal or independently visible in
the repository history.

## Invariant verification

| Invariant | Result | Evidence |
| --- | --- | --- |
| Audit verdict remains `GO_WITH_REVISIONS` | `PASS` | The audit artifact is byte-identical and the amendment explicitly does not issue a replacement verdict. |
| Human comprehension remains `not_established` | `PASS` | README and amendment specification retain `not_established`; no study result is introduced. |
| `research_standing: accepted_narrow_scope` | `PASS` | Effective README and amendment standing retain the registered value. |
| `capability_standing: absent/unallocated` | `PASS` | Effective standing is unchanged; an unowned research specification is not promoted to a chain. |
| `gate_standing: NO_GO` | `PASS` | Value is retained; only its basis is corrected. |
| No institutional holder appointed | `PASS` | Instrument owner is `unowned`; human principal is a routing destination, not an appointee; no adjudicator, panel or threshold owner is created. |
| Commendation C001 preserved | `PASS` | No-human-result and literature/non-substitution boundary remain. |
| Commendation C002 preserved | `PASS` | Denominators, attempts/commits, latency and HCW cells remain. |
| Commendation C003 preserved | `PASS` | Accessible relation parity and real-AT conditions remain. |
| Commendation C004 preserved | `PASS` | Set-valued truth and disagreement remain. |
| Commendation C005 preserved | `PASS` | Rate non-transfer and theoretical disagreement remain. |

No blocker invariant moved.

## External source resolution

### Survey identities

The five supplied survey files reproduce all five SHA-256 values and byte counts in
`external-source-ledger.md`:

```text
SURV-01  74673 bytes  9ee76f2bc23ecf118365c0ab0f7f92b4a1e03417ff6f8fa3abe00b071c0ae67e
SURV-02  72801 bytes  cefa71c2261beb11fec0c7808cd280425911cb5b2e5ba19feec0e5affc0b499f
SURV-03  61511 bytes  82b404d93a10cca0d788cb817bf4944980f92204b822af924c1185e75579142f
SURV-04  78961 bytes  39491d6731185cdb16e5cc1ea91a5981cd9e139ca4d6f46791613d77be811475
SURV-05  61762 bytes  d8eda1e5c6867a52f452e3e5fa77053ef19269101a8bc240c3a3bce9ad3d331c
```

The survey line totals in the ledger match their logical file line counts. The files omit a terminal
newline, so POSIX `wc -l` reports one fewer newline character; that is not a ledger discrepancy.

### Self-caught identifiers

`PMID 6827763` resolves to Hanley and Lippman-Hand, *If nothing goes wrong, is everything all right?
Interpreting zero numerators*, JAMA 249(13), 1743–1745 (1983). It is the correct source behind the
zero-event rule-of-three diagnostic attributed by `EXT-13`.

`10.1007/11555261_68` resolves to Eaton, Plaisant and Drizd, *Visualizing Missing Data: Graph
Interpretation User Study*, INTERACT 2005, pages 861–872. The publication describes a 30-participant
between-subject comparison of three missing-data display variants and supports the missing-information
mechanism attributed by `EXT-02`.

The amendment's self-correction is therefore verified and merits a precise commendation: it discovered
and repaired its own identifier error before stage-4 review.

### Remaining traceability gap

The stable ledger is materially better than stage 1, but these map entries still delegate load-bearing
support to unavailable survey content rather than to the stable anchors named in the row:

- `EXT-01`: “plus the survey's risk/uncertainty experiments”;
- `EXT-03`: a negative-review conclusion with only adjacent anchors;
- `EXT-04`: “consumer-budget studies identified in the survey”;
- `EXT-06`: “the survey's fireground/AEGIS studies”;
- `EXT-07`: “pathology/speaking-up anchors in the survey”.

The survey digests prove identity, not accessibility. A repository-only reader cannot reconstruct all
five claims from committed bytes and stable identifiers. The explicit fail-closed rule prevents this
gap from becoming authority; it does not satisfy `RR-02`'s full acceptance signal.

## Predicate-partition verification

The partition sums exactly:

```yaml
surface_semantic_contract:
  - AUI-R01
  - AUI-R02
  - AUI-R03
  - AUI-R05
  - AUI-R08
  - AUI-R09
  count: 6

enforcement_contract:
  - AUI-R04
  - AUI-R06
  - AUI-R07
  count: 3

instrument_integrity:
  - AUI-R10
  - AUI-R11
  - AUI-R12
  count: 3

behavioral_trial: []
behavioral_count: 0
total: 6 + 3 + 3 + 0 = 12
```

The assignments are defensible against the stage-1 red witnesses:

- `R01`–`R03`, `R05`, `R08` and `R09` ask whether a semantic relation is represented without collapse;
- `R04`, `R06` and `R07` ask whether an inadmissible ranking/currentness/admission state can authorize
  action;
- `R10`–`R12` ask whether the measurement instrument can observe attempts, elicit confidence before
  feedback and preserve sealed keys.

None requires a real participant to go green. The amendment says so at the point where `12/12` is
permitted, so the audit's conformance-versus-comprehension concern is closed.

## Verdict vector

```yaml
overall_verdict: CONFORMS_WITH_GAPS

vector:
  branch_topology_and_delivery: CONFORMS
  finding_and_disposition_coverage: CONFORMS
  protocol_and_metric_revision: CONFORMS
  predicate_partition_and_staleness: CONFORMS
  standing_and_invariant_preservation: CONFORMS
  institutional_boundary: CONFORMS
  self_caught_source_identifier_repair: CONFORMS
  same_pin_factual_correction_locality: CONFORMS_WITH_GAPS
  external_claim_traceability: CONFORMS_WITH_GAPS

gaps:
  G1_same_pin_factual_supersession_locality:
    affects: [INT-R3-AUD-F001, INT-R3-AUD-F002, INT-R3-AUD-O05]
    dimension: baseline_and_finding_binding
    result: effective package is corrected, but false same-pin assertions remain in unchanged files
      that still declare baseline/finding authority
    settles_when: original baseline/finding surfaces carry a local tombstone or amended status and
      point directly to the superseding clauses, without deleting history
    blocker: false

  G2_external_claim_traceability_incomplete:
    affects: [INT-R3-AUD-F003]
    dimension: evidence_reproducibility
    result: survey identities and many primary anchors resolve, but five EXT rows still require
      uncommitted survey content or unnamed source families
    settles_when: each affected row receives exact stable primary identifiers and result locators, or
      a readable committed extract/bibliography sufficient for repository-only reconstruction
    blocker: false
```

No structural defect requires `NO_GO`. Neither gap upgrades standing, permits benchmark passage or
launders missing evidence: the package remains fail-closed. A bare `CONFORMS` would nevertheless be
wrong because `RR-01`'s no-unresolved-false-coordinate signal and `RR-02`'s repository-only
reconstruction signal are not fully met.

## Environmental limits

Ordinary Git transport could not resolve `github.com`. This is an **environmental limit in my
verification**, not a package defect.

It prevents a clean terminal `ls-remote` receipt and direct `git fetch`. It does not prevent content,
remote-ref or ancestry verification here because:

1. the connected GitHub API exposed the exact remote commits, parents, trees, blobs and branch ref;
2. the local Git readback was built from those exact Git objects, with each constructed commit hash
   checked against its remote SHA before the ancestry commands were run; and
3. all package/audit/amendment text used for the verdict was read from the connected repository at the
   pinned heads.

The failed `ls-remote` is retained as a non-receipt and is not laundered into success. The limitation
belongs to the transport-observation dimension of this verification; it is not a finding against the
amendment.

## Consolidation-only observation

The package's amended evidence is correct at `32cfebd02`: `TimeSemanticsLabel` there does not expose an
`epochSemantics` prop. Any later branch that adds such a prop must not be used to rewrite the pinned
baseline. This observation creates no new audit finding.

## Final readback

The final remote readback occurs after this file's final commit. The stage-4 hand-back reports the
final command outputs and API-observed remote ref; this artifact does not pre-claim its own future
commit SHA.
