# INT-R5 Claim-Evidence Ledger

## 1. Method And Claim Classes

This ledger evaluates load-bearing claims rather than sentence count. Each row records:

- the package claim;
- claim class;
- evidence actually inspected;
- evidence holder relative to this audit;
- audit disposition;
- any resulting finding.

Claim classes are:

```text
repository_fact
repository_absence
formal_claim
comparative_legal_synthesis
control_or_engineering_inference
boundary_or_capability_claim
```

Evidence-holder labels follow W4-K02:

```text
recomputed
independently_reconciled
consumer_asserted
institutionally_supplied
not_established
```

For repository facts, this audit used exact code and document bytes at the pin. For the five external
surveys, the survey content was supplied to the audit and read as evidence, but the package branch
itself does not preserve stable identities or claim anchors for those inputs. That distinction is
recorded rather than hidden.

## 2. Repository Claims

| Claim ID | Package claim | Evidence inspected | Holder | Audit disposition | Finding |
|---|---|---|---|---|---|
| `CL-R01` | GY-PA2 evaluates five operational predicates. | `runtime/quality/agent_action_authority.py`; strict delegation contracts; currentness logic. | `recomputed` | **supported in declared scope** | — |
| `CL-R02` | GY-PA2 binds operation, subject, tenant, resource, time and active/revoked state. | PA2 decision construction and accountability checks. | `recomputed` | **supported** | — |
| `CL-R03` | GY-PA2 represents complete institutional authority. | Same code. | `recomputed` | Package explicitly denies this stronger claim. | commendation |
| `CL-R04` | DS9 separates human actor from PolicyOS custody signer. | `services/human_decision_contracts.py`, `services/human_decisions.py`, `routes/human_decisions.py`. | `recomputed` | **supported** | — |
| `CL-R05` | DS9 uses a strict PA2/production source union and re-resolves current inputs. | DS9 contracts/service/route. | `recomputed` | **supported** | — |
| `CL-R06` | DS9 provides narrow reviewer separation. | `ReviewerSeparationCredential` and source resolution. | `recomputed` | **supported, narrow** | — |
| `CL-R07` | DS20 binds verified principal, exact permission, operation, resource and step-up. | `authorization.py`, `resource_binding.py`, `step_up.py`, `permissions.py`, Rego mirror, route declarations. | `recomputed` | **supported** | — |
| `CL-R08` | Python/Rego permission vocabularies each contain 34 equal values. | Exact enum and Rego vocabulary at the pin. | `independently_reconciled` | **supported exactly** | `INT-R5-A-C03` |
| `CL-R09` | Historical 33 is documentation drift caused by later human-decision permission. | DS20 closure record plus current enum/Rego and `runs.human_decisions.create`. | `independently_reconciled` | **supported** | `INT-R5-A-C03` |
| `CL-R10` | `ingest_data` is protected by `EVIDENCE_ACQUIRE`, acquisition resource binding and acquisition step-up. | `routes/control.py::_INGEST_DATA_AUTHZ`, `_INGEST_DATA_STEP_UP`, `ingest_data`. | `recomputed` | **supported** | — |
| `CL-R11` | The same acquisition effect consumes PA2 and DS9 currentness/guarded decision persistence. | `routes/control.py::ingest_data`; `ControlPlaneService.run_data_ingestion`; DS9 route/service. | `recomputed` | **refuted** — the paths are separate. | `INT-R5-A-002` |
| `CL-R12` | Ten files form the complete canonical executable owner closure. | Direct import and route/call closure from PA2, DS9, DS20 and acquisition. | `recomputed` | **refuted** | `INT-R5-A-003` |
| `CL-R13` | No quorum/co-signature semantic exists in the ten selected files. | Complete read of those ten files. | `recomputed` | **supported for selected slice only** | A-003 prevents repository-wide inference. |
| `CL-R14` | No COI/recusal semantic exists in the ten selected files. | Same. | `recomputed` | **supported for selected slice only** | A-003 prevents repository-wide inference. |
| `CL-R15` | No acting/succession semantic exists in the ten selected files. | Same. | `recomputed` | **supported for selected slice only** | A-003 prevents repository-wide inference. |
| `CL-R16` | No parent-grant/subdelegation semantic exists in the ten selected files. | Same. | `recomputed` | **supported for selected slice only** | A-003 prevents repository-wide inference. |
| `CL-R17` | No cross-agency acceptance semantic exists in the ten selected files. | Same. | `recomputed` | **supported for selected slice only** | A-003 prevents repository-wide inference. |
| `CL-R18` | No act-effect distinction exists in the ten selected files. | Same. | `recomputed` | **supported for selected slice only** | A-003 prevents repository-wide inference. |
| `CL-R19` | Full graph/certificate capability is absent/unallocated. | No admitted graph contract, producer, consumer, bridge or e2e chain; package itself research-only. | `recomputed` against named package and inspected runtime surfaces | **supported** | `INT-R5-A-C07` |
| `CL-R20` | DS9 is the closest reusable future pre-effect certificate consumer. | DS9 raw-source re-resolution, currentness and guarded persistence. | `recomputed` | **supported as placement inference**, not current composition. | — |
| `CL-R21` | DS14 remains a future projection consumer. | No DS14 slice artifact in the active `atlas-slices` folder at the pin; main plan treats it as future. | `recomputed` | **supported as unimplemented routing** | — |

