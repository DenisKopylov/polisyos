# Canary Rollback or Failed Production Promotion

Related policy: [SLO and Error Budget Policy](../reference/operations/slo-error-budget.md).
Related how-to: [Deploy Runtime](../how-to/deploy-runtime.md).

> Используйте этот runbook для staged rollout, canary evaluation или любого
> production promotion gate. PolicyOS now performs a live runtime canary from
> the installed release artifact before production promotion, а этот документ
> также покрывает manual environment approval / rollback after the automated
> checkpoint.

Owner: `@platform-owners`
Last tested: `2026-04-17` against current canary and acceptance-rehearsal evidence.
Evidence path: `docs/archive/reports/platform-release-canary.md`; `docs/archive/reports/platform-acceptance-manual.md`; `docs/reference/operations/platform-acceptance-audit.md`
Rollback path: return traffic and config to the last known-good candidate before further investigation, then freeze further promotion until the root cause is understood.

## Symptom

- release candidate не проходит promotion checkpoint;
- после limited rollout деградируют golden signals, и rollout останавливается;
- rollback был запущен вручную или автоматически по alert threshold;
- production deploy technically успешен, но runtime/control-plane surface стала
  хуже baseline.

## Likely Causes

- runtime/config drift между staging и production;
- silent contract mismatch между runtime и dashboard/operator tooling;
- hidden dependency на state store, auth, SBOM/signing, OPA или connector path;
- SLO burn начал расти после rollout, хотя pre-release checks были зелёными;
- release candidate содержал migration/feature flag combination, не покрытую
  smoke path.

## Timeline Capture Expectations

Зафиксируйте обязательно:

- candidate build ID, commit SHA и release note summary;
- точное окно rollout start / hold / rollback в UTC;
- какой checkpoint не пройден: health, latency, errors, saturation, manual sign-off;
- что сравнивалось против baseline;
- какой decision maker нажал hold/rollback/promote;
- какие user-facing routes, jobs или dashboards пострадали.

## First Triage Steps

1. Подтвердите, что failure действительно promotion-related, а не older
   background incident.
2. Сравните candidate против last known good по:

   - health/readiness;
   - runtime error rate;
   - DAG success rate;
   - control-plane queue/worker health;
   - frontend platform health.
3. Откройте trusted dashboards:
   `executive-overview`, `slo-overview`, `scientist-agents`,
   `security-phase4`.
4. Если rollout partial, зафиксируйте scope: какой процент traffic/users/jobs
   уже попал под candidate.
5. Сразу проверьте, нет ли parallel failure в contracts, signing/SBOM,
   docs publish или replay/state restore path.

## Rollback / Mitigation

- если candidate ухудшает golden signals, rollback имеет приоритет над поиском
  идеального root cause;

- возвращайтесь к last known good artifact/config pair, а не только к коду;
- заморозьте дальнейшую promotion активность до стабилизации и incident review;
- security fixes и P0 restoration work остаются carve-out even under freeze, но
  их scope должен быть минимальным и явно записан.

## Escalation Owner

- primary: `@platform-owners`;
- runtime evaluation: `@runtime-owners`;
- affected subsystem owner joins after rollback decision, не вместо него.

## Follow-up Checklist

- recorded candidate-vs-baseline comparison preserved;
- root cause классифицирован: code, config, dependency, migration, traffic shape;
- если rollback делался вручную, documented manual steps now exist;
- release checklist amended, если missing checkpoint allowed bad candidate through;
- error-budget impact reflected in freeze/no-freeze decision.

## Blameless Postmortem

### What Went Well

- какой checkpoint вовремя остановил bad promotion;
- насколько быстро вернулся known-good state;
- были ли sufficient ownership and decision rights.

### What Went Poorly

- где rollout signal оказался ambiguous;
- какие staged checks не отражали реальный production path;
- было ли слишком много manual knowledge в rollback steps.

### Action Items

| Action item                                                 | Owner              | Due date   | Status |
| ----------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add or tighten the missing promotion checkpoint             | `@platform-owners` | YYYY-MM-DD | open   |
| Reduce manual rollback steps for this release path          | `@platform-owners` | YYYY-MM-DD | open   |
| Add staging/prod parity coverage for the root-cause surface | affected owner     | YYYY-MM-DD | open   |
