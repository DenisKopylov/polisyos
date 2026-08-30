# INT-R5 Orientation Error Ledger

## 1. Supplied Orientation

The stage-1 orientation is the prompt that commissioned INT-R5. It supplied:

- the exact research question and ten required attributes;
- the PolicyOS identity/custody boundary;
- the PAO-R4 non-substitution boundary;
- a mandatory repository baseline against GY-PA2, DS9, DS20, DS14 and acquisition approval;
- three legitimate repository outcomes: sound/formalised, sound but incomplete, or wrong on some
  point;
- the instruction to preserve requirement-derived model and repository comparison separately;
- five external surveys to consume;
- the claim that the ordering constraint had already been violated three times;
- the claim that a live acquisition-approval gateway reused DS9's PA2 arm.

The audit treats those statements as supplied orientation, not as evidence. Each was checked against
the pinned task row, code, plans and closure records.

## 2. Verified Orientation Statements

| Orientation ID | Supplied statement | Audit result | Evidence |
|---|---|---|---|
| `ORI-01` | INT-R5 must define a pre-action decision-authority graph/certificate rather than an after-the-fact audit trail. | **verified as the task subject** | backlog INT-R5 row and prompt question |
| `ORI-02` | The result must address temporal/subject delegation, quorum/co-signature, SoD, COI/recusal, acting/succession, subdelegation, emergency/expiry, mid-operation revocation, cross-agency acceptance and act-type distinction. | **verified** | backlog row enumerates all ten attributes |
| `ORI-03` | The research must remain inside the identity/custody boundary. | **verified** | identity decision and backlog mandatory baseline |
| `ORI-04` | PAO-R4 is a separate individual-use boundary. | **verified** | PAO-R4 and task prompt both state non-substitution |
| `ORI-05` | GY-PA2 had closed before INT-R5 landed. | **verified** | GY-PA2 closure commit `82474845a…` resolves and predates the package |
| `ORI-06` | DS9 had closed before INT-R5 landed. | **verified** | DS9 merge `fd243d1ad…` resolves and records closure 24/24 |
| `ORI-07` | DS20 had closed and supplied a 29-operation action-permission floor. | **verified as a historical receipt** | DS20 merge `03ebc1ce8…`; current vocabulary separately measures 34 |
| `ORI-08` | DS14 was not a landed consumer at the pin. | **verified** | no DS14 task artifact exists in the active `atlas-slices` folder at the pin; the master plan retains DS14 as future work |
| `ORI-09` | The repository outcomes must include “wrong on some point”. | **verified** | prompt explicitly names all three outcomes; the audit found one wrong composition claim |
| `ORI-10` | The researcher must not retrofit shipped fields into the requirement-derived model. | **verified and followed** | package separates target model from repository comparison |
| `ORI-11` | Five commissioned surveys were the external evidence inputs. | **verified** | all five were supplied and their subjects match the prompt; branch custody is separately deficient under A-005 |
| `ORI-12` | The 34/34 Python/Rego parity and `runs.human_decisions.create` addition are real. | **verified independently** | exact current owners agree |

## 3. Orientation Errors

### 3.1 `ORI-E01` — three identical ordering violations

**Supplied orientation:**

> The sequencing constraint was already violated three times.

**Pinned task-row predicate:**

```text
INT-R5 must land before GY-PA2 or Atlas DS9/DS14 consumers close.
```

The same row then says INT-R5 also **feeds** the action-permission vocabulary and
acquisition-approval flow.

At the pin:

- GY-PA2 closed — one explicit ordering violation;
- DS9 closed — second explicit ordering violation;
- DS14 did not close — no third instance;
- DS20 had closed without this input — real downstream-feed drift, but not the same predicate as the
  must-land-before sentence;
- acquisition lacked the claimed PA2/DS9 composition — a separate wiring defect.

The orientation changed relationship type while counting. The correct ledger is:

```text
explicit closure-order violations: 2
missed downstream feed to DS20: 1 distinct dependency drift
acquisition PA2/DS9 bridge missing: 1 distinct wiring defect
```

This error entered the package's `INT-R5-RF-01`, which names GY-PA2, DS9 and DS20 together as the
ordering violation. It does not change the fact that sequencing failed; it changes the denominator
and classification.

Audit finding: `INT-R5-A-009`, **minor**.

### 3.2 `ORI-E02` — live acquisition gateway reusing PA2/DS9

**Supplied orientation:**

> A live acquisition-approval gateway reuses DS9's PA2 arm and adds freshness and post-decision
> revocation checking.

The pinned production acquisition route does not.

Observed route:

```text
POST /api/v1/control/data/ingest
  -> DS20 EVIDENCE_ACQUIRE permission/resource binding
  -> ACQUISITION_APPROVAL step-up
  -> ControlPlaneService.run_data_ingestion
  -> connector/Fabric ingestion
```

Observed DS9 PA2 route:

```text
/api/v1/runs/{run_id}/human-decision-...
  -> HumanDecisionPA2GateInput
  -> HumanDecisionService source/currentness/custody path
```

No edge connects the first path to the second. The orientation may have observed an in-flight or
adjacent gateway design, but it presented it as live acquisition protection. The stage-1 package then
hardened that orientation into the false “acquisition-approval composition” row.

Audit finding: `INT-R5-A-002`, **material**.

### 3.3 `ORI-E03` — “closest seam” versus “landed seam”

The orientation correctly noticed that PA2 + DS9 + DS20 form the smallest plausible reuse path. It did
not preserve the distinction between:

```text
components exist and are composable
```

and

```text
this protected effect actually invokes the composition
```

This is not counted as an additional audit-register row because it is the causal explanation of
`ORI-E02`/A-002, not a second defect.

## 4. Unresolved Orientation Claims

The following orientation claims could not be elevated beyond their bounded form and are deliberately
not additional findings:

| Claim | Audit standing | What would settle more |
|---|---|---|
| GY-PA2 is globally sound | **not established**; narrow five-predicate core survived attack | complete transitive authority/consumer closure and class-wide false-grant tests |
| DS9 is globally sound | **not established**; run-bound source/currentness/custody seam survived attack | complete route/store/concurrency denominator, including separately registered PostgreSQL residual |
| DS20 is globally sound | **not established**; exact permission/resource/step-up floor survived attack | complete route denominator and all authorization-source/binding-authority cases at the pin |
| acquisition has no other institutional gate outside the inspected route | **not established globally**; the actual `ingest_data` effect path contains none | a complete call graph across every acquisition operation, if more than `ingest_data` is claimed |
| all six missing INT-R5 semantics are absent from the repository | **not established** after denominator failure | complete executable/authority closure with positive controls |

The audit does not turn a bounded verification into a universal one merely because no further defect
was found in one pass.

## 5. Consequences For The Audit

The orientation audit changed the package review in four ways:

1. It forced separation of two true closure-order violations from one missed feed and one missing
   bridge.
2. It exposed a real wrongness result under T2 instead of accepting four comfortable verdicts.
3. It prevented “in-flight design” or architectural adjacency from becoming evidence of a production
   call edge.
4. It preserved the valid parts of the orientation: the task subject, five surveys, PAO-R4 boundary,
   three legitimate outcomes and the need to inspect shipped components rather than assume absence.

Orientation errors are not grounds to discard the package. They are precisely why the audit keeps an
orientation ledger separate from the package finding register while cross-linking the two findings
that propagated into package claims.
