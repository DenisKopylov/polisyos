# Policy Design Case Rollout And Rollback

Related runbooks: [Policy Design Case Operator Triage](policy-design-case-operator-triage.md),
[Production Quality Canary](production-quality-canary.md),
[Cloud Production Debugging](cloud-production-debugging.md),
[Canary Rollback or Failed Promotion](canary-rollback-or-promotion-failure.md),
and [Replay or Restore Workflow](replay-or-restore.md).

Related reference:
[Policy Design Case Operator Guide](../reference/policy-design-case-operator-guide.md),
[Policy Design Case Evidence Paths](../reference/policy-design-case-evidence-paths.md),
[Policy Design Case Capability Ratchet](../reference/policy-design-case-capability-ratchet.md),
[Policy Design Case Structural ADR Registry](../reference/policy-design-case-structural-adr-registry.md),
and [Quality Gates](../reference/quality-gates.md).

Owner: `@platform-owners` with `team-policyos-runtime`,
`team-runtime-quality`, `team-quality-closeout`, producer owners, and
governance reviewers.
Last tested: `2026-05-23` against W5.E docs/runbook regression coverage.
Evidence path: runtime bundle `quality_evidence/*.json`, accepted wave
summaries under `docs/archive/reports/`, and active command output under
`_build/.tmp/policy-design-case/<phase-or-wave>/` until promoted.
Rollback path: stop promotion, disable or downgrade the affected feature flags
and tuned configs, quarantine public/dashboard/API/export projections, preserve
the original bundle and CAS refs, rerun closeout or bundle inspection, and
record the outcome in a closeout note.

Use this runbook when promoting, holding, rolling back, or disabling universal
Policy Design Case public, reviewer, expert, machine, dashboard, export, audit,
semantic-evaluation, calibration, memory, or tuned-config behavior.

Treat any safe-disable path as a kill switch only when it has a named owner,
runtime flag or config value, rollback value, and evidence-preservation step.

## Authority Rules

- Closeout reader output and producer-owned evidence are authority. This
  runbook is a procedure for finding and preserving that authority.
- Dashboard, public export, API, audit package, and docs summaries may project
  evidence but cannot make blocked, limited, contested, missing, or omitted
  evidence appear successful.
- Feature flags and tuned configs need owner, version, evidence, rollback path,
  health telemetry, and cleanup or revalidation condition before promotion.
- Historical calibration and memory influence can change future routing,
  review, uncertainty posture, or authority caps. They cannot close or refute
  current-run claims.
- Typed blockers and accepted deficits are honest safety outcomes. They do not
  count as useful-design capability.

## Preflight Inputs

Record these before running or promoting anything:

| Input | Required value |
| --- | --- |
| Git revision | Exact SHA for the frozen candidate. |
| Scenario set | Corpus or lane names and authority profiles. |
| Feature flags | Names, values, owners, and rollback values. |
| Tuned configs | Names, versions, owners, status, and default source. |
| ADR authority | Relevant ADR ids and structural registry C-rows. |
| Capability report | Path and summary readiness band from `architecture/policy_design_case/capability_reality_report.json`. |
| Evidence output plan | `_build/.tmp/policy-design-case/<phase-or-wave>/` for active logs and `docs/archive/reports/` for accepted summaries. |
| Promotion posture | `research-only`, `governed pilot`, `production-capable`, or `held`. |

## First 15 Minutes Of A Failed Promotion

1. Stop publication, approval, promotion, and dashboard refresh for the
   affected run or lane.
2. Capture run id, job id, tenant, cell, scenario, authority profile, bundle
   path, public export ref, dashboard URL, feature flags, tuned config versions,
   and git revision.
3. Preserve the original bundle, CAS refs, runtime event refs, command output,
   and current closeout verdict.
4. Check whether the failure is a missing evidence path, missing producer,
   projection truth gap, semantic false pass, tuned-config maturity gap,
   rollout command failure, or cloud-lane failure.
5. Route closeout and producer failures through
   `docs/runbooks/policy-design-case-operator-triage.md`.
6. Route canary infrastructure failures through
   `docs/runbooks/canary-rollback-or-promotion-failure.md` or
   `docs/runbooks/cloud-production-debugging.md`.

## Rollout Ladder

Run commands from `policy-engine/` and preserve outputs according to
`docs/reference/policy-design-case-evidence-paths.md`.

### 1. Docs And Operator Surface

```bash
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py \
  tests/repo_quality/tools/test_policy_design_case_documentation_paths.py \
  tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py \
  -q

uv run polisyos-tools workspace tool-configs --check
uv run --extra docs python -m mkdocs build --strict
```

Abort if ADRs, evidence paths, tuned owners, validation ladders, capability
evidence, runbooks, or nav discoverability are missing.

### 2. External Surface Truth

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py -q
uv run pytest tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
```

Abort if public, reviewer, expert, machine, dashboard, API, export, or audit
surfaces hide blockers, omit required omission manifests, or turn missing refs
into apparent success.

### 3. Capability Reality

```bash
uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py \
  --repo-root .
