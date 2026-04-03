# Использование control plane

Related reference: [Control Plane API](../reference/api/control.md). Related how-to: [Deploy Runtime](deploy-runtime.md).

> Эта страница для операторов и интеграторов, которым нужно запускать runs, ingestion и Lex jobs через runtime HTTP surface и понимать, как читать control-plane state.

Control plane в PolicyOS отвечает за write-capable операции:

- запуск workflow run;
- запуск natural-language run;
- data discovery / resolve / ingest;
- Lex batch jobs;
- operational visibility через jobs, workers, outbox и decision-validity endpoints.

## Перед началом

Убедитесь, что runtime поднят:

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
```

И что execution profile и state store заданы осознанно:

- `POLISYOS_EXECUTION_PROFILE`
- `POLISYOS_CONTROL_WORKER_BACKEND`
- `POLISYOS_CONTROL_STATE_STORE_BACKEND`
- `POLISYOS_CONTROL_SQLITE_PATH` или `POLISYOS_CONTROL_POSTGRES_DSN`

Подробнее про env surface: [Deploy Runtime](deploy-runtime.md).

## 1. Запустите workflow run

Базовый launch:

```bash
curl -X POST "http://localhost:8000/api/v1/control/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source": {
      "data_snapshot_ref": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    },
    "execution_profile": "research"
  }'
```

Ответ даёт:

- `run_id`
- `job_id`
- `effective_execution_profile`

`run_id` нужен для run-facing debug APIs, `job_id` для durable control-job state.

## 2. Poll durable job state

Сразу после launch проверяйте job, а не пытайтесь гадать по логам:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
```

Смотрите прежде всего на:

- `state`: `pending`, `running`, `completed`, `failed`
- `kind`
- `progress`
- `started_at` / `finished_at`

## 3. Просматривайте workers и outbox

Если job завис или не движется, переходите к operational endpoints:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/workers"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/outbox"
```

Что искать:

- есть ли активный lease на worker;
- не застрял ли job без heartbeat;
- копятся ли outbox events без downstream consumption;
- совпадает ли ожидаемый backend с фактическим deployment mode.

## 4. Используйте data endpoints как отдельный operational слой

Control plane умеет не только запускать Scientist workflow, но и подготавливать данные:

- `POST /api/v1/control/data/discover`
- `POST /api/v1/control/data/resolve`
- `POST /api/v1/control/data/preview`
- `POST /api/v1/control/data/ingest`
- `GET /api/v1/control/data/connectors`
- `GET /api/v1/control/data/profiles`
- `GET /api/v1/control/data/binding-profiles`

Практический паттерн:

1. discover/resolve candidate datasets;
2. preview coverage;
3. ingest и получить `data_snapshot_ref`;
4. запускать workflow run уже с готовым snapshot.

## 5. Запускайте Lex jobs как control-plane workload

Для batch Lex path:

```bash
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cards_path": "data/lex/cards",
    "texts_path": "data/lex/texts",
    "output_dir": ".polisyos/lex-out",
    "resume": true,
    "execution_profile": "research"
  }'
```

Затем:

- `GET /api/v1/control/jobs/{job_id}`
- `GET /api/v1/control/lex/status/{pipeline_id}`
- `GET /api/v1/control/lex/graph/stats`

## 6. Понимайте границы control plane

Control plane не заменяет собой весь runtime debug surface.

Используйте его для:

- launch/poll/operate;
- durable state;
- worker/outbox visibility;
- write-capable orchestration.

Переходите в run/debug APIs, если вам нужно:

- timeline;
- node outcomes;
- artifact lineage;
- evidence context;
- decision-validity summary по конкретному run.

## 7. Минимальный операторский маршрут

Если нужно быстро понять состояние системы, последовательность обычно такая:

1. `POST /api/v1/control/runs` или `.../lex/trigger`
2. `GET /api/v1/control/jobs/{job_id}`
3. при проблеме: `GET /api/v1/control/workers`
4. затем: `GET /api/v1/control/outbox`
5. если run уже создан: переход к `/api/v1/runs/{run_id}/timeline`, `/nodes`, `/lineage`

## Что дальше

- Для развертывания и env policy смотрите [Deploy Runtime](deploy-runtime.md)
- Для failure triage откройте [Debug Failed Run](debug-failed-run.md)
- Для полного endpoint catalog смотрите [Control Plane API reference](../reference/api/control.md)
