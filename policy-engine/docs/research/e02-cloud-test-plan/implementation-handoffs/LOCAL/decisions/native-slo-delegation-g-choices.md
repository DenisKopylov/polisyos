# Native SLO delegation: five owner choices, not fifteen renewals

Date: 2026-10-10  
Disposition: G choice pending named owners. The initial source-only investigation made no SLO, registry, alert, runbook, threshold, or release-setting changes. The authorized follow-up below corrects the existing Core tenant-series binding and loads the already-declared Scientist and mTLS rule files. No target, window, expiry, exception disposition, or issuer authority was inferred. No Prometheus server, production scrape, full SOTA gate, or heavy suite was run.

## Decision requested

Rows 32–46 of LOCAL/dx0-native/native-remaining-disposition-68b.md are five decisions mirrored in three registries. Treat each component as one decision and the remaining rows as projections:

| Component | Mirrored rows | Owner choice required |
| --- | --- | --- |
| common | 32, 37, 42 | Is Common a library/dependency boundary whose impact is accounted for at consuming services, or does it own a separately operated service promise? If delegated, which exact dependent objectives and tested failure routes account for it? |
| berl | 33, 38, 45 | Is BERL only Scientist validation support, or an independently operated explanation-reliability service? If delegated, does a BERL failure change an admitted Scientist outcome or only produce a diagnostic result? |
| ddm | 34, 39, 46 | Is DDM an internal evaluation library behind Scientist, or an operational monitoring service? The ddm_15_7 compatibility alias does not answer this. |
| calibration | 35, 40, 44 | Does the SLO component mean generic polisyos.calibration, Foundry parameter calibration, DDM calibration, or a separately operated service? The bundle currently combines these scopes. |
| security | 36, 41, 43 | Is security one operational service, a set of control-specific obligations, or an out-of-scope service whose controls remain governed by release/security gates? A single aggregate security SLO would mix different failure meanings. |

All five ops/components/<component>/slo.yaml files currently have status: exception, exception_expires: 2026-08-01, and objectives: [] (each file lines 1–7). These exceptions are expired on 2026-10-10. The mirrored TOML action due dates are 2026-05-31 and also past. This needs current owner decisions, not date-only renewal.

Three current registry surfaces duplicate these decisions: ops/components/index.toml is owned by team-ops and remains active_draft; architecture/component_observability.toml is report_only under team-observability; architecture/runbook_coverage.toml is report_only under team-ops. The component-first ops organization points toward one decision per component, but its SLO exception owner, reason, expiry, and action are repeated in each mirror.

## What the live source chain establishes

The release consumer checks less than delegated coverage. tools/ops_runners/release/check_operability_release_gates.py:273–320 checks status, exception fields, date/action policy, and status: exception text. Its exception branch does not require an objective or exact delegated SLI. Lines 322–384 check observability metadata and paths. _check_alert_coverage at lines 623–660 resolves alert names and runbook paths; it does not bind an alert expression to an emitted metric or a named SLO objective. tools/devx/workspace/repository_sota_closeout.py:919–963 also checks exception fields and dates rather than coverage semantics. The bundle tests at tests/repo_quality/architecture/test_repository_best_in_class_phase4_9_operability_bundles.py:56–71 assert file/status/metadata shape. tests/repo_quality/tools/test_operability_release_gates.py:61–105 exercise exception metadata and date rules.

This is a concrete P38 divergence: a non-expired exception that satisfies the existing date/action rule can satisfy the metadata branch with no objective or tested coverage relation. The listed expired dates make the SLO exception predicate red today, but changing dates alone would not prove coverage. The five component alerts files and central runbook entries provide human routing; route presence does not establish that a service metric is correct or that a dependent failure reaches it.

### Component-level source and candidate-SLI findings

