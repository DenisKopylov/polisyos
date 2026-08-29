# INT-R4 ‖ OPS-R5 — Amendment Conformance Verification

Verified amendment head: `329edb60f77867f914581d380acfccf5882d607d`  
Research head: `c3999897b5be2308513846935f1c4fb68157bcb3`  
Audit head: `ea2eac5575e5b8fb4a5462c068a37bb913076952`  
Base: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`

Verification used fresh GitHub Connector reads at exact SHAs. The user explicitly redirected this round to the connector after ordinary Git transport failed. Connector values are not presented as terminal output; the five required shell receipts remain `not_produced`.

## Verdict Vector

```yaml
verdict: CONFORMS_WITH_GAPS
delivery_and_containment: connector_verified; exact initial ref identity and three merge-base relations observed
disposition_reconciliation: conforms; 18 unique rows = 10 INT + 8 OPS
stage_contract_conformance: gap; 17/18 rows use the §3.3 vocabulary
closure_tests: 4 PASS / 2 FAIL / 6 UNRUNNABLE
finding_closure: 11 closed / 5 partially_closed / 2 not_closed / 0 not_assessable
internal_consistency: gap; GY-O1 interim rule conflicts with the unchanged INT research report
```

The amendment responds to all 18 findings and preserves the three standing axes. It does not achieve the audit's conditional post-revision target of `GO`: two closure tests fail and six cannot run because required package artifacts do not exist.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
prior_audit_verdict: GO_WITH_REVISIONS
```

## Per-Finding Closure

| Finding | Severity | Claimed disposition | Where amendment says the change is | Where change was found | Closed? |
|---|---|---|---|---|---|
| `AUD-F01` | material | `accepted` | `int-r4/amendment-ledger.md:30-57` | Seven OPS-R7 questions receive estimand/admission rules, evidence, failure tests and residue. | `partially_closed` — no question-specific fixture packets or executed benchmark; CT-01 fails. |
| `AUD-F02` | material | `accepted` | `ops-r5/amendment-ledger.md:28-276` | Refresh/recompute/recalibrate; adjust/narrow/reissue; pause/rollback; redesign/terminate are separated with entry, authority, version, claim, exit and divergent cases. | `partially_closed` — operation semantics are discharged as prose contracts, but no operation-level response fixtures exist; CT-01 fails. |
| `AUD-F03` | material | `accepted_with_variation` | `int-r4/amendment-ledger.md:58-153` | Holdout strata, selective-risk measures, class metrics, baselines and anti-degeneracy design are specified. | `partially_closed` — holdout, oracle, evaluator and results remain absent; CT-05 is unrun. |
| `AUD-F04` | material | `accepted` | `int-r4/amendment-ledger.md:154-238` | Five-field shape adopted; peer substantive gates replace global causal precedence; mixed observation/behavior case opens both mandatory lanes. | `closed` at research-contract level; CT-04 passes. |
| `AUD-F05` | material | `routed_pending_principal` | `int-r4/amendment-ledger.md:239-334` | Ledger and INT register impose `expected_variation → no effect-posterior mutation` and isolate an eight-condition request. | `partially_closed` — the unchanged INT report still permits routine assimilation and says there is no contradiction; CT-02 fails. Label also violates §3.3. |
| `AUD-F06` | material | `accepted` | `ops-r5/amendment-ledger.md:277-304` | `amendment-state-invariants.md` defines `StateInvariant`, `AllowedTransition`, three forbidden tuples and the independent-basis reverse case. | `partially_closed` — no state engine or pairwise/three-way mutation suite; CT-06 is unrun. |
| `AUD-F07` | material | `accepted_with_variation` | `int-r4/amendment-ledger.md:335-357` | Gap record defines the packet contract, five independent O3 mutations and positive control. | `not_closed` — zero diagnosis packets, sealed oracles or consumer assertions exist; CT-03/05/07/10 cannot run. |
| `AUD-F08` | material | `accepted_with_variation` | `ops-r5/amendment-ledger.md:305-328` | Gap record defines response packet fields, operation coverage and pairwise falsifiers. | `not_closed` — zero response packets, transition oracles or evaluator exist; CT-08 cannot run. |
| `AUD-F09` | material | `accepted` | `int-r4/amendment-ledger.md:358-408` | Ten capability cells changed to `absent/unallocated`; research-sketch wording moved to a descriptive column. | `closed`; CT-09 passes on 36 capability cells. |
| `AUD-F10` | minor | `accepted` | `int-r4/amendment-ledger.md:409-447` | Representation monopoly narrowed to one governed source semantics or a total, versioned, authority-preserving crosswalk. | `closed` as a semantic rule; no crosswalk artifact exists, so CT-10 remains unrun. |
| `AUD-F11` | minor | `accepted` | `ops-r5/amendment-ledger.md:329-350` | Both registers retain six columns and add evidence refs, kind/transfer, falsifier/resolution and artifact note. | `closed`; a sampled row is traceable without reconstructing the package. |
| `AUD-F12` | commendation | `accepted` | `int-r4/amendment-ledger.md:448-456` | Narrow S13-producer-versus-validator baseline preserved. | `closed`. |
| `AUD-F13` | commendation | `accepted` | `int-r4/amendment-ledger.md:457-464` | P35 census remains `not_established`; no downstream global-zero dependency added. | `closed`. |
| `AUD-F14` | commendation | `accepted` | `int-r4/amendment-ledger.md:465-472` | Connector and terminal provenance remain distinct. | `closed`. |
| `AUD-F15` | commendation | `accepted` | `ops-r5/amendment-ledger.md:351-358` | `OPS-F06` remains `refuted`; no universal linear ladder is reintroduced. | `closed`. |
| `AUD-F16` | commendation | `accepted` | `ops-r5/amendment-ledger.md:359-367` | Both institutional findings remain `blocked` with external appointment/preauthorization as unblocker. | `closed`. |
| `AUD-F17` | commendation | `accepted` | `ops-r5/amendment-ledger.md:368-376` | N8/DDM/monitoring/S13/Fabric/continuous-governance/Atlas owner boundaries remain reuse-first. | `closed`. |
| `AUD-F18` | commendation | `accepted` | `ops-r5/amendment-ledger.md:377-386` | Protection remains separable from learning; SMDV source diagnosis remains distinct from S13 destination accountability. | `closed`. |