```

Abort or hold if a capability needed for the declared posture still has
`contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`,
`consumer_missing`, `verification_missing`,
`implemented_but_not_orchestrated`, `surface_missing`, or
`semantic_test_missing`.

### 4. Local Validation

Use the implementation plan's W12.A local validation ladder. The canonical
runner preserves the W6.A manifest path for compatibility, then records command
evidence, typed blockers, owners, next actions, closeout-honesty metrics,
useful-design metrics, and W11.E compilation-truthfulness metrics:

```bash
uv run python tools/quality/validation/run_policy_design_case_local_validation_ladder.py \
  --repo-root . \
  --profile full \
  --output _build/.tmp/production-quality/universal_pdc_local_validation_ladder.json
```

For targeted reruns, the underlying command groups are:

```bash
uv run pytest tests/unit/runtime/quality tests/unit/scientist tests/unit/lex tests/unit/fabric tests/unit/foundry -q
uv run pytest tests/repo_quality/tools/test_evidence_bundle_inspection.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
uv run python tools/quality/validation/check_compilation_truthfulness.py --corpus tests/fixtures/universal-corpus --output _build/.tmp/production-quality/compilation_truthfulness_report.json
uv run python tools/quality/validation/check_domain_coverage_breadth.py --corpus tests/fixtures/universal-corpus --output _build/.tmp/production-quality/domain_coverage_breadth_report.json
uv run python tools/quality/validation/check_critic_ensemble_diversity.py --input tests/fixtures/universal-corpus --output _build/.tmp/production-quality/critic_ensemble_diversity_report.json
```

Then run the local production-debug quick path:

```bash
uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py \
  --repo-root . \
  --checks quick,production-data-static,docs-repro \
  --output _build/.tmp/production-quality/universal_pdc_local_quick.json
```

### 4.1 Compilation Truthfulness

Run W12.B before any rollout posture decision. This executes W11.E over the
universal outcome corpus, preserves the raw per-case bucket report, and emits
typed compilation blockers for cases or slices below the declared posture floor.
Those blockers are diagnostic rollout blockers; they do not count as useful
design and they are not closeout-honesty failures.

```bash
uv run python tools/quality/validation/run_compilation_truthfulness_audit.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --rollout-posture governed-pilot \
  --raw-report-output _build/.tmp/production-quality/w12b_compilation_truthfulness_report.json \
  --output _build/.tmp/production-quality/w12b_compilation_truthfulness_audit.json
```

### 4.2 Domain Coverage And Critic Diversity

Run W12.C alongside W12.B before any rollout posture decision. This executes
the W11.F domain breadth and critic diversity tools, preserves both raw reports,
and emits the domain x authority-level useful-design matrix used by the rollout
floor. A committed slice with zero useful-design outcomes is a typed
domain-coverage blocker. A `critic_monoculture` warning does not count as
useful design and caps rollout at governed pilot or below.

```bash
uv run python tools/quality/validation/run_domain_coverage_critic_diversity_audit.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --rollout-posture governed-pilot \
  --raw-domain-report-output _build/.tmp/production-quality/w12c_domain_coverage_breadth_report.json \
  --raw-critic-report-output _build/.tmp/production-quality/w12c_critic_ensemble_diversity_report.json \
  --output _build/.tmp/production-quality/w12c_domain_coverage_critic_diversity_audit.json
```

### 4.3 Universal Outcome Corpus

Run W12.D before rollout posture closeout. This is the canonical real-corpus
evidence command: every W11 outcome case goes through W6 universal compilation,
W7 producer pipeline orchestration, and W8.A RuntimePolicyDesignCase graph
assembly. The output records per-case outcomes, evidence-bound graph artifact
refs, W11.C expert-adjudication deltas, and authority-level metric
stratification. Synthetic fixtures from earlier waves do not substitute.

```bash
uv run python tools/quality/validation/run_universal_outcome_corpus.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --graph-output-dir _build/.tmp/production-quality/w12d-runtime-pdc-graphs \
  --output _build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json
```

### 4.4 Corpus Stub Boundary Check

Use corpus-stub mode only when the real producer environment is intentionally
synthetic or unavailable. The mode uses W11.C-derived fixtures under
`tests/fixtures/universal-corpus/producer_stubs/` to prove the compiler and
producer bridge can produce useful design when admissible evidence is present.
It cannot satisfy production closeout, producer domain truth, claim evidence
authority, or public projection authority.

```bash
uv run python tools/quality/validation/run_universal_outcome_corpus.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --mode corpus_stub \
  --producer-stub-dir tests/fixtures/universal-corpus/producer_stubs \
  --graph-output-dir _build/.tmp/production-quality/w12d-runtime-pdc-graphs \
  --output _build/.tmp/production-quality/w12d_universal_outcome_corpus_stub_run.json \
  --allow-typed-blockers