| Component | Producer and consumer path found | Existing candidate | What remains unproved |
| --- | --- | --- | --- |
| common | src/polisyos/common/README.md describes a shared Python helper facade used by Core, Runtime, Foundry, Scientist, Lex, Scholar, Fabric, and tooling. Runtime uses it in http/services/task_runner.py, http/resilience.py, and http/container.py. No Common-owned request/service producer or alert family is declared: component_observability.toml has no Prometheus rule and ops/components/common/alerts.yml has alerts: []. | Runtime API or Scientist DAG outcomes are existing user-facing SLI candidates. docs/reference/operations/slo-error-budget.md:17–23 says critical execution dependencies affect the owning service promise. | The exception says “dependent component SLOs” without naming an objective. Existing metrics do not bind a failure to Common or prove which Common failures are included. An API error SLI may account for user impact, but it cannot establish Common as the cause. No Common-specific dependency-fault control is linked to an SLI. Source supports “not a standalone service” as the likely package boundary, but not the current blanket coverage claim. |
| berl | src/polisyos/berl/README.md calls BERL active Scientist support. scientist/validation/phase5_preflight.py:1098–1115 calls validate_persisted_explanation_bundle_payload and returns passed, display policy, violations, and warnings. runtime/quality/explanation_reliability.py also consumes BERL. Scientist metrics_otel.py:115–130 records overall workflow status and duration; the SLI is not BERL-tagged. No BERL Prometheus rules or alerts are declared. | Scientist DAG success >=0.95 and p99 duration <300s in ops/components/scientist/slo.yaml:5–16 are candidates if BERL failures fall inside that operational promise. | A rejected explanation bundle can be a quality result rather than a service failure. No linked test shows how BERL outcomes change workflow status or which user promise is affected. Ops names team-architecture as owner, while the canonical package and behavior path name team-scientist. The behavior owner must decide service scope. |
| ddm | src/polisyos/ddm/README.md describes a canonical drift/degradation monitor package. ddm/integration/monitor.py computes DDMWindowResult and readiness/event evidence when invoked. Targeted source search across src/polisyos Python files found a Scientist fairness detector importing DDM event types, but no outside-package construction of DriftAndDegradationMonitor. No ddm-specific Prometheus series is declared in reviewed metric sources or rules, and ddm/alerts.yml is empty. | Scientist DAG SLI is only a candidate if a real monitor result is produced on that path and changes its admitted outcome. | Source classifies the package as internal; ddm_15_7 is a compatibility alias. The monitor is a callable evaluation API, not an observed background service. There is no owner-approved detection window, population, miss/false-positive objective, or source-bound SLI. A Monitor class or readiness DTO is not an SLO. |
| calibration | The component aliases generic polisyos.calibration, polisyos.foundry.calibration, and polisyos.ddm.calibration together (ops/components/index.toml:248–267). The actual Prometheus-producing path found is foundry/calibration/calibrator.py:287–301, which flushes polisyos_calibration_loss and polisyos_calibration_grad_norm; _metrics_registry_base.py:695–716 declares both as gauges. ops/observability/prometheus/alerts.yml:151–174 defines CalibrationDiverging and CalibrationStuck; both map to benchmark triage (architecture/runbook_coverage.toml:490–497). Prometheus config loads these rules (prometheus.yml:5–11). | Foundry SLO has a method-dispatch error objective <1%, but its expression uses polisyos_foundry_method_dispatch_total, which is absent from the reviewed core metric registry and source declaration search. It is not a qualified substitute for calibration. | The two real calibration alerts are diagnostic alerts, not an SLO. CalibrationStuck applies increase() to polisyos_calibration_loss, declared as a GaugeProxy; the metric owner must justify or correct the query before it can be treated as SLI coverage. No calibration SLO objective or linked fault-to-objective consumer test exists. Generic calibration is Scientist-owned, the cited gauges and alerts are Foundry-owned, and DDM calibration is another bounded context. Split the contexts before issuing one service claim. |
| security | Unlike the four library/support scopes, ops/components/security classifies security as operational_control and lists nine alerts. Source-backed examples include runtime cell routing recording polisyos_security_incidents_total (runtime/http/cell_router_middleware.py:247–252; metrics_parts.py:802–806), TEE attempts (core/security/tee_middleware.py:102–139), and SBOM scan counts (core/security/sbom.py:294). Alerts route to CAS/OPA, signing/SBOM, or key-rotation runbooks. At initial review, component_observability.toml and security/alerts.yml declared rules/mtls-rules.yaml, but prometheus.yml omitted it; the follow-up now loads that declared file and Promtool validates both rules. | ops/release/promotion-gates.toml declares security_sbom_provenance and operability_release_supply_chain; these are release-control candidates, not quantitative service SLOs. Core has a tenant-boundary SLI whose metric name was corrected in the follow-up to match the source-emitted series. | At initial review, Core queried polisyos_tenant_boundary_violations_total, which was not emitted; the follow-up corrected both active Core SLO copies to the source-emitted polisyos_audit_tenant_boundary_violations_total. This establishes metric-name alignment, not the owner’s intended population or a live scrape/evaluation. Other declared alerts cover identity, TEE, SBOM and mTLS: distinct control properties that cannot be honestly collapsed into one “security success rate” without a decision on populations, denominators and failure meanings. Release gate declarations are manually reviewed; check_operability_release_gates.py:679–720 validates their IDs/evidence paths but does not compute these SLOs. |

