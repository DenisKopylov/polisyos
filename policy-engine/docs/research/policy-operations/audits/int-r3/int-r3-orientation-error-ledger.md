---
task_id: INT-R3
stage: 2
artifact_role: orientation_error_ledger
audit_target: 819a83a88315a90320fdd4b25fcb328b434c77de
status: complete
---

# INT-R3 orientation-error ledger

## Orientation sources

The controlling stage-1 orientation is the commissioned prompt beginning “INT-R3 — stage 1,
research”. It states the exact subject, eight constructs, six metrics, required baseline targets,
five survey inputs, hazards, standing rules and delivery contract.

The current stage-2 prompt is also recorded where its execution instructions conflict with the
pipeline or misdescribe the package. Those entries are not attributed to the stage-1 author of the
package and are not repairable by package amendment.

An orientation statement was treated as an error only when it was internally contradictory, refuted
by the pinned repository or contrary to a governing rule. A demanding instruction that the package
satisfied is recorded as a non-error.

## Errors

| ID | Source | Orientation statement | Verification | Severity | Consequence / owner |
| --- | --- | --- | --- | --- | --- |
| `INT-R3-AUD-O01` | stage 2 | create the audit branch from `dc7bdf79a` | pipeline §2 says an audit branch branches from and contains the research head it responds to; `819a83a88` is not an ancestor of the created audit branch | `material` | The direct instruction was obeyed, but the audit branch does not carry the package. Principal/pipeline owner must either rebase the audit onto the research head or record an explicit topology waiver. |
| `INT-R3-AUD-O02` | stage 2 | package register is `F001-F010`; seven of ten findings are `accepted_narrow_scope` | complete read of the committed register gives `F001-F018`; accepted rows are `F004`, `F005`, `F006`, `F007`, `F009`, `F010`, `F015` | `minor` | Threat framing used a false denominator. Audit uses seven of eighteen. Principal should correct future handoffs. |
| `INT-R3-AUD-O03` | stage 1 | opening identifies INT-R3 as one of Wave 5’s tasks; later says “Unlike the other Wave 8 tasks” | internal contradiction in the same prompt | `minor` | Wave identity and comparison class are unclear. The package followed the substantive INT-R3 row, so no package revision is required solely for this error. |
| `INT-R3-AUD-O04` | stage 1 | “there are real surfaces in this repository showing exactly the eight constructs” | pinned baseline shows Trust, Cycle Board, Case Workspace and Human Decision controls today; outer-set/`unknown`/incomparability, conditional δ, full epoch perturbations and quarantine are plan/in-flight targets | `material` | The orientation conflates current and planned surfaces. The package mostly separates them, but its headline should not inherit “all eight current.” Principal should state `current_targets` and `planned_targets` separately. |
| `INT-R3-AUD-O05` | stage 1 | “the system has ... no evidence anyone understands the output” and the page suite stands at `20/24` | the count was institutionally supplied; no complete human-evidence census, denominator, executor or controls were supplied to the researcher | `material` | `20/24` may be cited as supplied, but the repository-wide zero cannot be inherited as `confirmed`. The prompt should require verification or `not_established`, not command the conclusion. |
| `INT-R3-AUD-O06` | stage 1 | after naming three DS11 debts, says “your benchmark is what would close it” | a behavioral benchmark can close the comprehension-evidence claim; it cannot by itself close page-a11y conformance, an external countersign or the structural checker’s copy-coverage boundary | `minor` | The antecedent is ambiguous. Future prompts should say exactly which claim the benchmark closes and which DS11 debts remain separately owned. |

## Non-errors

| Orientation requirement | Audit result |
| --- | --- |
| behavior, not preference | correctly carried into terminal-action primary outcomes |
| no human-subject claim at stage 1 | correctly carried; current result remains `not_established` |
| mandatory pre-build input | correctly represented through red-first surface constraints, although the later human run remains separate |
| accessible path is not an annex | correctly integrated into item construction, validity and timing |
| confident-and-wrong must remain visible | correctly implemented as direct cells beside calibration metrics |
| borrowed institutions must be named | correctly named; no developer/model is permitted to impersonate them |
| preserve NDM versus heuristics-and-biases disagreement | correctly preserved |
| source-domain rates do not transfer | correctly preserved |
| three standing axes remain separate | fields are separate, although the gate axis uses the wrong predicate and the capability axis misses the DS6 owner seam |
| Markdown-only delivery and branch readback | stage 1 delivered eight Markdown files and a remote branch; stage 2 also remains Markdown-only |

## Consequences

### What the package resisted correctly

The stage-1 researcher did not blindly inherit every orientation defect. It labelled the `20/24`
counts institutionally supplied, separated current targets from in-flight plans in the detailed
baseline, refused to claim a human result and stated that no external rate estimates PolicyOS
behavior.

### What the package inherited

The package promoted the supplied repository-wide evidence zero to `confirmed` without a complete
walk. It also retained the broad premise that all required surfaces exist or are planned without
sharply separating what can be frozen for a study today from what is still a design target.

### What belongs to the principal, not the amendment author

`O01`–`O06` are orientation defects. The package amendment should correct only the claims it actually
inherited. It cannot rewrite the principal’s stage-1 or stage-2 prompts. The principal/pipeline owner
should correct branch topology, wave identity, package counts, current-versus-planned framing,
set-level evidence attribution and the DS11 closure antecedent in future commissions.

## Ledger total

```yaml
orientation_error_total: 6
severity:
  blocking: 0
  material: 3
  minor: 3
  commendation: 0
sum_check: 0 + 3 + 3 + 0 = 6
```

The orientation ledger is complete for the supplied stage-1 prompt plus stage-2 execution instructions
used in this pass. It does not claim that every historical programme instruction was audited.