### 2.1 Absence-claim correction

Rows `CL-R13`–`CL-R18` are the precise P35 issue. The audit does not find the missing semantics in the
selected ten files. It finds that the package changed the denominator label from “selected strict
chain” to “complete executable owner closure” without deriving a complete closure.

The correct post-audit state is therefore:

```text
absence in selected ten-file slice: established
absence in complete production/authority closure: not established
```

The package may recover the stronger claim only through a complete, reproducible closure walk with
positive controls.

## 3. External-Practice Claims

### 3.1 Survey evidence available to this audit

The audit read five supplied survey reports:

| Survey | Principal package use | Audit view of survey support |
|---|---|---|
| delegation/acting/subdelegation/revocation/cure | authority edge types, attenuation, amount, succession, emergency, cure | strong comparative support with explicit regime differences |
| collegial decision validity | forum, composition, quorum timeline, vote, co-signature, proof record | strong support for profile-relative model; explicitly rejects universal nullity |
| COI/recusal/self-approval | structural SoD, detectability boundary, recusal/waiver | strong support for structural self-approval and bounded conflict claim |
| pre-action authorization/freshness | proof versus receipt, chain reduction, TOCTOU, status and revocation | strong support for non-inferability and three temporal semantics; not for literal inequality |
| cross-agency acceptance/act type | narrow recognition, residual duties, consultation/recommendation/approval/decision | strong support for purpose-limited recognition and consequence-based act classification |

### 3.2 Claim-level transfer audit

| Claim ID | Transferred claim | Survey support | Audit disposition |
|---|---|---|---|
| `CL-E01` | `person → role → delegation` is insufficient. | Delegation survey enumerates source power, scope, time, amount, geography, office status, subdelegation, succession and emergency. | **supported** |
| `CL-E02` | Child scope cannot amplify parent scope. | Public-law subdelegation limits plus SPKI/capability attenuation analogy. | **supported as conservative reducer invariant**, not universal legal doctrine. |
| `CL-E03` | Parent must possess subdelegation power at child-creation time. | Australian §34AB and special-statute examples. | **supported with jurisdiction/source qualification** |
| `CL-E04` | Acting, succession, implied authorization and emergency are distinct provenance paths. | Australian, US and UK regimes distinguish source, trigger and consequence. | **supported** |
| `CL-E05` | Amount authority requires valuation and aggregation, not one invoice value. | Public financial-delegation schemes and anti-splitting rules. | **supported as recurring institutional pattern** |
| `CL-E06` | Legal organ/forum is distinct from physical membership. | Delaware, German and UK examples. | **supported** |
| `CL-E07` | Quorum must be item/profile relative and event sourced. | `at_vote`, `throughout`, written-vote and presumptive-continuance regimes. | **supported as engineering inference** |
| `CL-E08` | Self-approval is structural and disclosure does not cure it. | SoD, audit independence and judicial analogues. | **supported for configured incompatible roles** |
| `CL-E09` | No system can prove absence of conflict known only to a person. | COI survey's record/self-known/evaluative partition. | **supported information boundary** |
| `CL-E10` | Cross-agency acceptance is purpose-limited reliance, not blanket trust. | HCCH, eIDAS, NIST and recognition regimes. | **supported synthesis** |
| `CL-E11` | Act type follows legal effect, not title or UI verb. | EU/UK/US examples. | **supported with profile qualification** |
| `CL-E12` | Later cure can be permitted, forbidden or unresolved. | FAR, FVRA, corporate validation and saving-rule examples. | **supported** |
| `CL-E13` | Later cure can never have relation-back effect. | Surveys expressly identify relation-back/retroactive effects in some regimes. | Package does not make this legal claim, but its fixture should require the temporal effect to avoid ambiguity. `INT-R5-A-008`. |

### 3.3 Branch-level source-custody defect

The survey support above was available to this audit because the reports were separately supplied.
The package branch does not identify those exact bytes. Its transfer ledger has no fields equivalent
to:

```yaml
survey_id
content_hash
stable_repository_or_archive_ref
claim_anchor
source_class
jurisdiction
retrieved_or_effective_date
```

The named statutes and cases allow later research, but they do not prove that the package accurately
transferred the commissioned surveys. That is `INT-R5-A-005`.

## 4. Formal And Information-Limit Claims

