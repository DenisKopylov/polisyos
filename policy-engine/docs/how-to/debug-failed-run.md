# Диагностика failed run

Related reference: [Runs API](../reference/api/runs.md). Related how-to: [Use Control Plane](use-control-plane.md).

> Эта страница для инженеров и операторов, которым нужно быстро локализовать failure: понять, это проблема orchestration, данных, governance или control-plane инфраструктуры.

Лучший practical подход в PolicyOS: не начинать с исходников, а идти по наблюдаемым слоям сверху вниз.

## 1. Начните с job state

Если run стартовал через control plane, первым делом проверьте job:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
```

Важные сигналы:

- `state=failed` сразу говорит, что проблема уже зафиксирована durable state store;
- `progress` показывает, завис ли job посередине;
- `kind` отделяет workflow failure от Lex pipeline failure.

Если job не двигается, сразу смотрите:

- `GET /api/v1/control/workers`
- `GET /api/v1/control/outbox`

## 2. Переключитесь на run timeline

Как только у вас есть `run_id`, переходите к timeline:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/timeline"
```

Timeline помогает ответить на три вопроса:

- на каком узле остановился workflow;
- был ли failure после governance gate или до него;
- есть ли последний успешный checkpoint / artifact emission перед падением.

## 3. Посмотрите node outcomes и workflow view

Следующие два endpoint-а обычно дают самый высокий signal-to-noise ratio:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/nodes"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/workflow"
```

Ищите:

- node со status/error, который оборвал граф;
- missing prerequisites;
- divergence между ожидаемым DAG и реально выполненными шагами.

## 4. Постройте lineage артефактов

Если есть подозрение на data/input/problem, переходите к lineage:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/lineage?max_depth=3&max_nodes=250"
```

Это особенно полезно, когда нужно понять:

- какой `data_snapshot_ref` реально вошёл в запуск;
- был ли собран `NormPack` или evidence bundle;
- дошёл ли run до decision-packet / replay artifacts.

## 5. Проверьте governance и decision-validity layer

Если run не упал технически, но остановился по policy/gate причинам, смотрите:

- `GET /api/v1/runs/{run_id}/evidence-context`
- `GET /api/v1/control/runs/{run_id}/decision-validity`

Симптомы governance-related stop:

- issues с severity `BLOCKER`;
- human-review requirement;
- missing evidence / trust / replay prerequisites.

## 6. Используйте live stream для активной отладки

Когда run ещё исполняется и вам нужен near-real-time след:

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/live"
```

Live stream особенно полезен для:

- timeline events;
- governance summaries;
- decision-validity state;
- agent/pipeline progress.

## 7. Как думать про checkpoint и replay

Если failure случился после частичного прогресса, смотрите:

- какой `checkpoint_policy` использовался при launch;
- есть ли `last_checkpoint_ref` в run-facing artifacts/state;
- были ли уже собраны replayable audit artifacts.

Практическое правило:

- если failure до materialized artifacts, лечите input/orchestration;
- если failure после checkpoint, выгоднее продолжать triage от lineage и replay-ready артефактов;
- если failure выглядит nondeterministic, сравнивайте checkpoint/ref trail между двумя прогонами.

## 8. Быстрая decision tree

1. `job failed` и нет worker heartbeat:
   смотрите control-plane backend и worker leases.
2. `job completed`, но run unusable:
   смотрите governance / decision-validity / evidence-context.
3. `run stalled` в середине DAG:
   смотрите `timeline`, `nodes`, `workflow`.
4. `unexpected result` при успешном завершении:
   смотрите `lineage`, входные артефакты и replay trail.

## Что дальше

- Для launch/poll operational surface смотрите [Use Control Plane](use-control-plane.md)
- Для env и deployment posture откройте [Deploy Runtime](deploy-runtime.md)
- Для API деталей используйте [Runs API reference](../reference/api/runs.md)
