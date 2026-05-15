---
title: Honest Diagnostics Substrate Wave 0 Closeout
status: wave-0-closeout
owner: team-runtime-quality
created: 2026-05-15
source_plan: docs/plans/active/POLICYOS_HONEST_DIAGNOSTICS_SUBSTRATE_IMPLEMENTATION_PLAN.md
---

# Honest Diagnostics Substrate Wave 0 Closeout

Wave 0 freezes the current failure surface. It intentionally does not implement
the runtime authority behavior that would make the HDS red controls pass.

## Baseline

Commands:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic --json-output _build/honest-diagnostics/baseline/deterministic_matrix.json --timeout-s 1200
uv run python tools/ci/check_policyos_production_quality_best_in_class.py --repo-root . --output-format json > _build/honest-diagnostics/baseline/readiness.json
```

Results:

- Deterministic matrix created at `2026-05-15T07:50:54+00:00`.
- Matrix summary: `1 selected`, `1 executed`, `1 passed`, `0 failed`, `0 blocked`, `0 skipped`.
- Matrix lane:
  `profile-research__provider-simulated__data-canonical_production__scenario-public_golden__ui-api_only`
  passed with scorecard status `pass`.
- Readiness aggregator status: `pass`.
- Readiness findings: `24 total`, `24 pass`, `0 fail`, `0 warn`.
- New Bucket A substrate blocker from this baseline: none found.

Generated baseline JSON remains under `_build/honest-diagnostics/baseline/` and
is not source tracked.

## Red Controls

Normal red-control command:

```bash
uv run pytest tests/unit/runtime/quality tests/unit/tools/test_canary_evidence_authority.py tests/repo_quality/tools/test_honest_diagnostics_substrate_red_controls.py -q
```

Result: exit code `0`; HDS red controls stayed as strict expected failures.
Observed shape: `70` collected checks, `16` strict `XFAIL`, no `XPASS`.

Proof command:

```bash
uv run pytest tests/unit/runtime/quality tests/unit/tools/test_canary_evidence_authority.py tests/repo_quality/tools/test_honest_diagnostics_substrate_red_controls.py --runxfail -q
```

Result: exit code `1`; the following HDS controls failed for the expected
pre-implementation reasons:

- bundle-local `quality_evidence/*.json` refs still satisfy scorecard gates;
- embedded report ref mismatch is not yet failed closed;
- fixture-only authority envelopes are not yet blocked for serious closeout;
- warn scorecards still produce `warn` instead of serious closeout failure;
- missing or sampled-away serious diagnostic events are not yet blockers;
- canary assembly still mints bundle-generated runtime-looking refs;
- projected `quality_status=pass` can still leak through bundle/dashboard surfaces;
- silent fallback without degradation ledger is not yet blocked;
- `no norms retrieved` is not yet distinguished from `no applicable law`;
- data existence is not yet tied to a semantic binding ledger;
- readiness runtime-ref gates still accept bundle-local projected refs.

These failures are retained as `pytest.mark.xfail(strict=True, reason="HDS red control pending implementation")`.

## Coverage And Anti-Drift

Commands:

```bash
uv run python tools/quality/validation/build_honest_diagnostics_coverage.py --repo-root . --output-dir _build/honest-diagnostics/rebaseline/wave-0
uv run python tools/quality/validation/compare_honest_diagnostics_rebaseline.py --repo-root . --current _build/honest-diagnostics/rebaseline/wave-0 --previous _build/honest-diagnostics/rebaseline/wave-minus-1 --output _build/honest-diagnostics/rebaseline/wave-0/diff_from_wave_N_minus_1.json --output-format json
uv run python tools/quality/validation/check_substrate_drift.py --repo-root . --require-passing
```

Results:

- Coverage status: `pass`.
- Coverage summary: `1 invariant`, `0 invalid invariants`, `13 required metrics`.
- Operator TTRC metrics are explicitly `measurement_status=not_measured` with
  `value=null`, `numerator=0`, `denominator=0`.
- Rebaseline comparator status: `no_prior_baseline`.
- Rebaseline summary: `13 improved`, `0 missing`, `0 regressed`, `0 denominator_changed`, `0 violations`.
- Embedded anti-drift status: `pass`.
- Anti-drift counts: `xfail_strict_count=4`, `xfail_non_strict_count=0`,
  `skip_count_substrate_tests=0`, `allow_fallback_count=0`,
  `fixture_serious_consumption_count=0`, `warn_closeout_acceptance_count=0`,
  `adr_softening_findings=[]`, `non_goal_violations=[]`.

## Source-Control Boundary

Wave 0 source-controlled set:

- `architecture/production_quality/invariant_registry.toml`
- `docs/archive/reports/HONEST_DIAGNOSTICS_WAVE0_CLOSEOUT_2026-05-15.md`
- `docs/plans/active/POLICYOS_HONEST_DIAGNOSTICS_SUBSTRATE_IMPLEMENTATION_PLAN.md`
- `docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md`
- `tests/_helpers/hds_quality.py`
- `tests/fixtures/runtime_quality/**`
- `tests/repo_quality/tools/test_honest_diagnostics_coverage.py`
- `tests/repo_quality/tools/test_honest_diagnostics_decision_log.py`
- `tests/repo_quality/tools/test_honest_diagnostics_substrate_drift.py`
- `tests/repo_quality/tools/test_honest_diagnostics_substrate_red_controls.py`
- `tests/repo_quality/tools/test_production_invariant_registry.py`
- `tests/repo_quality/tools/test_runtime_quality_contract_fixtures.py`
- `tests/unit/runtime/quality/test_authority_envelope_contract.py`
- `tests/unit/runtime/quality/test_diagnostic_event_contract.py`
- `tests/unit/tools/test_canary_evidence_authority.py`
- `tools/devx/workspace/verify.py`
- `tools/quality/validation/build_honest_diagnostics_coverage.py`
- `tools/quality/validation/check_substrate_drift.py`
- `tools/quality/validation/compare_honest_diagnostics_rebaseline.py`

Generated files under `_build/honest-diagnostics/**` are intentionally ignored
and must not be committed unless explicitly requested.

## PR Notes Block

Wave 0 HDS freezes contracts and red controls only. Runtime behavior is not
weakened or remediated in this wave.

Expected red-control evidence:

- Normal HDS suite exits `0` with strict HDS `XFAIL` controls and no `XPASS`.
- `--runxfail` exits `1` with 16 failing HDS controls, proving the controls are
  still red before implementation.

Baseline evidence:

- Deterministic matrix: `1/1` lane passed, scorecard status `pass`.
- Readiness aggregator: `24/24` findings passed.
- No new Bucket A substrate blocker found in this baseline.

Closeout evidence:

- Coverage dashboard: `pass`, 13 metrics, 1 valid invariant.
- Comparator against missing prior baseline: typed `no_prior_baseline`.
- Anti-drift audit: `pass`, zero non-strict xfails, zero substrate skips, zero
  fallback allowances, zero fixture serious consumption, zero warn closeout
  acceptance, zero ADR softening findings, zero Non-Goal violations.
