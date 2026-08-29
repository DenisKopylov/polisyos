---
task_id: INT-R3
stage: 2
artifact_role: anchor_and_citation_verification
audit_target: 819a83a88315a90320fdd4b25fcb328b434c77de
status: complete
---

# INT-R3 anchor and citation verification

## Repository anchors

### Exact audited package

The audit read the following eight blobs from commit
`819a83a88315a90320fdd4b25fcb328b434c77de` before creating the audit branch.

| Path | Blob SHA | Read status |
| --- | --- | --- |
| `policy-engine/docs/research/policy-operations/int-r3-authority-ui-comprehension-benchmark.md` | `415ec2a6a49a854b9fbf8dd8dfbde9cfd8f64cc4` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/README.md` | `a21fdf3e9f8373d3f91f888ff334d814c4803391` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/benchmark-specification.md` | `df6b64f620112247ec25976a0df85135eabdb96c` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/contract-coverage.md` | `12578c98b27acefaceb2a6d98a693a0d2dea7b0d` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/external-evidence-ledger.md` | `8c712c326f4a16ba46427402e55d854e7a5c840f` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/finding-register.md` | `b9d3ab864f0a8d2e85b38049c39c48e84dd45a52` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/pattern-pass.md` | `e65b133c08549414d819c6fa2970d51ede0d0912` | complete |
| `policy-engine/docs/research/policy-operations/int-r3/repo-baseline.md` | `713124dcb340512769c96499ebe04a5c161a050f` | complete |

### Checked source coordinates

| Package coordinate or claim | Pinned source readback | Verdict |
| --- | --- | --- |
| `TrustPosturePage.tsx` — `TrustPosturePage` | symbol exists; route loads and validates posture, renders unavailable/available arms and MACHINE download | verified |
| `TrustPosturePage.tsx` — `TrustPostureContent` | no such symbol exists in the complete pinned file | **invalid anchor** |
| `ClaimPostureRegister.tsx` — posture fields | claim id, subject, effective state, limitations, blockers, dates and source bindings are rendered | verified |
| `trust/domain/posture.ts` — strict schemas | owner, evidence, support predicates, dates, source state, blocker codes and closure signal are represented | verified |
| `public/atlas/trust-claim-posture.v1.json` | generated artifact exists at the pin | verified existence; semantic population was not independently regenerated in this audit |
| `TimeSemanticsLabel.tsx` | accepts `cacheAgeLabel`, `freshness`, `payloadAsOf`, `txAt`, `validAt`; renders policy-valid, knowledge-transaction, payload/source/observation and cache-age labels | verified actual contract |
| baseline description of `TimeSemanticsLabel` | claims `createdAt`, `asOf`, `updatedAt`, `validFrom`, `validUntil`, `freshness`, `generic` | **source description refuted** |
| `CycleBoard.tsx` — `CycleBoard`, `CycleBoardRow`, `FactField`, `GapCard` | symbols exist; weakest/missing links, acquisition route/economics, source state/freshness and owner routes are rendered | verified |
| `CaseWorkspacePage.tsx` — `CaseRecordSummary`, `CaseWorkspaceDocument`, `AuthorizedCaseWorkspace` | symbols and the `artifact_missing`, `record_available_authority_abstaining`, `available` arms exist; blocker/limitation/objection/abstention and owner/closure data are rendered | verified |
| `HumanDecisionGate.tsx` | role, rights, evidence exposure, mandate times and action submission machinery exist | verified |
| Atlas master plan — INT-R3/DS6 seam | says INT-R3 content upgrades the behavioral battery and **DS6 owns the instrument** | verified; conflicts with package owner-zero |
| Atlas master plan — DS12 gate | first governed promotion + DS11 + `INT-R7`, `INT-R8`, `INT-R1`, preregistered `INT-R9`; INT-R3 is not named | verified |

The two failed source checks establish `INT-R3-AUD-F001`. They are not line drift: one names an
absent symbol and the other describes a different public component contract.

### Governing-document anchors

| Governing claim | Verification |
| --- | --- |
| stage 2 requires seven named artifacts | verified in pipeline §3.2 |
| audit finding severities must sum to the register total | verified in pipeline §3.2 |
| audit branch should contain the research head it responds to | verified in pipeline §2; current stage-2 delivery instruction deliberately produced a non-containing branch and is recorded as orientation error `O01` |
| set-level zero needs complete pinned enumeration, denominator, executor and controls | verified in pipeline §4 and `W4-K01` |
| standing uses three axes from registered vocabularies | verified in `W4-K05` |
| `gate_standing` is the first-public-signature gate | verified in `W4-K05` |
| prose is not a capability chain | verified in `W4-K06` |

## External evidence anchors

### Survey coverage

The audit had access to all five commissioned surveys:

