# INT-R4 ‖ OPS-R5 — Anchor And Citation Verification

Audited package head: `c3999897b5be2308513846935f1c4fb68157bcb3`

## Verification Method

The audit checked four separate properties:

1. **resolution** — the named file and section exist at the pinned package head;
2. **coordinate accuracy** — the cited range contains the asserted object;
3. **entailment** — the source supports the claim actually made, not merely a nearby fact;
4. **transfer boundary** — repository facts, external empirical results and package synthesis are not
   silently promoted into one another.

For repository paths, verification used fresh GitHub file reads at the full package SHA. For the five
supplied surveys, verification used the full institutionally supplied files available to the audit.
No external filename was treated as repository-resolvable unless it exists in the branch.

## Internal Package Anchors

| Anchor | Resolution | Semantic check | Verdict |
|---|---:|---|---|
| INT front matter → `shared_vocabulary_location: section_4` | yes | `## 4. Result` is the sole SMDV-1 derivation. | `pass` |
| OPS front matter → `int-r4-performative-effect-update-diagnosis.md#4-result` | yes | GitHub slug for `## 4. Result` is `#4-result`. | `pass` |
| OPS §1.1 → INT §4 | yes | OPS imports rather than restates the seven classes. | `pass` |
| OPS §5.1 → INT `#5-counterexamples-and-failure-modes` | yes | INT heading exists and contains O1/O3 audits. | `pass` |
| INT → `int-r4/evidence-register.md` | yes | Relative path resolves from `policy-operations/`. | `pass` |
| OPS → `ops-r5/evidence-register.md` | yes | Relative path resolves. | `pass` |
| INT register top-level deliverable `../int-r4-performative-effect-update-diagnosis.md` | yes | Resolves from `int-r4/`. | `pass` |
| OPS register top-level deliverable `../ops-r5-monitoring-diagnosis-and-adaptation.md` | yes | Resolves from `ops-r5/`. | `pass` |
| OPS references to E/X/V/C, A0–A6, transition charter, capstone | yes | All target sections exist inside OPS document. | `pass` |
| INT references to 24-case corpus and O3 frozen red | yes as prose sections | The sections exist, but no separate fixture artifact exists. | `resolves_but_not_fixture`; linked to `AUD-F07`. |
| OPS references to 20-scenario corpus | yes as prose section | The section exists, but no separate scenario packets/evaluator exist. | `resolves_but_not_fixture`; linked to `AUD-F08`. |

No broken relative Markdown link was found in the four package files.

## Repository Anchors

### Governing and task anchors

| Package coordinate | Verified object | Result |
|---|---|---|
| `AGENTS.md:1-120` | identity, capability-chain discipline, P35/P36, P37/P38, readback and one-lattice constraints | `pass` |
| `policy-engine/CONTRIBUTING.md:1-160` | strict typed APIs, architecture boundaries and test expectations | `pass` |
| `docs/reference/policy-operations-research-pipeline.md:1-220` | seven stages, branch topology, stage-2 seven artifacts, delivery/readback discipline | `pass` |
| `docs/research/policy-operations-and-real-world-runtime-backlog.md:485-492` | INT-R4 task, absorbed OPS-R7, GY/Atlas targets and false greenfield sentence | `pass` |
| same backlog `:527-531` | OPS-R5 task, absorbed OPS-R6 and joint binding requirement | `pass` |
| `wave4-decision-evidence-ratification.md:185-245` | W4-K05 and W4-K06 standing/capability semantics | `pass` |
| GY `:5020-5095` | Phase-6 dependency, O1/O2/O3 text, exact riders and build-new/reuse distinction | `pass` |

The backlog citations entail the package’s scope statements. They do **not** entail that absorbed scope
was discharged; that is an audit conclusion, not an anchor failure.

### S13 attribution anchors

