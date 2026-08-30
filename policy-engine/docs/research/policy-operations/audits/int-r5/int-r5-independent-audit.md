---
title: "INT-R5 — stage 2 independent audit"
audit_id: INT-R5-AUDIT
status: delivered_independent_audit
verdict: GO_WITH_REVISIONS
package_branch: research/int-r5-research
package_head: 02e203de90d51280d569e7f641a158569ae4df39
package_base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
audit_branch: research/int-r5-independent-audit
research_standing_reviewed: accepted_narrow_scope
capability_standing_reviewed: absent/unallocated
gate_standing_reviewed: NO_GO
finding_total: 18
blocking: 0
material: 7
minor: 2
commendation: 9
---

# INT-R5 Independent Audit

## 1. Audit Scope And Pin

This audit is hostile to the stage-1 package and independent of its authorship. It audits the five
package files at exact head `02e203de90d51280d569e7f641a158569ae4df39` against repository base
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`, the stage-1 orientation, the pipeline contract, W4-K05,
the five supplied surveys and the executable repository surfaces needed to test the package's
claims.

The five package files were read in full before the first audit artifact was created:

1. `docs/research/policy-operations/int-r5-decision-authority-validity.md` — 833 lines;
2. `docs/research/policy-operations/int-r5/decision-authority-specification.md` — 605 lines;
3. `docs/research/policy-operations/int-r5/external-evidence-ledger.md` — 448 lines;
4. `docs/research/policy-operations/int-r5/adversarial-fixtures.md` — 443 lines;
5. `docs/research/policy-operations/int-r5/repository-baseline.md` — 231 lines.

The audit did not modify any package, source, workflow, `AGENTS.md`, pattern-register or decision
file. It produced only the seven Markdown artifacts required by pipeline §3.2.

## 2. Step 0 And Branch Containment

### 2.1 Observed branch creation

The GitHub repository ref for `research/int-r5-research` was resolved to the full package head
`02e203de90d51280d569e7f641a158569ae4df39`. The audit branch was created from that exact SHA.
Before any audit file existed, a GitHub compare of package head to audit branch returned:

```text
status: identical
ahead_by: 0
behind_by: 0
merge_base: 02e203de90d51280d569e7f641a158569ae4df39
```

This is the connector-observed equivalent of:

```text
git merge-base --is-ancestor 02e203de9 research/int-r5-independent-audit; echo $?
0
```

The containment condition passed before writing. The audit branch therefore contains all five package
files and every package commit it cites.

### 2.2 Headings-only delivery

The seven required audit files were then created as seven successive commits, headings only, before
substantive audit writing:

| Artifact | Skeleton commit |
|---|---|
| `int-r5-independent-audit.md` | `5b6506eca45dd38ddbe78abd5d5bd5b1abb278c0` |
| `int-r5-formal-argument-audit.md` | `aab84073115c78ca7f85cd6dff9da4b1fc1c54d5` |
| `int-r5-claim-evidence-ledger.md` | `e2ad5542cdc9c61ef5b9f8e989065d8e7fce6d4f` |
| `int-r5-anchor-and-citation-verification.md` | `590ef05305a6954b6e807123bc613e28592d9c95` |
| `int-r5-seam-and-crosscheck.md` | `671f0413e5d55516dd6f49855d8eb85e59a5bb75` |
| `int-r5-orientation-error-ledger.md` | `9b1f1336665da41fdc176e30edd3fdb5e27ef9af` |
| `int-r5-recommended-revision.md` | `698dd040f126f92f38d3620128dc989ce99f9594` |

After the seventh skeleton, compare reported `ahead_by: 7`, `behind_by: 0`, the package head as exact
merge base, and exactly the seven audit paths as additions. Final verification found that an earlier
version of this table had recorded incorrect SHA values; this metadata-only correction records the
actual GitHub commit history and changes no package finding or verdict.

## 3. Verdict

**`GO_WITH_REVISIONS`.**

The package contains a valuable and mostly well-bounded target architecture. Its principal design
moves — exact decision/effect commitment, graph reduction, jurisdiction profiles, item-level quorum,
transaction-level separation, bounded conflict claims, mutable-dependency revalidation and immutable
historical replay — survive hostile review.

The package cannot receive `GO` because seven material defects remain:

- a non-theorem is labelled a theorem and written with a false universal inequality;
- the acquisition flow is represented as a landed PA2/DS9/DS20 composition when the production
  `ingest_data` path contains only DS20 permission/resource/step-up enforcement;
- the claimed ten-file complete executable denominator is not an executable or authority closure;
- several decisive certificate coordinates have no independent producer;
- the transferred external evidence is not traceable from the branch to exact survey evidence;
- bare candidate refusal codes duplicate live semantics without namespace or mapping;
- the positive effect handoff does not conjunctively invoke PAO-R4 for individual-case use.

None is structurally unrepairable. They require revision of claims, denominators, producer bindings,
vocabulary mapping and handoff conditions, not abandonment of the graph/certificate model. The audit
therefore does not reach `NO_GO`.

This audit verdict does not alter the package's separate W4-K05 axes. After audit they remain:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

## 4. Finding Register

| ID | Severity | Finding | Evidence and consequence | Recommended revision |
|---|---|---|---|---|
| `INT-R5-A-001` | **material** | The “information-limit theorem” is misquantified. `authority_at_check(t0) != authority_at_use(t1)` asserts actual inequality, while the defensible result is non-inferability or possible divergence under mutable state. | `int-r5-decision-authority-validity.md` §4.2; supplied pre-action survey. Equal state at both times is an immediate counterexample. The downstream need for snapshot, lease or revalidation still follows after correction. | Replace the equation with a quantified indistinguishability/non-inferability claim and call it a lemma or information-limit proposition unless a formal theorem is supplied. |
| `INT-R5-A-002` | **material** | The package falsely describes acquisition approval as a landed DS20 + GY-PA2 + DS9 composition. | At the pin, `routes/control.py::ingest_data` declares only `_INGEST_DATA_AUTHZ` and `_INGEST_DATA_STEP_UP`; `ControlPlaneService.run_data_ingestion` directly executes Fabric ingestion. No PA2/DS9 gate, human-decision record or guarded decision store occurs on that route. | Reclassify acquisition as a DS20-only protected operation plus an adjacent, reusable PA2/DS9 seam. Name the missing bridge and consumer instead of calling the composition sound. |
| `INT-R5-A-003` | **material** | The ten-file “canonical executable denominator” is not a complete executable, producer or authority closure. | Direct imports from `agent_action_authority.py` and `mandate_bounded_delegation.py` reach omitted security, authority, reconciliation, event-log, candidate-firewall, idempotency and artifact-writing owners. The route/service closure also omits `approval.py`, `routes/human_decisions.py` and `services/control/run_lifecycle.py`. Therefore six `not representable` zeroes are plausible but not established by the claimed denominator. | Derive and publish an AST/import plus call/route closure, partition it by producer, bridge, consumer and projection, and rerun every absence claim against that denominator. |
| `INT-R5-A-004` | **material** | “Every decisive certificate field has a producer distinct from the requester” is not satisfied. | The producer table does not name an authoritative producer for `decision_time`, `requested_effect_time`, `effect_class`, profile selection or the semantic source of several commitment fields. A canonicalizer preserves integrity but cannot turn caller-selected time or effect semantics into independently established facts. | Add server/event-time, effect-classification and profile-selection owners; state which caller fields remain candidate-only and how they are reconciled before becoming decisive. |
| `INT-R5-A-005` | **material** | The external-evidence transfer is not independently replayable from the branch. | `external-evidence-ledger.md` names surveys, regimes, statutes and cases but carries no committed survey refs, stable URLs, bibliographic ledger, source digests, page/line anchors or citation IDs. A reader can see the synthesis but cannot verify which exact supplied passage warrants a transferred rule. | Add a source manifest for all five surveys with immutable identity and claim-to-source anchors; preserve source class and jurisdiction per claim. |
| `INT-R5-A-006` | **material** | The package avoids a second global result lattice but creates an unmapped, bare refusal vocabulary that duplicates live semantics. | The local union is explicitly provisional, which is sound. But fixtures and §15 use stable-looking tokens such as `CERTIFICATE_STALE` and `REVALIDATION_REQUIRED` while the repository already uses namespaced/versioned family codes such as `polisyos.eval_safety.certificate_stale@1.0.0`. No crosswalk or namespace prevents collision. | Keep a family-native local payload, but namespace/version every reason or mark it non-binding; define the projection crosswalk before fixtures treat codes as oracle values. |
| `INT-R5-A-007` | **material** | PAO-R4 is respected as an anti-role boundary but omitted as an executable conjunct in the individual-case effect path. | `EffectAuthority`, the operator workflow and the OPS-R15 linkage proceed from certificate/DS9 revalidation to DS20 effect. `may_not_use_for: individual-case authorization under PAO-R4` is a restriction, not an enforcement step. | Add a conditional `PAO-R4` crossing-gate receipt to the effect predicate and handoff whenever the effect is individual-case or pointwise recoverable. |
| `INT-R5-A-008` | **minor** | Post-hoc cure preserves history correctly but does not require an explicit relation-back legal-effect coordinate. | The fixture properly refuses to rewrite the original pre-action certificate and profiles cure as permitted, forbidden or unresolved. Some regimes nevertheless deem later ratification effective from an earlier point. The generic claim envelope can represent `legally_effective_from`, but the cure fixture does not require it. | Require every cure profile/result to state prospective, relation-back, saved-act or unresolved temporal legal effect while leaving the historical certificate immutable. |
| `INT-R5-A-009` | **minor** | The stage-1 orientation and repository finding `INT-R5-RF-01` overstate the ordering violation as three closures. | The backlog says INT-R5 must land before GY-PA2 or Atlas DS9/DS14 close; DS20 vocabulary and acquisition are “feeds”. At the pin, GY-PA2 and DS9 had closed and DS14 had not. DS20 is a missed feed, not the third closure condition written in the task row. | Report two explicit closure-order violations plus separate downstream-feed drift. Do not combine unlike dependency predicates into one count. |
| `INT-R5-A-C01` | **commendation** | Delivery and branch reporting were honest. | The stage disclosed DNS failure, distinguished connector observations from shell output, and read back the committed branch rather than a staging area. | Retain. |
| `INT-R5-A-C02` | **commendation** | The package names its measurement holder and explicitly rejects search-index zeroes as absence evidence. | This is materially better than predecessor packages and directly applies P35/W4-K01, notwithstanding finding A-003 about the chosen closure. | Retain; apply it to a complete denominator. |
| `INT-R5-A-C03` | **commendation** | The 34/34 Python/Rego permission parity and the historical 33 documentation drift are correctly separated. | Independent recheck agreed exactly. The package found and classified its own documentation drift instead of manufacturing a parity failure. | Retain. |
| `INT-R5-A-C04` | **commendation** | The conflict detectability boundary is correctly bounded. | The graph distinguishes record-established, record-indicated, self-known/off-system and evaluative conflicts; the certificate never claims absence of undisclosed conflict. T7 was not established. | Retain. |
| `INT-R5-A-C05` | **commendation** | Collegial validity is jurisdiction/profile relative rather than a global quorum Boolean. | Wrong forum, `at_vote`, `throughout_meeting` and `presumptive_until_challenged` variants preserve real disagreement. | Retain. |
| `INT-R5-A-C06` | **commendation** | The fixture pack is genuinely red-first in shape. | Each mandatory adversary has a property, Given/When/Then result, near-pass control and mutation family; the extended pack adds replay, stale-state and fault-injection cases. | Retain after vocabulary revision. |
| `INT-R5-A-C07` | **commendation** | Institutional absence is represented as a typed missing-holder result without borrowing a maintainer or disabling candidate demonstrations. | This follows the programme's standing decision and keeps the authority/candidate bands separate. | Retain. |
| `INT-R5-A-C08` | **commendation** | The package does not absorb PAO-R4 or claim that an authority certificate decides an individual case. | The doctrinal boundary is explicit and correct; finding A-007 concerns the missing executable ordering, not anti-role drift. | Retain and add the gate conjunct. |
| `INT-R5-A-C09` | **commendation** | Historical replay and post-effect handling avoid fictional rollback. | Original evidence remains immutable; later revocation stops dependent effects and opens correction/withdrawal/remedy paths rather than rewriting history. | Retain; add relation-back projection per A-008. |

## 5. Severity Arithmetic

The register contains **18 rows**. The count is by table row, not by severity-word occurrence.

```text
blocking      0
material      7
minor         2
commendation  9
----------------
total        18
```

Arithmetic check:

```text
0 + 7 + 2 + 9 = 18
```

The severity distribution therefore closes exactly against the finding register.

## 6. Threat-Model Results

| Threat | Position | Result |
|---|---|---|
| `T1` information-limit theorem | **established** | A-001. The information limit is real; the displayed inequality and theorem label are not earned. Correcting the quantifier leaves downstream architecture intact. |
| `T2` comfortable verdicts | **established for acquisition; not established for the three narrow component cores** | A-002. Direct code inspection found no universal false grant in the declared GY-PA2, DS9 or DS20 cores, but the package did not verify their claimed acquisition composition and called an unwired seam sound. |
| `T3` `partial` as hedge | **not established for the four partial rows; absence half remains under-warranted** | Each partial row names a real implemented fragment. The `expiry and emergency` row is asymmetric but not content-free. The six `not representable` claims fail the denominator warrant under A-003. |
| `T4` ten-file denominator | **established** | A-003. It is a selected subject slice, not the complete executable/authority closure it claims to be. |
| `T5` non-requester producers | **established** | A-004. At least time, effect classification and profile selection lack independent producers. One such field is sufficient to defeat the universal property. |
| `T6` second status lattice | **partly established** | No second global lattice is created: the result union is explicitly local and awaits mapping. A-006 establishes a parallel bare reason-code vocabulary without namespace or crosswalk. |
| `T7` detectability boundary | **not established** | The package stays on the correct side of the boundary and expressly refuses to prove undisclosed/off-system absence. C04. |
| `T8` post-hoc cure universality | **strong universal defect not established; one temporal omission found** | The original certificate is an immutable historical computation, not the law's final view of the act. Profile-dependent new results are correct. A-008 requires explicit relation-back effect. |
| `T9` PAO-R4 boundary | **established at the handoff, not at the conceptual boundary** | The anti-role distinction is respected, but the effect formula and workflow omit the conditional PAO-R4 gate. A-007 and C08. |

## 7. Residual Band

The following were registered and deliberately not pursued as defects:

- no appointed institutional holder, signer, adjudicator or panel;
- `capability_standing: absent/unallocated`;
- jurisdiction-specific quorum, saving, cure, recognition and act-effect mechanisms that the package
  already marks as jurisdiction specific;
- external empirical rates not claimed to transfer;
- open ownership and implementation questions routed to consolidation.

The audit does not demand an institution before the model can represent institutional absence. It
does demand that any future positive be based on a complete denominator, independently produced
decisive coordinates and a real enforcing consumer.

## 8. Hand-Back

The seven artifacts are:

1. this verdict and finding register;
2. `int-r5-formal-argument-audit.md`;
3. `int-r5-claim-evidence-ledger.md`;
4. `int-r5-anchor-and-citation-verification.md`;
5. `int-r5-seam-and-crosscheck.md`;
6. `int-r5-orientation-error-ledger.md`;
7. `int-r5-recommended-revision.md`.

The recommended revision is bounded to the nine defects above. It does not authorize implementation,
change capability standing, appoint an owner, open a gate or rewrite the package from inside the audit.