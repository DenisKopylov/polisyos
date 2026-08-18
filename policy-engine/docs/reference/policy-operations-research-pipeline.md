# Policy-Operations Research Pipeline

Owner: `team-architecture`
Source of truth for the **stages**; the Wave-2 backlog
(`docs/research/policy-operations-and-real-world-runtime-backlog.md`) remains source of truth for the
**tasks**, the Research Quality Bar and the Unified Deliverable Form.

This specifies how a policy-operations research task travels from commission to ratified decision.
Four waves ran this pipeline before it was written down — Stage 0, INT-R1/R9/R10, INT-R7/R8, and
wave 4 — and each re-derived it from prompts. Every rule below exists because its absence cost
something measurable in one of those waves; where that is so, the cost is named.

Written 2026-08-17, commissioned by ratified `W4-K06`'s parent act
(`docs/system-design-decisions/wave4-decision-evidence-ratification.md` §6.5), which recorded that
five of the six stages were specified in no document and that the pipeline had begun to yield more
findings about itself than about its subjects.

## 1. The stages

| # | Stage | Answers | Run by |
| --- | --- | --- | --- |
| 1 | **Research** | What is true about this subject, and what may the repository safely do with it? | commissioned researcher |
| 2 | **Independent audit** | Where is this package wrong, and what does it claim it has not earned? | an auditor who did not write it, hostile by instruction |
| 3 | **Amendment** | What does the package do about each finding? | the package author |
| 4 | **Amendment verification** | Did the amendment actually close what it says it closed? | a verifier who wrote neither package nor audit |
| 5 | **Remediation → delta verification** | *(conditional)* Are the specific blocking findings now closed, and does the prior verdict lift? | author, then a fresh verifier |
| 6 | **Consolidation** | Across the wave: what is dispositioned, what is routed, what is a candidate? | a consolidator, once per wave |
| 7 | **Ratification** | Which statements bind, and at what price? | the human principal, on an architect-prepared act |

Stages 1–5 are per task; 6–7 are per wave. **Only stage 7 confers authority.** Every earlier stage
produces evidence, and no stage may promote a capability, appoint an owner, or open a gate.

## 2. Branch topology — the rule that was missing

**Each stage branches from the stage it responds to, and its head must contain that stage's head.**

```
research ──► independent-audit ──► amendment ──► amendment-verification
                                        └──► remediation ──► remediation-verification
```

Naming: `research/<task>-<stage>`, e.g. `research/ops-r14-amendment-verification`. Corrections that
land after ratification use `research/<task>-<purpose>-correction`.

**Why this is stated first.** In wave 4 all four amendment branches were cut from **research** rather
than from **audit**, so no response-line branch contained its own audit — 7 commits behind, 11 for
one package. The consequence is not cosmetic: the two lines then collide on the same paths, the audit
line holding the text the findings cite by line number and the response line holding the current
text, hundreds of lines apart. Any reader of a single terminal branch silently loses every audit
finding document. Verify containment before you begin a stage, and stop if it fails.

Two derived rules:

- **Never quote a line number from one line against the other.** Cite the audit line for the defect
  and the response line for the response.
- **History is append-only.** No rebase, force-push, reset onto an ancestor, or stash-as-storage on a
  research branch. A correction adds commits; a standing is changed by an appended record, never by
  rewriting the artifact it describes (`S0-K08` applied to ourselves).

## 3. Per-stage contract

### 3.1 Research

Governed entirely by the backlog: the Mandatory Repo Baseline Study, the Research Quality Bar, the
Unified Deliverable Form (10 sections), the Operational closure addendum, and the Pattern Pass.
Deliver at `docs/research/policy-operations/<task-id>-<short-slug>.md` plus a `<task-id>/` directory.

Report standing on the three ratified axes (`W4-K05`), never one field.

### 3.2 Independent audit

The auditor did not write the package and is instructed to be hostile. Seven artifacts, which is the
shape all four waves converged on independently:

```
<task>-independent-audit.md            the verdict and finding register
<task>-formal-argument-audit.md        the reasoning, attacked
<task>-claim-evidence-ledger.md        every claim against its evidence
<task>-anchor-and-citation-verification.md   do the anchors resolve, and say what is claimed
<task>-seam-and-crosscheck.md          against parallel tasks in the wave
<task>-orientation-error-ledger.md     defects in the supplied orientation
<task>-recommended-revision.md         what would close each finding
```

Verdict: `GO` · `GO_WITH_REVISIONS` · `NO_GO`. Findings carry a severity — `blocking` · `material` ·
`minor` · `commendation` — and the severities must **sum to the register's finding total**.

The `orientation-error-ledger` is not optional. Orientation packs are `institutionally_supplied` to
the agent that receives them (`W4-K01`), and auditing the supplied orientation has found architect
errors in every wave that included it.

### 3.3 Amendment

The package author responds to every finding. One row per finding in
`<task>/amendment-ledger.md`, with disposition ∈ `accepted` · `accepted_with_variation` ·
`declined_with_reason`. A declined finding must give the reason and the evidence; declining is
legitimate and has been correct at least once per wave.

**The dispositions must reconcile against the audit's finding total.** In wave 4 an architect summary
reported dispositions that exceeded each package's own finding count — 46 against 39, 34 against 30,
35 against 31 — because occurrences of a word were counted instead of table rows. One sum check
catches this class entirely; run it before reporting.

### 3.4 Amendment verification

A third party, author of neither the package nor the audit. Verdict: `CONFORMS` ·
`CONFORMS_WITH_GAPS` (name each gap) · `NO_GO` (name each blocker).

Binding rules:

- **Anti-ratchet.** Measure against the audit's findings and the registered patterns at the pin —
  never against the package's own summary of itself, and never against the prompt's summary of the
  package. Where evidence and prompt disagree, evidence wins and you say so.