| Package claim | Source coordinate | Observed content | Entailment |
|---|---|---|---|
| Eight typed S13 classes exist. | `post_deploy_accountability.py:43-58` | `DivergenceAttributionClass` contains eight literals. | `pass` |
| Attribution/status are fields. | same file around `DivergenceRecord` | Both are required model fields. | `pass` |
| Learning requires attributed status/owner. | validator around `:260-310` | Validator checks consistency and ownership. | `pass` |
| Implementation failure cannot alone refute theory. | validator around `:280-300` | Independent ref required when theory is marked refuted. | `pass` |
| Canonical fixtures supply class/status. | `tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204` | Each case contains literal `attribution_class` and `attribution_status`. | `pass` |
| Inspected path derives the class. | no cited producer | No derivation function is established by the cited path. | Package does **not** make this claim; narrower absence is sound. |

The package’s orientation correction is therefore exactly supported: adjacent typed attribution exists,
but the cited path validates supplied values rather than deriving joint SMDV movement diagnosis.

### N8 typed-carrier anchors

| Coordinate | Observed content | Package use | Verdict |
|---|---|---|---|
| `generation_cycle.py:416-568` | `ValueGateReceipt`, `ValuePortObservation`, content/version/identification and explicit pending/blocked states | typed comparison inputs and reuse seam | `pass` |
| `core/contracts/value_outer_set.py:1-300` | interval/scenario/unknown representations, point/partial/proxy/blocked identification, uncertainty and strict content | non-scalar carrier claim | `pass` |

The carrier anchors do not establish a post-deployment comparison or diagnosis producer. The package
preserves that boundary.

### DDM and monitoring anchors

| Coordinate | Observed content | Entailment | Verdict |
|---|---|---|---|
| `ddm/integration/events.py:1-232` | shift, degradation, data quality, readiness and root-cause localization are separate typed records | DDM detects/localizes rather than establishing SMDV cause | `pass_bounded` |
| `realized_performance_monitor.py:1-151` | intervals and label-delay p50/p90 | delayed-label fragment | `pass` |
| `data_quality_monitor.py:1-142` | schema/null/type/range/value/freshness checks | measurement-health fragment | `pass` |
| `track_2_2_shift_adapter.py:1-62` | local watch/investigate thresholds | values are local routing, not universal policy thresholds | `pass` |
| `calibration/multiple_testing.py:1-89` | multiplicity/FDR machinery | signal calibration, not causal diagnosis | `pass` |
| `runtime/quality/ddm_monitoring.py:1-287` | implementation, monitoring, evaluation, DDM groups and publication ordering | reusable monitoring/evaluation bridge | `pass` |

The phrase “does not establish cause” is a semantic inference from the event contracts and explicit
module separation. It is entitled for the named owner; it is not a census-backed claim that no caller
could ever misuse the records.

### Continuous-governance anchors

`scientist/governance/continuous/monitors.py:1-113` contains:

- source/calibration/fairness/context/incident event types;
- monitor/stale/human-review/reissue/withdrawal-review recommendations;
- public validity statuses;
- a validator that prevents a monitor recommendation from directly withdrawing an artifact.

This supports the package’s “bounded lifecycle primitives exist” claim and its “no action authority
follows automatically” qualification. Verdict: `pass`.

### World and Fabric anchors

| Coordinate | Observed content | Entailment | Verdict |
|---|---|---|---|
| `world_model_record.py:58-68,185-239` | `BranchMode.DEPLOYMENT_UPDATE`; `DeploymentUpdateRefs` explicitly says it declares forward refs without performing update; `WorldModelRecord` is a bridge, not store | forward hook, not executor | `pass` |
| `docs/reference/fabric/time-travel.md:1-111` | snapshots, branches, bitemporal reads, append-only assertion/correction/revocation and governed merges | append-only destination/replay substrate | `pass` |
| `fabric/data_plane/quarantine.py:1-106,220-463` | CAS-backed dead-letter record, retry policy, deterministic reprocessing and lineage | generic quarantine is reusable but reprocessable | `pass` |

The package correctly refuses to infer causal ancestry or O3 permanent semantics from these storage
features.

### Architecture anchors

