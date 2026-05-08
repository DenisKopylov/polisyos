# Benchmarks

`benchmarks/` is the public product evaluation surface. Phase 1.4 keeps the
current files in place, but fixes the target contract before Wave 2/3 moves.

## Target Shape

```text
benchmarks/
  README.md
  suites/
  _data/
src/polisyos/benchmarks/
  runner/
  metrics/
  reporting/
  harness/
```

## Collection Contract

- Public benchmark suites collect from `benchmarks/suites`.
- Benchmark data and golden inputs collect from `benchmarks/_data`.
- Reusable runner implementation moves to `src/polisyos/benchmarks`.
- Internal performance and cost-regression checks stay under
  `tests/performance`.
- New benchmark pytest configuration is not allowed. The existing
  `benchmarks/conftest.py` is a Phase 1.4 explicit transition exception in
  `architecture/tests/ratchets.toml`.

Physical moves are deferred to Wave 2 and Wave 3; this README is the
report-only collection contract for new work.