Nearby numeric SLOs are candidates, not automatic coverage: Scientist DAG success >=0.95 and p99 <300s (scientist/slo.yaml:5–16), Foundry simulation NaN <0.001 and cache hit >=0.60 (foundry/slo.yaml:5–22), Core artifact/audit objectives and tenant-boundary objective (core/slo.yaml:5–22), and Runtime API targets (docs/reference/operations/slo-error-budget.md:48–56). None is referenced by these five exceptions as a typed delegation. At initial review, the Core tenant-boundary query and Foundry method-dispatch query had source-divergent metric names. Core's active SLO copies now both bind to `polisyos_audit_tenant_boundary_violations_total`. The source-bound test `tests/repo_quality/architecture/test_repository_best_in_class_phase4_9_operability_bundles.py::test_core_tenant_boundary_sli_names_the_metric_emitted_by_its_native_producer` invokes the native `MetricsRegistry` producer and checks the SLI against an `InMemoryMetricReader` emission. The separate runtime-guard witness `tests/unit/runtime/http/test_runtime_authorization_access_audit.py::test_tenant_boundary_metric_records_only_verified_mismatches` covers authenticated run/artifact mismatches and verifies counter points are emitted only for verified mismatches; the independent focused run reported seven passes. These local emission/guard results do not prove live Prometheus scraping/evaluation or SLO authority. The Foundry query remains source-divergent. Security alert thresholds such as TEE failure >1% and SBOM deny rate >5/hour are alert conditions, not owner-ratified SLO targets. Calibration's >1000 gradient threshold is also an alert condition.

## Exact issuer and authority needed

The registry owner fields are not approval records. docs/reference/ownership.md:22–28 says logical groups are stable owner vocabulary, @DenisKopylov is the current GitHub-enforced reviewer, and @platform-owners is the fallback. Boundary-crossing changes require affected owner groups and platform approval for shared contracts/ops (lines 88–95). The SLO policy is owned by @platform-owners; docs/reference/operations/slo-error-budget.md:111–118 assigns SLI interpretation to Runtime, Scientist, Foundry and Security/Compliance owners with Platform coordination. A team alias or archived issue URL is not an owner decision/signature.

| Component | Scope issuer | Required coordination |
| --- | --- | --- |
| common | team-core / @core-owners | @platform-owners for the shared ops/SLO delegation contract; downstream service owners only for objectives they accept. |
| berl | team-scientist / @scientist-owners | @architecture-owners must reconcile the current team-architecture issuer in the three mirrors; @platform-owners approves the SLO disposition. |
| ddm | team-scientist / @scientist-owners | @architecture-owners resolves alias/package-version boundary and current ops owner; Platform approves the SLO disposition. |
| calibration | Joint team-scientist / @scientist-owners for generic API and DDM scope and team-foundry / @foundry-owners for Foundry emitter/alert scope. | @platform-owners for SLO/ops; neither owner silently absorbs the other contexts. |
| security | team-security / security-compliance owner for control intent | @platform-owners for release/ops and @core-owners for the Core tenant-SLI source correction; include Runtime for any runtime auth/routing objective. |

The decision is not “extend expiry.” Each issuer must choose: (a) standalone service with its user promise; (b) no standalone service with exact dependent objective refs and tested failure-to-objective routes; or (c) library/control-only scope with SLO out_of_scope while named release/runtime controls remain separately accountable. BERL, DDM and calibration also need package-versus-service scope. Security must choose control-specific SLOs or separate release-gate accountability; this packet does not infer one aggregate target.

