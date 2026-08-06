---
title: PAO-R4 comparative models
research_id: PAO-R4
artifact_role: comparative-model-survey
status: research
research_only: true
repository_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# Comparative models

## 1. Selection criterion

A model is retained only if it contributes an observable that makes the commission's violation
falsifiable. The decisive questions are:

1. can the exporter decide the violation from the artifact and request;
2. if not, can a consumer-side event make it visible;
3. is the evidence obligation complete and mandatory; and
4. if neither boundary can observe the use, does the model refuse the export class?

No single model answers all four. The selected architecture is a conjunction with refusal as its
terminal case.

## 2. Survey and disposition

| # | Model | Contribution | Eliminating property when used alone | Disposition |
|---:|---|---|---|---|
| 1 | Artifact-class allow-list | Makes the export boundary enumerable and default-deny. | A permitted aggregate can still be used for a person after export; class membership alone does not reveal use. | **Selected as first gate, never alone.** |
| 2 | Form-based transformation: aggregate-only, k-anonymized, rule-level-without-parameters | Removes obvious rows, keys, small cells, and executable parameters. | “Anonymized” is auxiliary-information- and composition-relative; aggregate form does not prevent downstream individual application. | **Selected as bounded transformation tests; rejected as a sufficient guarantee.** |
| 3 | Contract-based denied-use declarations enforced by the consumer, with attestation | Reuses live `may_not_use_for` semantics and places a red gate at the actual use point. | Self-attestation or voluntary evidence makes prohibited use plus silence indistinguishable from compliance. | **Selected only with mandatory evidence and reconciliation.** |
| 4 | Provenance-carried machine-checkable restriction | Keeps denials attached through transport and derivation; supports `PV-K04` monotonicity. | Restrictions can be stripped in an uncontrolled copy, and their presence does not prove observance. | **Selected as carrier; never treated as use evidence.** |
| 5 | Request-time purpose binding | Makes the intended use visible before the artifact is disclosed. | A truthful request can be followed by a different use; a false declaration is not detectable from the request. | **Selected as precondition, not proof of compliance.** |
| 6 | Human-in-the-loop | Can supply case facts, reasons, review, and responsibility within a lawful individual procedure. | A human rubber stamp may materially rely on the same prohibited population inference; formal human presence does not reveal semantic contribution. | **Rejected as boundary control; retained only as a downstream safeguard.** |
| 7 | Returning-evidence audit with permissive export | Observes actual imports, uses, protected actions, and reconciliation after the boundary. | Detection occurs after exposure; absent or voluntary reporting is observationally ambiguous; off-ledger use remains invisible. | **Rejected as sole layer; selected as mandatory feedback for use-time-only classes.** |
| 8 | Refusal to export the class | Eliminates unobservable individual application for the refused bytes. | Overbroad refusal destroys legitimate aggregate planning and candidate-band work. | **Selected for individually actionable or composition-unsafe classes only.** |
| 9 | Current state: live `may_not_use_for`, no individual-decision concept or export gate | Carries generic authority denials and projection-only posture. | Cannot name the protected individual-use class, observe material contribution, or reconcile downstream case actions. | **Negative comparator; insufficient.** |

## 3. Selected conjunction

The firewall is the following ordered contract:

```text
allow-listed class
AND export-time non-resolution/non-executability test
AND complete population basis
AND denied-use union preserved
AND named consumer + permitted purpose bound before receipt
AND composition-safe against controlled history
AND consumer-side denied-use gate for every material case contribution
AND mandatory complete returning evidence + reconciliation
OR refuse export
```

The result is deliberately asymmetric:

- aggregate planning artifacts can cross when their individual use is both denied and observable;
- individually actionable artifacts are refused unless a complete, trustworthy use boundary exists;
- absence of evidence is `not_established`, never “no violation”; and
- a human action does not sanitize a prohibited input.

## 4. Current-state walk against the fixtures

| Fixture | Current export observation | Current consumer observation | Current operator-visible result |
|---|---|---|---|
| Population risk rule used for individual eligibility | Generic projection/authority limits may be present, but no individual-eligibility purpose exists. | No named case-use gate or returning evidence contract exists. | No PAO-R4 gate is guaranteed red. |
| Two permitted aggregates joined to identify a person | Each export can appear aggregate-safe in isolation. | No controlled composition transcript for this boundary is established. | Re-identification can remain invisible. |
| Rule-level export with complete parameters | Existing code may classify it as projection-only, not authority. | Nothing tests whether a case system executes it. | “Projection-only” does not expose use. |
| Projection narrows a denied use | `PV-K04` supplies a binding rule, and some bounded projection consumers check required denied sets. | No individual-use vocabulary is present to preserve. | Generic permission amplification may fail; PAO-R4-specific narrowing is unnameable. |
| Individual result reconstructed through compliant queries | Each query may pass its own local checks. | No complete query-family transcript or material-contribution reconciliation exists. | Sequence-level violation can stay silent. |
| Human rubber stamp | No artifact-only test proves how the human used it. | No mandatory counterfactual reliance record exists. | Human presence can be mistaken for safety. |

## 5. Why the selected line is not weaker than legal comparators

Some legal regimes focus on a decision that is solely automated, legally significant, or formally
made by a covered body. PAO-R4 uses the broader **material-contribution** trigger: an artifact enters
the firewall when it changes a protected case action, recommendation, evidence weight, reason, route,
or review intensity, even if a human formally clicks the final button. That broader trigger is not a
compliance claim; it is the engineering choice that prevents a legal threshold from becoming a
technical bypass.

Similarly, notice and explanation after a decision do not cure an undetectable export. Those
safeguards belong inside the case system. PolicyOS's boundary question is prior: whether it can
observe and constrain the use at all.

## 6. Rejection summary

The eliminating property for every rejected stand-alone model is **silent individual use remains
possible**. The architecture accepts no prose-only prohibition, no “anonymized” label without a
model, no purpose declaration without later evidence, no human-presence shortcut, and no audit whose
absence is treated as compliance. Where observability cannot be made complete, export is refused.
