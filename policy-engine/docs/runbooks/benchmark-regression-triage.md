# Benchmark Regression Triage

Related how-to: [Run Benchmarks](../how-to/run-benchmarks.md). Related reference:
[Foundry](../reference/foundry/index.md).

> Используйте этот runbook, когда benchmark suite начинает проигрывать по
> quality, latency, stability, comparator completeness или release gate result.

## Symptom

- smoke или extended benchmark reports показывают lower pass rate;
- release summary или comparator matrix ухудшаются по suite/circuit;
- benchmark JSON output отличается между двумя одинаковыми runs без
  оправданной nondeterminism note;
- regression попадает в local validation, nightly pack или release review.

## Likely Causes

- change в Foundry/Scientist/Fabric logic ухудшил factual metrics;
- dependency/toolchain bump изменил numerics, runtime cost или JIT behavior;
- baseline snapshot устарел или был заменён без явной фиксации;
- comparator, ablation или shadow evidence path перестал быть complete;
- regression связана не с model quality, а с data or fixture drift.

## Timeline Capture Expectations

Зафиксируйте:

- suite ID, circuit, mode, profile и report path;
- baseline report и candidate report;
- commit SHA, environment, seed/profile if relevant;
- regression type: pass rate, latency, NaN rate, comparator completeness,
  release gate, memory/cost;
- был ли regression замечен локально, в nightly или в release review.

## First Triage Steps

1. Повторите failing suite через canonical registry-backed runner:

   ```bash
   cd policy-engine
   bash benchmarks/run_all_benchmarks.sh --circuit <suite-or-circuit> --mode smoke
   ```

2. Если regression выглядит performance-specific, запустите узкий pytest path
   или benchmark-specific test рядом с suite family.
3. Сравните generated JSON reports, а не только console summary.
4. Проверьте, не затронуты ли одновременно:
   - dependency upgrades;
   - schema/contract refresh;
   - replay/data fixture drift;
   - observability or instrumentation overhead.
5. Если regression user-visible only after aggregation, rebuild release summary
   и comparator completeness, а не делайте вывод по одному suite.

## Rollback / Mitigation

- если regression severe и confirmed, не повышайте candidate в release;
- если regression caused by recent merge, откатите offending change или
  temporarily pin feature flag/profile;
- если regression only on one benchmark family, ограничьте blast radius и не
  останавливайте unrelated work без evidence;
- если baseline устарел, обновление baseline допустимо только после явного
  review и rationale.

## Escalation Owner

- primary: `@foundry-owners`;
- supporting: owner затронутого subsystem surface
  (`@scientist-owners`, `@fabric-owners`, `@platform-owners`).

## Follow-up Checklist

- regression подтверждена повторным run на canonical runner;
- baseline и candidate artifacts preserved;
- root cause классифицирован как code, data, dependency, tooling или baseline drift;
- benchmark registry / release summary / docs updated if expectations changed;
- added targeted regression coverage if blind spot was discovered.

## Blameless Postmortem

### What Went Well

- какой suite или metric first exposed the regression;
- что помогло быстро локализовать источник;
- насколько reproducible оказался benchmark path.

### What Went Poorly

- где suite semantics или report format были неочевидны;
- какие baseline assumptions не были записаны явно;
- была ли путаница между benchmark drift и expected product evolution.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Add focused regression coverage for the failing benchmark path | `@foundry-owners` | YYYY-MM-DD | open |
| Clarify benchmark baseline or report interpretation if it was ambiguous | affected owner | YYYY-MM-DD | open |
| Update release review policy if the regression should block sooner | `@platform-owners` | YYYY-MM-DD | open |