- **Distinguish an environmental limit from a package defect, in those words.** If your environment
  cannot execute a complete tree walk, that is a gap in *your* verification, not necessarily a defect
  in the package — and it must not be laundered into either direction. In wave 4 the identical
  environmental limit was graded blocking in one package and a material gap in another, and the
  difference was justified only in one of the two cases.
- **A verdict is a vector, not a bit** (`PV-K01`). Report which dimension failed.

### 3.5 Remediation and delta verification (conditional)

Runs only on a `NO_GO`, and is **bounded to the named findings**. The remediating author may not
issue its own replacement verdict — the prior `NO_GO` lifts only through a fresh delta verification.

The delta verifier re-tests only the named findings plus the invariants that must not have moved, and
bounds the delta first: nothing outside those findings may have changed semantically, or the delta is
unverifiable. Per finding: `CLOSED` · `CLOSED_WITH_GAPS` · `NOT_CLOSED`; then the package verdict,
which is the only place the prior verdict may lift.

**Watch for the fixed point** (`W4-K03`): a remediation that preserves a positive by adding a
condition has created a new gate predicate, which must itself be classified. If the added condition
names a different **measurement class** than the evidence constructs, no further round closes it and
the positive must be withdrawn instead.

### 3.6 Consolidation

Once per wave, one consolidator, reading **both lines** of every task. It **dispositions and routes**;
it does not edit package artifacts, does not repair, and does not ratify.

Deliverables — the set converged across waves, and divergence from it has cost coverage:

```
<wave>-consolidation-report.md         what the wave established
<wave>-disposition-ledger.md           every finding, both lines, one row each
<wave>-routing-map.md                  each surviving item to a named destination
<wave>-ratification-candidates.md      propositions with evidence, falsifier, non-effect
<wave>-open-questions-and-next-research.md
<wave>-orientation-audit-record.md     every divergence from the supplied pack, incl. "none found"
<wave>-standing-statement.md           per package and for the wave
```

Two obligations that produced this wave's most valuable findings:

- **The cross-package analogue sweep.** For every confirmed defect, check whether the same defect
  survives unremarked in a sibling package. In wave 4 one verifier caught a census overclaim and
  another, having written *"not freshly recomputed here"* in its own report, left the same defect
  standing. Report the negative result explicitly when no further analogue is found.
- **Route to an owner that exists.** Where no competent destination exists, write *"no owner exists"*.
  Routing an unowned capability to a lane that does not own it leaves it unowned — this is how one
  gap was registered twice under two names before anyone noticed.

### 3.7 Ratification

The architect prepares an act; the human principal accepts it. Form, stable across four acts:

```
1  What is ratified, and why a separate act        7  Prices accepted
2  The lens, inherited                             8  Is the outcome vocabulary changed?
3  Dispositions table                              9  What this does not ratify
4  The statements                                 10  Impact note (constitution §12 form)
5  What this act refutes                          11  Revisit conditions
6  Current standing and architect corrections
```

Frontmatter carries `source_kernel` (the candidates file), `parent_lens`, every controlling head,
`informs`, `authoritative_for` and `may_not_use_for`.

**A separate act requires a separate subject.** Four exist: custody of claims (Stage 0) · what a
number may mean (INT) · what a public proof and projection may mean (PV) · what the deciding
machinery may turn on (wave 4). Amending a prior kernel for a new subject blurs both; the records are
related by inheritance, not revision. Index the act in
`docs/system-design-decisions/README.md`.

## 4. Rules binding every stage

- **Enumerate, never sample** (`P35`). Every set-level fact comes from a script walking the complete
  set, quoted with its path denominator, its file-type denominator, and **the party that executed the
  walk** (`W4-K01`). An index settles neither a zero nor a positive. A census you did not execute is
  `institutionally_supplied` to you and **cannot settle a zero**.
- **A zero needs a positive control.** Report a zero only from a harness that also returned non-zero
  for a token that must exist, and zero for one that cannot. Two harness defects were caught this way
  in wave 4 before any figure was retained; both would otherwise have "confirmed" real zeroes with a
  broken instrument.
- **Run the denominator check before reporting any count** — does it sum to a total the document
  already states?
- **Cite the finding by ID, not the prose around it** (`P36`). An aside in an authoritative source
  carries that source's tone, not its warrant.
- **Classify what the gate turns on** (`P37`), and **name where implementation and property diverge**
  (`P38`). A stop rule keyed to a number, list or directory *you were handed* is a proxy gate.
- **Classify before stopping.** Out of budget means deliver what is complete plus an explicit
  statement of what was not reached. A partial result with an honest boundary is a governed result; a
  complete-looking one built on a sampled branch is not.
- **Resolve identities, never complete them.** Use `git rev-parse`; a short hash extended by hand
  points at nothing and reads as correct.

## 5. Delivery discipline

Markdown only. No source, workflow, binary, staging or transport file, and no edit to `AGENTS.md` or
the pattern register from inside a research stage — those are routed, not made.

Network egress is frequently blocked for research agents. **Never** commit a CI workflow, a base64
fragment, a staging directory, or any self-executing automation as a transport workaround; deliver by
ordinary means and state the limitation instead.

**Read back from the branch after the final write** and report the branch head, the exact file set,
and each file's blob identity. A staging area is not the branch — one task in this project lost a
complete delivery while reporting success, and one wave-4 package could not evidence its own readback.

## 6. What this pipeline does not decide

It produces research contracts. Across four waves it has moved **no capability**: every completed
package has ended `absent/unallocated`, which is the honest label and not a failure. Implementation
authority, owner appointment, and institutional commitments come from elsewhere, and no volume of
pipeline output substitutes for them — a fully specified system can still lack anyone able to sign.