The identity/custody decision, target architecture, operating model, honest-diagnostics substrate,
north star, Atlas plan and distillation ledger were used chiefly for custody and owner routing. The
package’s owner conclusions are consistent with them:

- learning validity is PolicyOS core;
- field data and institutional decisions enter as integrate-evidence;
- GY consumes/adopts the research gates;
- Fabric owns storage/history, not causal admission;
- Atlas projects state and cannot mint authority;
- Group-B durable mechanics route toward H2 rather than an expanded GY platform.

No citation was found that appoints the missing institutional signer or creates the claimed joint
capability.

## External Survey Anchors

### Source-identity limitation

The registers name files such as `deep-research-report-287(2).md` through
`deep-research-report-291(2).md`. These files are not committed in the audited branch. They were
institutionally supplied to the researcher and audit. Their substantive text and line ranges are
available, but a filename alone is not a durable repository anchor.

This does not invalidate the package because it explicitly labels them `institutionally_supplied` and
never promotes them to repository authority. It does create consolidation cost: a future durable
package should record a content hash or stable external-source artifact ID. This supports the minor
traceability finding `AUD-F11` rather than a new finding.

### S1 — Identification when policy changes its evidence

| Package use | Cited range | Verified support | Verdict |
|---|---|---|---|
| observed movement decomposes into outcome/measurement/selection/behavior | `5-33`, `70-122` | explicit `Y_obs=g(Y*,M,S,R,A)` and domain examples | `pass` |
| independent sensors/holdouts/controls and their assumptions | `35-68` | method table and limits | `pass` |
| self-confirming observation loop | `124-226` | Michigan, policing, credit, coding and series-break cases | `pass` |
| no identification without independent source or structural restriction | `256-268` | explicit nonidentification conclusion | `pass` |
| an exact SMDV precedence order | no S1 result | S1 supports gates/distinctions, not the full order | `unsupported_transfer`; `AUD-F04` |

### S2 — Graded response, stopping and reversibility

| Package use | Cited range | Verified support | Verdict |
|---|---|---|---|
| no universal mature linear ladder | `5-82` | domains govern different risks/objects | `pass`; supports `refuted` |
| reversibility is control/state/outcome/inference | `139-190` | explicit four-part vector | `pass` |
| versions, dynamic rules, carryover, interference, promotion | `214-301` | four estimands, SMART limits, version protocol and no inheritance | `pass` |
| E/X/V/C factored model | `303-377` | explicit four axes and examples | `pass_as_synthesis` |
| E/X/V/C operational orthogonality | same | source calls them orthogonal but gives no reachability/invariant proof | `not_established`; `AUD-F06` |
| endogenous adaptation remains unresolved | `381-395` | explicit open problem | `pass`; package under-discharges it |

### S3 — Why a number moved

| Package use | Cited range | Verified support | Verdict |
|---|---|---|---|
| no universal cause vocabulary; domains preserve key distinctions | `5-41`, `43-130` | explicit cross-domain comparison | `pass` |
| detector is not cause | `43-79`, `183-287` | SPC, SRE and experimentation distinctions | `pass` |
| unresolved/multi-causal residue is normal | `89-112`, `132-181` | WHO-UMC, epidemiology and reliability evidence | `pass` |
| protective action may precede causal diagnosis | `5-13`, `81-130`, `183-227` | clinical/SRE contrasts | `pass` |
| one primary class plus contributors has validated reliability | no | six of seven fields lack inter-rater reliability; multi-label regimes common | `not_established`; `AUD-F03/AUD-F04` |
| observation must globally outrank behavior | no universal result | Microsoft example shows behavior can create outcome and observation paths together | `unsupported_transfer`; `AUD-F04` |

### S4 — Metric as governed contract

