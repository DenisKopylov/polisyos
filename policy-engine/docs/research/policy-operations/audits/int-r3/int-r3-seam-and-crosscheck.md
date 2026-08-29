---
task_id: INT-R3
stage: 2
artifact_role: seam_and_crosscheck
audit_target: 819a83a88315a90320fdd4b25fcb328b434c77de
status: complete
---

# INT-R3 seam and crosscheck

## Governing seams

### Pipeline topology

The pipeline requires each stage branch to branch from the stage it responds to and to contain that
stage’s head. The supplied stage-2 delivery instruction instead required
`research/int-r3-independent-audit` to branch from `dc7bdf79a`, while the research package is at
`819a83a88`. The audit obeyed the direct delivery instruction and records the result: the audit branch
does not contain the package commit it audits. This is `INT-R3-AUD-O01` and is an orientation error,
not a stage-1 package amendment.

### `W4-K05` standing seam

The three axes are not interchangeable:

```yaml
research_standing: confirmed | accepted_narrow_scope | refuted | blocked | deferred_open_problem
capability_standing: absent/unallocated | contract_only | ... | implemented
gate_standing: GO | NO_GO
```

`gate_standing` is the first-public-signature gate. The package instead uses it as a local prohibition
on citing INT-R3 as comprehension evidence. The local prohibition is correct; the field is wrong for
that predicate. The seam repair is:

```yaml
gate_standing: NO_GO  # only with the actual DS12/global basis at the pin
comprehension_claim_use: NO_GO
int_r3_is_ds12_gate_input: false
```

### `W4-K01` / `P35` seam

The package properly labels historic page-a11y counts as institutionally supplied. It does not apply
the same discipline to its repository-wide zeros. “No admitted human comprehension evidence,” “no
canonical behavioral contract” and “no owner” require a complete pinned walk or must remain
`not_established`. The DS6 owner statement independently refutes the unqualified owner zero.

### Identity/custody boundary

The package’s four-way verdict is sound in shape:

- PolicyOS owns the requirement that its own authority projections be demonstrated as usable;
- recruitment, ethics, employment conditions and operational authority are integrated evidence;
- adoption/training/workarounds are observed;
- preference is not correctness.

No sovereign employer, ethics board, court or operational command system is absorbed. No conflict
with the identity boundary was found.

## Parallel-task seams

### `INT-R5` — decision authority

INT-R3 measures whether an operator correctly reacts to an authority state. It does not define whether
a particular person or body actually holds authority. The stage-1 package correctly routes delegation,
quorum, recusal, conflict, succession and acting authority to INT-R5/GY-PA2/DS9. Its action key may
consume an authority certificate or typed refusal; it may not author one.

**Crosscheck result:** seam holds at the research-contract level.

### `INT-R6` — semantic identifiers and terminology

The benchmark depends on stable meanings for `unknown`, `incomparable`, evidence state, action and
blocker identifiers. INT-R3 may test comprehension of those meanings but must not create a competing
canonical vocabulary. The package treats its event and artifact shapes as candidates and routes
consolidation.

**Crosscheck result:** seam holds, subject to later vocabulary consolidation.

### `OPS-R15` — capstone and realistic workflow

The benchmark needs realistic lifecycle and after-hours context; OPS-R15 can supply capstone cases.
The benchmark supplies human action measurement. The package explicitly prevents either side from
claiming the other’s authority or unresolved producer.

**Crosscheck result:** seam holds. The capstone is not a substitute for target-operator recruitment or
actual-use validation.

### DS15 — acquisition, quarantine and re-entry

INT-R3 may constrain how acquisition routes and quarantine states are presented and measured. The
stage-1 baseline correctly marks the full quarantine/re-entry path as planned/in-flight rather than
current comprehension evidence.

**Crosscheck result:** no ownership conflict. Direct quarantine behavior remains an open empirical
problem.

### DS16 — value, `unknown`, outer set and incomparability

INT-R3 provides red-first semantic and behavioral constraints; DS16 owns the value grammar and
surface implementation. The package correctly forbids point collapse and unsupported ranking.

**Crosscheck result:** seam holds. The direct human evidence for the constructs remains
`deferred_open_problem`; the package needs construct-specific resolution conditions.