| Claim ID | Formal claim | Test | Disposition |
|---|---|---|---|
| `CL-F01` | `authority_at_check(t0) != authority_at_use(t1)` for mutable authority. | Construct an unchanged history. | **refuted as universal inequality** — A-001. |
| `CL-F02` | A `t0` certificate alone cannot know a future `t1` revocation event. | Compare two histories identical through `t0` and divergent afterward. | **supported** |
| `CL-F03` | Snapshot, issuer-authorized lease and revalidation/checkpoint are distinct semantics. | Compare their treatment of revocation after start. | **supported taxonomy**, not proof that every regime fits exactly one without profile interpretation. |
| `CL-F04` | Effective child authority is intersection/attenuation along a path. | Attempt a child scope wider than parent. | **supported safety invariant** |
| `CL-F05` | One invalid path need not destroy an independent valid path. | Two independent root-to-actor paths. | **supported** |
| `CL-F06` | Threshold proof must preserve identities and branches, not only count. | Invalidate one used branch after a `k-of-n` result. | **supported** |
| `CL-F07` | A positive certificate cannot be constructed by requester. | Walk every decisive field to its producer. | **refuted as universal property** — time, effect class and profile-selection gaps in A-004. |
| `CL-F08` | Canonicalization makes a requester value independently established. | Compare provenance before and after hashing. | Package does not state this explicitly, but its producer table relies on canonicalization too broadly. **Not sufficient** under A-004. |
| `CL-F09` | Original pre-action refusal must remain immutable after later cure. | Ask whether later evidence existed in the original as-of snapshot. | **supported as custody rule** |
| `CL-F10` | Current legal effect after cure must always be prospective. | Apply a relation-back profile. | Package leaves profile-dependent effect possible, but fixture does not require explicit temporal output. A-008. |

## 5. Capability And Boundary Claims

| Claim ID | Claim | Evidence | Disposition |
|---|---|---|---|
| `CL-B01` | Research, capability and gate standings are independent. | W4-K05 and package frontmatter. | **supported** |
| `CL-B02` | `absent/unallocated` is correct for the complete capability. | Missing admitted contract/owner/producer/consumer/e2e chain. | **supported** |
| `CL-B03` | Institutional absence should not disable candidate demonstrations. | Programme authority/candidate band split and typed negative paths. | **supported** |
| `CL-B04` | PolicyOS owns computation/custody of its certificate, not external office or legal power. | Identity decision mapping and package four-way boundary. | **supported** |
| `CL-B05` | INT-R5 certificate and PAO-R4 gate are non-substitutable. | Package §1.5 and PAO-R4 anti-role boundary. | **supported conceptually** |
| `CL-B06` | The implementation handoff enforces PAO-R4 before an individual-case effect. | `EffectAuthority`, workflow and capstone chain. | **not supported** — A-007. |
| `CL-B07` | Local result union is not a new global lattice. | Specification §14 reserves downstream mapping to DS4/status owner. | **supported** |
| `CL-B08` | Local reason codes cannot collide with existing code families. | Bare candidate codes plus live namespaced certificate-stale blocker. | **not supported** — A-006. |

## 6. Unsupported Or Overstated Claims

The claims requiring revision are exactly:

| Claim | Required change |
|---|---|
| information-limit “theorem” inequality | change to possible divergence/non-inferability |
| landed acquisition composition | change to DS20-only route plus missing PA2/DS9 bridge |
| complete ten-file executable closure | derive complete closure or narrow claim denominator |
| every decisive field has independent producer | add time/effect/profile producers and provenance rules |
| independently auditable five-survey transfer | add immutable survey/source manifest and claim anchors |
| stable local refusal codes | namespace/version and crosswalk before fixture oracle use |
| PAO-R4 respected by effect handoff | add conditional PAO-R4 receipt as enforcing conjunct |
| three identical ordering violations | split two closure-order violations from DS20/acquisition feed drift |
| cure temporal effect fully represented | require relation-back/prospective/saved/unresolved output |

No evidence was found that requires changing:

- the package's `absent/unallocated` capability standing;
- its bounded conflict claim;
- its jurisdiction-profiled quorum model;
- the distinction between historical certificate and later cure event;
- the separation of authority competence from PAO-R4 individual-use admissibility;
- the narrow PA2, DS9 and DS20 component descriptions, except for their claimed acquisition wiring.

## 7. Conclusion

The package's strongest external and formal claims are mostly supportable. Its weakest evidence is
not legal doctrine but repository composition and evidence custody:

- one route was described as a composition it does not execute;
- one selected slice was called the complete closure;
- one independent-producer rule stops at canonicalization;
- one evidence ledger omits the immutable identity of its source evidence.

Those four failures account for most of the material revision. They are also mutually consistent:
the package is strongest when it says what a future model must represent and weakest when it says
what the present repository already composes or completely lacks.