| Package use | Cited range | Verified support | Verdict |
|---|---|---|---|
| metric contract is a synthesis, not one standard | `5-64` | explicit | `pass` |
| target/gaming mechanisms and decision rights | `67-190`, `248-365` | documented cases and governance patterns | `pass` |
| objective/guardrail/diagnostic/data-quality non-compensability | `195-243` | explicit role logic and composite-score consequence | `pass` |
| threshold can open review rather than decide result | `223-243` | EEOC example and response-semantics distinction | `pass` |
| exact KPIControlContract field set is an established standard | no | source calls it synthesis | Package correctly labels candidate/synthesis. |

### S5 — Delayed, unreported, subgroup and spillover harm

| Package use | Cited range | Verified support | Verdict |
|---|---|---|---|
| no signal does not imply no harm | `5-19`, `21-131` | passive/active channels, latency, censoring and zero-inclusion limits | `pass` |
| subgroup, spillover and external population must be separate | `179-251` | direct/indirect estimands and sentinel validity | `pass` |
| unknown capture/latency must remain unquantified | `253-301` | explicit limits and honest data states | `pass` |
| a universal horizon/detection rate can be selected | no | source expressly rejects transfer | Package correctly leaves thresholds open. |

## Citation Entailment

### Entailed load-bearing citations

The following high-impact package conclusions are supported at the cited scope:

- S13 is adjacent but not the required evidence-derived producer;
- policy-dependent observation destroys naive causal interpretation;
- detector output is not cause;
- independent/sentinel/negative-control evidence has explicit assumptions;
- delayed/censored/no-channel harm blocks positive closure;
- version identity, exposure and interference are causal conditions;
- one universal response ladder is refuted;
- non-compensable metric roles and transition charters are defensible;
- Fabric can preserve history but cannot decide admission;
- no institutional signer is appointed by research.

### Citations that support less than the package claims

| Package claim | Adjacent evidence | Missing entailment |
|---|---|---|
| Full 0–6 precedence | observation-first prior art | relative order and primary-winner semantics for version/context/behavior |
| Useful realistic class coverage | conceptual cross-domain distinctions | domain holdout, coverage and reliability |
| E/X/V/C orthogonality | examples of different combinations | legal-state product and independence proof |
| O1 non-contradiction | Bayesian routine assimilation intuition | plan text amendment and closed-loop safety |
| Fixed corpora | case families/counts | concrete packets, oracle and evaluator |
| `contract_only` research proposals | detailed Markdown contracts | admitted repository type required by W4-K06 |
| Sole vocabulary necessity | need for coherent semantics | proof that a total tested crosswalk is insufficient |

## Broken, Ambiguous, Or Unverified Anchors

### Broken anchors

None found among package-internal Markdown links or named repository paths.

### Ambiguous anchors

1. External survey filenames are not branch-resolvable and have duplicate `(1)`/`(2)` naming in the
   supplied environment. Substantive text matches the cited ranges, but durable source identity needs a
   content hash or stored artifact ID.
2. Some broad repository ranges combine several claims. The finding registers should backlink each row
   to narrower evidence IDs rather than force reconstruction.
3. `W4-K02` is correctly used for predicate-provenance labels in OPS §7.3. It should not be confused
   with W4-K05 research standings or W4-K06 capability labels.
4. “Fixed” and “frozen” resolve to prose requirements, not committed fixtures. The words overstate
   artifact maturity even though their sections exist.

### Unverified due to declared boundary

- complete repository-wide token census;
- production prevalence or reliability of SMDV-1 classes;
- concrete institutional authority appointments;
- terminal Git receipt after DNS failure.

The package declares all four limits. They are not silently filled by this audit.

## Verification Conclusions

```yaml
internal_links_broken: 0
repository_paths_materially_wrong: 0
load_bearing_repo_claims_overstated: 0
external_ranges_materially_mismatched: 0
unsupported_design_transfers: 7
external_source_identity_durable_in_repo: false
fixture_sections_resolve: true
fixture_artifacts_exist: false
```

The package’s citation mechanics are substantially sound. Its defects arise after citation: it grants
some cited patterns more design authority than they carry. That distinction matters. Correcting the
formal transfers does not require replacing the external research or repository baseline.