Closure arithmetic:

```text
11 closed + 5 partially_closed + 2 not_closed + 0 not_assessable = 18
```

## Stage-Contract Conformance

Pipeline §3.3 states:

> disposition ∈ `accepted` · `accepted_with_variation` · `declined_with_reason`

Seventeen rows conform. `AUD-F05` uses `routed_pending_principal`, which is not in the registered amendment vocabulary. This is a vocabulary deviation. Independently of the label, its substantive response is defensible: the amendment applies the conservative interim rule and clearly separates the unratified request. The absence of a principal ruling is not a package defect.

Branch topology conforms by connector observation: the verification branch initially resolved exactly to the amendment SHA; amendment compares ahead of audit with audit as merge base; audit contains research; research contains base. Disposition reconciliation conforms: 18 unique audit IDs, 18 disposition rows, and the claimed 10/8 split and token counts reproduce.

## Internal Consistency Finding

At amendment head, `int-r4-performative-effect-update-diagnosis.md` still states in §4.3 and §4.8 that `expected_variation` may enter a separately predeclared routine likelihood/calibration schedule; §5.1 calls this a scope clarification and says it does not contradict the rider. The appended amendment ledger and amended evidence register state the opposite interim rule.

This is not resolved by selecting the newer artifact: CT-02 expressly asks whether the package as a whole still gives both answers. It does. The unchanged report blob therefore matters materially for `AUD-F05`. For the other findings, an explicit append-only ledger supersession can validly narrow a historical statement; the verification does not treat unchanged research blobs as a generic failure.

## Gaps Under This Verdict

1. `AUD-F01` and `AUD-F02`: absorbed arguments improved, but required fixtures are absent.
2. `AUD-F03`: evaluation design exists, but no sealed holdout/oracle/results exist.
3. `AUD-F05`: package-wide GY-O1 inconsistency and one unregistered disposition token.
4. `AUD-F06`: invariant specification exists, but no engine or mutations exist.
5. `AUD-F07` and `AUD-F08`: both claimed corpora remain future specifications, not delivered fixtures.
6. `CT-10`: no versioned total crosswalk artifact or fixture population against which to establish totality.

## Matters Correctly Left Open

No defect is assigned for the absent institutional signer/adjudicator, `capability_standing: absent/unallocated`, `gate_standing: NO_GO`, the P35 census remaining `not_established`, connector-labelled delivery evidence, absent universal thresholds/horizons/rates, open classifier prevalence/reliability, or the absence of action/world-write/publication authority. Those are the audit's declared residual band, not excuses for the artifact gaps above.
