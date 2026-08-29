---
task_id: INT-R3
stage: 1
artifact_role: finding_register
status: research_complete
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
authoritative_for:
  - int_r3_finding_classification
may_not_use_for:
  - capability_claim
  - operator_comprehension_claim
---

# INT-R3 finding register

Every material finding is classified by kind, research standing and transfer. Evidence standing is
recorded separately and does not replace the three `W4-K05` axes.

| ID | Finding | Kind | Research standing | Source / transfer classification | Consequence |
| --- | --- | --- | --- | --- | --- |
| `INT-R3-F001` | The repository has real typed-refusal, time, weakest-link, acquisition and human-decision surfaces suitable as benchmark targets. | repo baseline | `confirmed` | recomputed from named source coordinates; not a comprehension result | Reuse actual surfaces and packets. |
| `INT-R3-F002` | Trust posture and case surfaces preserve more than a headline: blocker/owner/purpose, denied uses, inspectable evidence and closure signal can remain visible. | repo baseline | `confirmed` | source-derived | Benchmark whether operators use the relation, not whether fields exist. |
| `INT-R3-F003` | Structural and automated accessibility evidence is partial and expressly does not cover arbitrary copy semantics; no admitted human comprehension evidence exists. | negative repo finding | `confirmed` | source-derived; historic page counts institutionally supplied to this researcher | Current comprehension evidence is `not_established`. |
| `INT-R3-F004` | Conformance, notice, recall, preference and acknowledgement do not entail correct action. | cross-domain empirical rule | `accepted_narrow_scope` | mechanism transfers; source-domain rates do not | Terminal action is primary; opinion is diagnostic only. |
| `INT-R3-F005` | Time pressure can shorten search and increase misses, while expert recognition may be useful in valid environments. | competing empirical traditions | `accepted_narrow_scope` | explicit transfer argument; disagreement preserved | Support a fast path, put stop conditions in the first recognizable state, and test deadlines. |
| `INT-R3-F006` | Override frequency alone cannot distinguish rational correction from dangerous bypass. | empirical rule | `accepted_narrow_scope` | clinical mechanism transfers; rates do not | `unsafe_override` uses an adjudicated opportunity denominator and type. |
| `INT-R3-F007` | People may identify the weakest component while misunderstanding chain aggregation or over-focusing repair on that component. | empirical rule | `accepted_narrow_scope` | source tasks differ from governance minimum | Score blocker identification, terminal action and repair choice separately. |
| `INT-R3-F008` | Explicit `unknown`, pure outer sets, strict UI incomparability and δ-budget interpretation lack a mature direct behavioral base. | negative research finding | `deferred_open_problem` | no direct transfer available | Treat each as a hypothesis and keep construct-specific metrics. |
| `INT-R3-F009` | Access to each atomic value does not guarantee access to the qualifying relation under screen-reader or sequential navigation. | accessibility empirical rule | `accepted_narrow_scope` | relation-preservation mechanism transfers; exact effect does not | Accessible path is part of every item and timing model. |
| `INT-R3-F010` | Professional title and tenure cannot substitute for measured numeracy, graph literacy or assistive-technology proficiency. | empirical rule | `accepted_narrow_scope` | prevalence does not transfer | Measure and stratify; do not exclude low-literacy target operators. |
| `INT-R3-F011` | Correctness can be formally exact for semantic states while operational action remains set-valued or contestable. | benchmark protocol | `confirmed` | logical/procedural distinction adapted from formal semantics and RAND/FDA practice | Seal three-layer truth and retain `contestable`. |
| `INT-R3-F012` | Accuracy without calibration can hide a confident-and-wrong safety tail. | measurement result | `confirmed` | proper scoring and direct-cell definitions | Brier/curve plus direct high-confidence-wrong denominators are mandatory. |
| `INT-R3-F013` | A blocked unsafe attempt is evidence about intended action, not a committed harm and not proof of comprehension. | benchmark protocol | `confirmed` | derived from event semantics | Log attempt and commit separately. |
| `INT-R3-F014` | A single latency mean is invalid when some operators never reach a correct action. | benchmark protocol | `confirmed` | survival/competing-outcome reasoning | Report correctness by deadline and censored/competing latency. |
| `INT-R3-F015` | Current evidence does not demonstrate that the demonstrability ruling is false; it demonstrates a material risk and a missing test. | architectural interaction finding | `accepted_narrow_scope` | inference from absence of a direct PolicyOS study | No early architect stop now; a failed real benchmark can trigger one. |
| `INT-R3-F016` | Until the benchmark is executed with real target operators on a frozen build, PolicyOS surface comprehensibility and actionability are `not_established`. | controlling negative result | `confirmed` | direct consequence of no run | Literature and structural checks may not close the claim. |
| `INT-R3-F017` | The benchmark specification is a mandatory pre-build input, but no admitted owner, study run or result chain exists. | capability finding | `confirmed` | `W4-K06` classification | `capability_standing: absent/unallocated`. |
| `INT-R3-F018` | Publication or production cannot cite this package as operator-comprehension evidence. | gate finding | `confirmed` | comprehension-claim boundary | `gate_standing: NO_GO` for that claim. |

## Separate standing axes

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
evidence_standing: not_established
```

### Rationale

- `accepted_narrow_scope`: the protocol, failure mechanisms and pre-build constraints are supported;
  transfer limits and open problems remain explicit.
- `absent/unallocated`: Markdown is an input, not an admitted contract/producer/consumer chain, and
  no benchmark owner or institutional adjudicator is appointed.
- `NO_GO`: no actor may claim operator comprehension, use it as closure evidence, or let a favorable
  structural score stand in for a behavioral result.
- `not_established`: this additional evidence-status annotation says the target human result has not
  been measured. It does not merge or replace the three registered standing axes.