```

Accept the corpus-stub result only as governed-pilot validation evidence. A
production-capable promotion still needs real-producer mode or explicit
producer-owned evidence. If corpus-stub mode reports useful design while
real-producer mode blocks, record that as `producer_missing` or
`bridge_missing` for the production lane, not as a successful production
closeout.

### 4.5 I7-bis Integration Realism Check

Run I7-bis before Wave 6 exit and again before Wave 12 entry. It proves the
runtime path invokes W6/W7 components instead of relying on isolated unit tests.
Typed blockers from this command are integration blockers, not useful-design
outcomes.

```bash
uv run python tools/quality/validation/run_universal_compilation_integration_realism_check.py \
  --repo-root . \
  --output _build/.tmp/production-quality/i7bis_integration_realism_check.json \
  --allow-typed-blockers
```

### 5. Cloud One-Lane Revalidation

Run only after local checks are green or intentionally held with typed
blockers:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --deterministic \
  --only-lane profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only \
  --json-output _build/.tmp/production-quality/universal_pdc_final_live_research_lane.json \
  --timeout-s 1200

uv run python tools/quality/validation/inspect_evidence_bundles.py \
  --repo-root . \
  --matrix-run-json _build/.tmp/production-quality/universal_pdc_final_live_research_lane.json \
  --json-output _build/.tmp/production-quality/universal_pdc_final_evidence_bundle_inspection.json
```

## Accept, Hold, Or Abort

| Decision | Minimum condition | Required record |
| --- | --- | --- |
| Promote research-only | Closeout honesty is preserved and all public limitations/blockers are visible; useful-design floor may be absent. | Closeout note with research-only posture and typed blocker summary. |
| Promote governed pilot | At least one useful design outcome exists in every committed domain slice and at least 50 percent useful-design rate over the universal outcome set. | Closeout note plus feature flag and tuned config state. |
| Promote production-capable | At least one useful design outcome exists in every committed domain slice, at least 70 percent useful-design rate overall, and no domain slice below 40 percent unless explicitly held out. | Rollout ADR or release note with command evidence. |
| Hold | Validation produces narrow typed blockers, accepted tuned-parameter holds, or domain exclusions. | Closeout note with owner, next action, and revalidation trigger. |
| Abort or rollback | Projection truth fails, capability labels remain open for required posture, evidence provenance is missing, or cloud/live lane fails without typed blocker. | Rollback record and incident or closeout note. |

## Rollback Procedure

1. Stop promotion, public publication, dashboard refresh, export packaging, and
   API publication for the affected run or lane.
2. Set Universal PDC projection and other affected feature flags to their
   rollback values.
3. Downgrade affected tuned configs to advisory, warning-only, strict
   hard-collapse, no-fallback, or recommendation-only posture as listed in the
   operator guide.
4. Preserve the failed bundle, public export, dashboard snapshot, API payload,
   scorecard, closeout verdict, feature flag state, tuned config versions, and
   command output.
5. Rerun the smallest verifier that proves the rollback effect:

   ```bash
   uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py -q
   uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root .
   ```

6. If runtime evidence may have been published, route through the PDC operator
   triage runbook for scoped reissue, withdrawal, or public revision state.
7. Write or update a closeout note under
   `docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md`.

Rollback is successful only when the external surfaces no longer expose the
failed projection as successful and the evidence explaining the failure remains
available.

## Tuned Config Rollback Map

| Control | Safe rollback posture |
| --- | --- |
| Universal PDC projection | Disable public projection; keep reviewer/audit inspection over closeout refs. |
| Effective-independence graded weights | Revert to strict hard-collapse and publish limitations. |
| Acquisition planner commit | Recommendation-only; require human or governed commit. |
| Review-effectiveness consequences | Advisory only; no blocking consequence. |
| Calibration blocking | Warning/review only; historical prior remains future influence. |
| Complexity budget closeout effect | Advisory complexity report only. |
| Participation thresholds | Downgrade to limitation or review-required; no prevalence authority from thin evidence. |
| Rare-domain scarcity path | Typed deficit or public limitation; no support inflation. |
| Run-cost and degradation thresholds | Warning/limitation only unless authority policy explicitly blocks. |
| Legal fallback tables | Disable fallback and emit limited/no-authority blocker. |

## Closeout Record Minimum

Every rollout, hold, abort, or rollback note must include:

- git revision, scenario set, authority profiles, feature flags, tuned config
  versions, and command set;
- closeout honesty rate and useful-design rate, reported separately;
- public, reviewer, expert, machine, dashboard, API, export, and audit surface
  status;
- every capability label still open and its owner;
- every accepted tuned-parameter hold and revalidation trigger;
- bundle, CAS, runtime event, scorecard, closeout, public export, and dashboard
  refs;
- rollback action taken or explicit reason rollback was not needed;
- next owner and expected verification command.

## Pattern Pass

Relevant patterns: `P03`, `P06`, and `P13`.

Correct pattern: rollout and rollback are command-backed operator procedures
that preserve public truth and evidence provenance without adding a parallel
authority object. The runbook closes the W5.E `surface_missing` risk for
rollout/rollback procedure discoverability, while runtime capabilities remain
governed by their own evidence chains.