1. `unknown`, missing, intervals, incomparability and remaining risk budget;
2. time pressure, escalation and deferral;
3. refusal, bypass, override and weakest-link behavior;
4. behavioral benchmark and ground-truth methodology;
5. accessibility, assistive technology and numeracy.

They support the package’s broad evidence map at the levels they declare. In particular, they state
that direct evidence is very thin for explicit epistemic `unknown`, pure set-valued uncertainty,
strict UI incomparability, policy-risk-budget interpretation, quarantine behavior and the
assistive-technology intersection. They also distinguish comprehension/application from actual use,
warn that alert override rates are heterogeneous, and show that accessible atoms do not guarantee an
accessible relation.

### Repository-only resolvability

The committed package does not make those survey claims independently resolvable. Its
`external-evidence-ledger.md` contains sixteen `EXT-*` rows and a list of author/document names, but
it does not provide:

- a stable URL, DOI, report identifier or archival coordinate for every source;
- a claim-to-source key from each `EXT-*` row to specific primary sources;
- page, table, section or result locators;
- the survey documents or a committed bibliography;
- a content digest for the exact source/extract relied upon.

The conversational citation tokens embedded in the supplied surveys are not repository-stable
coordinates. Consequently, an auditor who has only the branch can read the synthesis but cannot
reconstruct which exact source supports which exact transfer. This establishes
`INT-R3-AUD-F003` (`material`).

### Anchor-strength verdicts

| External claim family | Audit strength |
| --- | --- |
| risk/uncertainty format affects objective performance | externally supported; direct PolicyOS magnitude absent |
| missing rendered as zero can be read as zero | direct small experiment; explicit `unknown` transfer remains hypothesis |
| time pressure compresses search and may shift misses | externally supported mechanism; target workflow mapping incomplete |
| overrides are heterogeneous and friction/history matter | externally supported; rates prohibited from transfer |
| weakest-link detection differs from chain aggregation | externally supported in adjacent tasks; PolicyOS deterministic-min transfer incomplete |
| set-valued action truth and retained disagreement | supported procedural adaptation; institution remains unappointed |
| Brier/calibration plus direct high-confidence-wrong cells | supported measurement method |
| accessible atoms can lose relations | supported narrow mechanism; direct refusal/δ/epoch action under AT remains open |
| professional title is not a numeracy/AT proxy | supported narrow rule; target prevalence absent |

## Count and denominator verification

### Stage-1 package populations

The auditor read every member of the following declared sets:

| Set | Complete members | Count |
| --- | --- | ---: |
| package files | eight paths listed above | 8 |
| stage-1 findings | `INT-R3-F001`–`INT-R3-F018` | 18 |
| `accepted_narrow_scope` stage-1 findings | `F004`, `F005`, `F006`, `F007`, `F009`, `F010`, `F015` | 7 |
| red-first predicates | `AUI-R01`–`AUI-R12` | 12 |
| external evidence rows | `EXT-01`–`EXT-16` | 16 |
| mandatory metrics | false action, false pass, missed blocker, unsafe override, time to correct, confidence/correctness | 6 |

The stage-2 orientation’s phrase “F001-F010” and “seven of ten” is therefore false. The correct
fractions are seven `accepted_narrow_scope` rows among eighteen stage-1 findings; the fraction itself
is not analytically useful, because rows have different evidence classes.

### Historic page-a11y counts

The package states that the base count `20/24` and later denominator changes were institutionally
supplied from committed receipts and were not recomputed by the stage-1 researcher. That attribution
is correct. The package does not use the supplied count to settle a zero. The audit therefore records
no defect in the count’s attribution.

### Repository-wide absence claims

No complete tracked-tree walk, executable command, path/file-type denominator or controls accompany:

- “no admitted human comprehension evidence exists”;
- “no canonical behavioral event/result contract exists”;
- “no benchmark owner exists.”

The baseline describes a path-following search seeded by task terms. That is a sample. It cannot
settle a set-level zero. The owner zero is additionally contradicted by the DS6 master-plan entry.
This establishes `INT-R3-AUD-F002` and `INT-R3-AUD-F012`.

## Unresolved anchors

The audit did not independently regenerate the 2.6 MB trust-posture artifact, execute dashboard tests
or enumerate every production importer. Those operations are unnecessary to establish the two source
anchor errors and are outside a Markdown-only stage-2 pass. Claims depending on full generated
population or runtime behavior remain at their package-provided evidence class.

The audit also did not establish a repository-wide absence of an operator panel, signer or ethics
route. Institutional absence is a standing programme statement and an acceptable residual. This audit
does not turn that supplied premise into a newly recomputed zero.

## Verification conclusion

Repository anchoring is **materially incomplete**. Most positive target coordinates are real, but two
mandatory baseline facts are wrong, three repo-wide zeroes lack a complete walk, the DS6 owner seam is
missed and the external evidence chain cannot be reconstructed from committed bytes alone. None of
these defects requires discarding the protocol; all require amendment before the package is used as a
canonical design input.