The owner record should name the actual approving identity, decision/effective time, review trigger, package aliases/version in scope, chosen disposition, exact SLI IDs, runbooks, escalation owner, and residual limits. Distinguish technical issuer from registry projection owner (team-ops/team-observability) and current GitHub reviewer. The reviewer identity alone does not show that any decision has already been made.

## Narrow G alternatives

1. Reuse existing objectives where proven. Preserve current metrics, rules and runbooks. Select exact SLI IDs from Runtime/Scientist/Foundry/Core only after the component owner proves the relevant failure reaches that objective. Strongest candidate paths are Scientist workflow for BERL and an actual DDM-in-Scientist use, Runtime/API and consumer workflow outcomes for Common, existing Foundry calibration diagnostics for calibration, and a corrected Core tenant-control SLI or separate security release controls for Security. Current candidates are not established coverage; the Core mismatch and absent Foundry dispatch series refute two assumptions.
2. Extend the existing bundle contract. Add one typed disposition to the canonical component bundle: standalone_service, delegated_objectives, non_service, or control_only. For delegation, require the current owner decision ref, exact objective ID, producer metric/source, rule/runbook refs, effective/review times and limitations. An empty delegate list cannot pass. Do not invent targets. If no existing objective fits, the service owner must provide the population, numerator/denominator or event count, exclusions, window, target and error-budget response before creating one.
3. Consolidate the mirrors. Use component-first ops/components as the decision surface if team-ops and Platform accept this ownership. Keep architecture/component_observability.toml and architecture/runbook_coverage.toml as compatibility projections with an exact reference/parity check. If they remain separate sources, name each issuer and fail on disagreement. One choice per component must project to all three rows.
4. Build new only if current schema cannot distinguish a non-service package from an unproven delegation or a control-only disposition. Use a small versioned ComponentSloDisposition contract and evaluator bound to existing sources; do not create another metrics system or infer closure from metadata.

### Generic coverage-guard prototype and falsifier

A read-only probe is saved at LOCAL/dx0-native/raw/native-slo-delegation/native-slo-coverage-guard-prototype.json (SHA-256 4c562efd6db8c9083ae8d7c28fde975303581ef132fe3d5af2302c576b4fc9d1). It covers only the five rows and named candidate objectives/metric paths. It is a source probe, not a production validator or owner approval.

One generic guard should admit delegated coverage only when this source-bound tuple resolves:

owner decision + service/control boundary + exact objective ref + current emitted metric/query + rule/evaluator + operator runbook + owner escalation + component-specific positive/negative control

Small falsifiers:

- Make exception_expires future while leaving objectives empty/no typed delegate: metadata may accept its shape, but the guard must refuse.
- Keep alert name and runbook path while removing/renaming the actual series: path checks remain green, but query-to-emitter binding must fail.
- Link a real dependent SLI but inject a component failure that does not affect it: metadata remains green, but the consumer-side control must fail.
- For Security, the existing Core SLI metric name now matches the registry producer. Its intended event/population and live evaluation still need owner confirmation and a producer-to-evaluator control; the binding correction alone is not coverage proof.
- For Calibration, demonstrate an actual stuck/diverging path through its producer/exporter and alert evaluator, after the GaugeProxy/increase() semantics are resolved. An alert name alone is not SLI coverage.
- For Security mTLS, the active config now includes rules/mtls-rules.yaml and Promtool parses both rules. A future coverage guard must still require an actual evaluator/source-path control before treating the alerts as SLI coverage.

The current five remain not_established for delegated SLO coverage, even where parts of an alert→runbook chain exist. A full positive is possible only after issuer decisions and source-bound behavioral controls. Test fixtures do not establish an external production fact.

## Migration and acceptance

