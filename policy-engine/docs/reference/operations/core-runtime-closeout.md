# Core Runtime Closeout

Related reference: [Platform Acceptance Audit](platform-acceptance-audit.md), [SLO Error Budget](slo-error-budget.md), [Quality Gates](../quality-gates.md). Related runbooks: [Runbooks](../../runbooks/index.md).

Owner: `@runtime-owners`
Source of truth: `release/core-runtime-closeout.ledger.toml`, `release/core-runtime-closeout.evidence.template.toml`, `docs/archive/reports/core-runtime-closeout.{md,json}`, and the `polisyos-tools workspace core-runtime-closeout` / `core-runtime-long-soak` commands

> This page is the executable Wave 0 / Stream G artifact for
> `CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md`: one canonical closure ledger
> for `WS-0A .. WS-3C`, with machine-readable evidence, reopen gaps, and final
> signoff hooks.

## Canonical Inputs

The closeout flow is driven by two repo-tracked inputs:

- `release/core-runtime-closeout.ledger.toml`
- `release/core-runtime-closeout.evidence.template.toml`

The ledger is the source of truth for:

- workstream status: `implemented`, `partial`, `missing`, `reopened`;
- code, test, docs/ops, and CI evidence paths;
- blocking gaps that still prevent a workstream from graduating to
  `implemented`.

The manual evidence file is used only for final signoff and operator review.

## Run the Closeout Ledger

From `policy-engine/`:

```bash
uv run polisyos-tools workspace core-runtime-closeout \
  --summary docs/archive/reports/core-runtime-closeout.md \
  --json-output docs/archive/reports/core-runtime-closeout.json
```

This performs the Wave 0 structural checks:

- every `WS-*` heading in `CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md`
  exists in the ledger exactly once;

- every evidence path in the ledger exists;
- implemented workstreams carry no blocking gaps;
- partial/missing/reopened workstreams declare explicit blocking gaps.

The default mode is intentionally non-blocking for incomplete programs: it
validates the ledger and emits the current reopen list, but it does not require
all workstreams to be fully closed.

## Long-Soak Evidence

Production-duration performance evidence is generated separately from the normal
PR gate so that closeout proof exists without stretching every patch workflow:

```bash
uv run polisyos-tools workspace core-runtime-long-soak \
  --summary docs/archive/reports/core-runtime-long-soak.md \
  --json-output docs/archive/reports/core-runtime-long-soak.json
```

The long-soak runner exercises:

- incremental `RunIndexService` refresh loops;
- timeline query/build loops with cache refreshes;
- first-class async CAS round trips;
- async checkpoint restore cycles;
- async cursor-store stream progress persistence.

This evidence is repo-tracked through the command and archived reports above.
If a team also schedules it in external CI or GitHub Actions, that automation
is operational/manual truth rather than a versioned workflow contract in this
repository.

## Final Closeout Mode

For final signoff, fill a manual evidence file first:

```bash
cp release/core-runtime-closeout.evidence.template.toml /tmp/core-runtime-closeout.evidence.toml
```

Then run the strict mode:

```bash
uv run polisyos-tools workspace core-runtime-closeout \
  --manual-evidence /tmp/core-runtime-closeout.evidence.toml \
  --require-manual-evidence \
  --require-full-closeout \
  --summary docs/archive/reports/core-runtime-closeout.md \
  --json-output docs/archive/reports/core-runtime-closeout.json
```

Strict mode fails unless:

- every workstream is `implemented`;
- every manual signoff item is recorded as `true`.

## Manual Signoff Checklist

The manual evidence template covers the minimum final closeout hooks:

- `engineering_signoff`
- `operator_signoff`
- `release_review_bundle`
- `reopened_followups`

Structured entries are also supported:

```toml
[manual.engineering_signoff]
status = true
notes = "Platform owners reviewed the residual list and approved final status changes."
evidence = ["release-review/contracts/core-runtime-closeout.json"]
```

## Required Outputs

The final closeout packet must leave:

- one validated closure ledger;
- one markdown summary;
- one machine-readable JSON snapshot;
- one long-soak markdown summary;
- one long-soak machine-readable JSON report;
- one manual evidence file or equivalent attached signoff artifact;
- one explicit reopen/residual list if any workstream is still not implemented.
