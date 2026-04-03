# Runtime API Outage

Related how-to: [Deploy Runtime](../how-to/deploy-runtime.md),
[Use Control Plane](../how-to/use-control-plane.md),
[Debug Failed Run](../how-to/debug-failed-run.md).

> Используйте этот runbook, когда runtime HTTP surface недоступен полностью
> или частично: health, runs, artifacts, control-plane endpoints либо operator
> dashboard перестали быть usable.

## Symptom

- `/health` или `/ready` не отвечают либо отвечают `degraded`/`5xx`;
- `GET /api/v1/runs`, `GET /api/v1/runs/{run_id}` или
  `POST /api/v1/control/runs` падают массово;
- dashboard показывает `Health: unavailable`, а `/platform` или `/runs`
  не может загрузить данные;
- alert family по DAG success rate, runtime latency, agent error spike или
  connector errors уходит в `warning`/`critical`.

## Likely Causes

- runtime boot failure в `create_runtime_api_app(...)`;
- bad deploy или config drift в authz/OIDC/OPA/state store variables;
- degradation Postgres/SQLite state store, worker backend или outbox consumer;
- upstream dependency outage: Keycloak, OPA, LLM gateway, external connectors;
- ресурсное истощение, saturation или deadlock в control-plane workers.

## Timeline Capture Expectations

Сразу собирайте один incident timeline:

- UTC timestamp начала симптома и кто заметил первым;
- environment, deployment SHA, execution profile;
- failing URL, HTTP method, status code, request ID, trace ID;
- affected routes: `health`, `runs`, `artifacts`, `control`;
- active alerts и dashboard snapshots;
- последние config/deploy changes за 60 минут до инцидента.

## First Triage Steps

1. Подтвердите blast radius:

   ```bash
   curl -i http://localhost:8000/health
   curl -i http://localhost:8000/ready
   curl -i http://localhost:8000/api/v1/health
   ```

2. Проверьте read surface и control surface отдельно:

   ```bash
   curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/runs

   curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/control/workers

   curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/control/outbox
   ```

3. Если known `job_id` или `run_id` уже есть, посмотрите durable state:

   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/control/jobs/$JOB_ID

   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/runs/$RUN_ID/timeline
   ```

4. Переключитесь на trusted dashboards:
   `slo-overview`, `executive-overview`, `scientist-agents`,
   `security-phase4`.

5. Если outage похож на config drift, сравните runtime env с последним
   known-good deploy, а не редактируйте env наугад.

## Rollback / Mitigation

- верните last known good deployment/release candidate;
- если проблема только в write path, временно ограничьте `POST` workload и
  оставьте read-only surface для операторов;
- если проблема в optional security/dependency sidecar, временный bypass
  возможен только по явному решению incident commander и с записью в timeline;
- снизьте ingress load или concurrency, если причина saturation, а не logic
  fault;
- не запускайте новые migrations, contract refreshes или dependency bumps до
  стабилизации.

## Escalation Owner

- primary: `@runtime-owners`;
- incident coordination: `@platform-owners`;
- supporting owners: `@frontend-owners` для operator UX, affected subsystem
  owners для downstream remediation.

## Follow-up Checklist

- сохранены request IDs / trace IDs и связанные логи;
- приложены dashboard panels, которые реально использовались в triage;
- зафиксирована точка rollback/mitigation и её effect;
- обновлён alert routing, если сигнал пришёл не тому owner;
- если outage был silent для dashboard users, добавлен synthetic check или
  frontend UX signal.

## Blameless Postmortem

### What Went Well

- какой signal дал fastest accurate detection;
- где correlation `alert -> dashboard -> trace/log -> runbook` сработала быстро;
- что уменьшило MTTR.

### What Went Poorly

- где не хватило correlation IDs;
- какие alerts были слишком поздними или noisy;
- что пришлось восстанавливать из чатов вместо системных артефактов.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Add or improve detection for the specific failing route/dependency | `@runtime-owners` | YYYY-MM-DD | open |
| Close the config, scaling, or dependency gap that caused the outage | affected owner | YYYY-MM-DD | open |
| Update dashboard, alert, or runbook routing if triage was slow | `@platform-owners` | YYYY-MM-DD | open |