1. Obtain the five decisions above, jointly where indicated; write factual unknowns as limitations.
2. Bind exact objective IDs and source emitters for every delegation. Have owners repair source-divergent SLI paths before reusing them. Do not select replacement thresholds here.
3. Add the generic guard and a five-disposition test matrix: proven delegation positive, date-renewal-only negative, metric-source mismatch negative (the current Core/Foundry cases), and component-fault control proving whether the selected consumer SLI changes. Keep Security objectives separated by control family.
4. Project each decision to all three registries and verify all references resolve to the same current decision/evidence. Preserve alert-to-runbook and release/security consumers; they test different properties.
5. Remove an expired exception only when a standalone SLO exists or a typed non-service/delegated disposition is accepted and consumed by the guard. Date renewal alone does not meet the criterion.

## Pattern and capability classification

- P40: same class as the prior exception-metadata-versus-property finding, widened over all 15 mirror rows. The deeper observation is source metric divergence and overlapping service scopes. The repair unit is five dispositions plus one generic guard, not per-row patches.
- P38/P32/P05: current presence/date/name checks are proxies; owner fields and issue URLs do not prove semantic coverage or decision authority.
- P01/P02/P10: exception metadata/artifacts exist and some alert producers exist, but the delegation has no bound objective/bridge/consumer test. The claim is contract_only; component-specific producer/bridge gaps are stated above. verification_missing and semantic_test_missing remain until the behavioral guard is implemented.
- P08/P07: SLO measurement windows are distinct from exception review/expiry dates; effective time and review trigger must be explicit.
- P14: a dependency SLI does not cover every consumer without owner-issued mapping and a tested consumer impact.
- Correct pattern: reuse existing metric/SLO/runbook sources; extend one typed owner decision; consolidate three mirrors; build one generic guard only if existing fields cannot encode the disposition. No numeric target is invented.

## Evidence and limits

Primary source basis: LOCAL/dx0-native/native-remaining-disposition-68b.md rows 32–46; current ops/components/index.toml, architecture/component_observability.toml, architecture/runbook_coverage.toml; the five exception SLOs; named candidate SLOs and metric/rule sources; and the ownership references above. The exception expiries and duplicate rows come from the input; no full native SOTA command was rerun. The raw guard JSON records source hashes and results. No live Prometheus endpoint was queried. Source config shows intended rule loading, not that a production deployment scraped the series or fired an alert.

## 2026-10-10 authorized internal follow-up

This follow-up closes two internal wiring defects that were separable from the
five owner choices:

- `ops/components/core/slo.yaml` and `ops/observability/slo/core.yaml` now name
  the metric actually declared/emitted by the Core audit registry:
  `polisyos_audit_tenant_boundary_violations_total`. The query’s source binding
  is corrected; the tenant-boundary objective and target were not redefined.
- `ops/observability/prometheus/prometheus.yml` now loads the already-declared
  Scientist and mTLS rule files. This follows the full declared
  `component_observability.toml` rule-file set; it does not add wildcard loading
  for unreviewed rules.
- The active config parsed with Prometheus 2.50.0 `promtool`; all eight loaded
  rule files parsed. The exact command/output transcript is preserved at
  `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/s3-empirical/raw/promtool-v2.50.0-e02-2026-10-10.txt`
  with SHA-256
  `2d8ce81903e99c08d1130926fc1f09665a7464efce624f8ba2ce3674dbfc5c1b`.
- The independent producer/consumer question remains for
  `core_audit_sink_success_rate`: its query names
  `polisyos_audit_sink_writes_total{status="success"}`, which is not emitted by
  the current source. A nearby metric is not a valid substitute. The minimum
  owner decision is whether the objective concerns logical acceptance at the
  public return boundary or physical replica durability after asynchronous
  writes/flushes. Until selected, classify this objective as
  `producer_missing`/`not_established`; do not claim closure or invent a target.

The raw Promtool receipt records the pinned tag and digest, dedicated Colima
context, exact argv/cwd, offline volume-copy method, full successful outputs,
container network/rootfs/config-mount flags, and before/after image footprint.
The tool transcript lacked wall-clock timestamps and did not record the Git SHA
or per-file source hashes at execution; this receipt states the checkout HEAD
only at reconstruction. The frozen final wave must validate the copied config
and rules as exact source-bound bytes. The read-only config/rule check proves
syntax and active file loading, not a production scrape, metric availability,
alert firing, authority, or owner acceptance. The five component disposition
choices above therefore remain pending.
