# Promoted Benchmark Reports

Benchmark reports are local by default. Generated output belongs under the
ignored `benchmarks/_reports/` tree until a quality owner promotes a small,
reviewable summary here.

## Promotion Checklist

- record benchmark suite id, profile, hardware, seed, and command;
- cite the gate, release, or ADR that needs the evidence;
- keep raw result bundles ignored unless registered as a generated artifact;
- prefer Markdown summaries plus compact JSON/TOML baselines;
- replace superseded baselines instead of accumulating every local run.

New files should use `YYYY-MM-DD-<suite>-<profile>.(md|json|toml)` and stay
under 1 MiB.