### DS17 — δ accounting

DS17 owns the confidence-ledger/risk-spend surface. INT-R3 tests whether the conditional δ rider
survives action and accessibility paths. It may not define the obligation set, risk budget or
publication semantics.

**Crosscheck result:** seam holds. `AUI-R05` is a semantic-unit constraint, not evidence of human
interpretation.

### DS18 — epoch and staleness

DS18 owns epoch and perturbation semantics. INT-R3 measures whether operators preserve the distinction
and choose a permitted action. `AUI-R06` currently overreaches by treating unchanged affordance as
universally wrong; it must be scoped to a currentness-dependent action whose admitted basis is the
stale item.

**Crosscheck result:** seam needs the `AUI-R06` revision.

### DS9 — human-decision machinery

The current `HumanDecisionGate` exposes rights, required role, evidence exposure, mandate validity and
server-offered actions/modes. INT-R3 may use those actual controls and log attempted/committed actions.
It may not reinterpret server authorization or treat a disabled action as comprehension.

**Crosscheck result:** seam holds. Primary blocker identification must be captured before or as part of
the terminal action, not only retrospectively.

## DS12 boundary

### What DS12 actually owns

At `dc7bdf79a`, DS12 is the **Public Publication Foundation**. Its gate requires:

1. a first governed promotion through GY-N9;
2. GY-N11 δ-accounting and GY-N12 epoch validity;
3. DS11;
4. the named pre-publication research inputs `INT-R7`, `INT-R8`, `INT-R1` and preregistered `INT-R9`.

A complete search of the master plan finds INT-R3 in the DS6 research-input augment, not in the DS12
gate. The plan says the behavioral battery and thresholds join the stable bar for interactive
authority surfaces and that **DS6 owns the instrument**.

### What INT-R3 may decide

INT-R3 may decide whether its own package is admissible as a research input and whether any actor may
cite it as evidence that humans understand PolicyOS. Until a real benchmark result exists:

```yaml
comprehension_claim_use: NO_GO
```

INT-R3 may not independently close or block the DS12 first-public gate. DS12 remains closed for its own
named predicates. A later ratified decision could add comprehension evidence as a DS12 dependency;
this package cannot do so by frontmatter.

### Gap between the package and DS12

There is no uncovered publication gap created by keeping INT-R3 outside DS12. A public record may be
governed and still make no claim that a particular operator UI has been behaviorally validated. If a
public surface later claims usability, accessibility comprehension or safe human action, that **claim**
requires evidence; it does not retroactively change DS12’s current gate definition.

**Verdict on T8:** the package’s substantive non-use rule is correct; its `W4-K05` gate axis is
mis-scoped and must be revised (`INT-R3-AUD-F010`).

## Cross-package analogues

### No capability moved

The pipeline’s completed research packages consistently terminate with research standing accepted or
confirmed while capability remains `absent/unallocated`. INT-R3 follows that pattern honestly: prose,
scenario grammar and metric definitions are inputs, not an operational benchmark chain.

The owner seam is the exception that must be named. The Atlas master plan has already allocated the
instrument to DS6. That does not make the capability implemented, but it means “unallocated” is not
established without adjudicating whether the allocation is live, stale or superseded.

### Formal disagreement versus institutional authority

The package’s use of set-valued `A_i*` resembles prior research packages that preserve disagreement
instead of forcing a scalar. The same rule applies here: a method such as RAND supplies a procedure,
not an appointed PolicyOS institution. INT-R3 handles this correctly and leaves the institution absent.

### Conformance versus behavior

The repository already distinguishes structural a11y checks from comprehension. INT-R3 does not
collapse them. Its own twelve-predicate battery needs a typed partition so that future “12/12” reports
cannot turn structural or instrumentation conformance into a behavioral result.

## Seam conclusion

The package has no sovereign-boundary breach and does not absorb INT-R5, DS9, DS15–DS18 or OPS-R15.
Three seams require revision:

1. reconcile the master plan’s DS6 instrument ownership with the package’s owner zero;
2. split the global DS12 gate from the local comprehension-claim-use prohibition;
3. scope the staleness predicate to a decision-critical currentness relation.

All are repairable in amendment. None requires `NO_GO` for the research programme as a whole.
