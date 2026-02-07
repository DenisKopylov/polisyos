# prometheus — Metrics Collection, Alerting & SLO

Конфигурация Prometheus для PolicyOS: scrape метрик, 16 alert rules (включая 5 SLO), 12 recording rules для предвычисления агрегатов.

## Файлы

| Файл | Назначение |
|---|---|
| `prometheus.yml` | Scrape config: 15s interval, targets polisyos (:9464) + self-monitoring (:9090) |
| `alerts.yml` | 11 alert rules по 4 группам: cost, agents, simulation, calibration |
| `slo_alerts.yml` | 5 SLO alert rules: DAG success rate, latency, NaN, connector errors |
| `recording_rules.yml` | 4 recording rules (30s): LLM cost/h, acceptance rate, cache ratio, error rate |
| `slo_recording_rules.yml` | 8 SLO recording rules (30s): success rates, percentiles, NaN rates |

## Scrape Configuration

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: polisyos          # host.docker.internal:9464/metrics
    labels: { environment: development }
  - job_name: prometheus         # self-monitoring, prometheus:9090
```

Все rule-файлы подключаются через абсолютные пути в контейнере (`/etc/prometheus/*.yml`).

## Alert Rules

### alerts.yml — Operational Alerts (11 rules)

**polisyos.cost** (team: platform)

| Alert | Условие | for | Severity |
|---|---|---|---|
| `HighLLMCost` | LLM cost >$50/h | 5m | warning |
| `HighLLMCostCritical` | LLM cost >$100/h | 5m | critical |

Формула cost: `(sum(rate(llm_tokens{prompt}[1h])) * 0.00001 + sum(rate(llm_tokens{completion}[1h])) * 0.00003) * 3600`

**polisyos.agents** (team: scientist)

| Alert | Условие | for | Severity |
|---|---|---|---|
| `AgentErrorSpike` | Error rate >5% за 5m | 5m | warning |
| `AgentErrorSpikeCritical` | Error rate >20% за 5m | 2m | critical |
| `GovernancePassSlowdown` | p95 latency >30s | 10m | warning |

**polisyos.simulation** (team: foundry)

| Alert | Условие | for | Severity |
|---|---|---|---|
| `SimulationStall` | Active runs >0 AND throughput ==0 | 5m | critical |
| `JITRecompilationStorm` | >10 compilations/min | 5m | warning |
| `JITRecompilationStormCritical` | >30 compilations/min | 2m | critical |
| `LowCacheHitRatio` | CAS cache hit <70% | 15m | warning |

**polisyos.calibration** (team: foundry)

| Alert | Условие | for | Severity |
|---|---|---|---|
| `CalibrationDiverging` | Gradient norm >1000 | 2m | warning |
| `CalibrationStuck` | Loss не снижается при active runs | 30m | warning |

### slo_alerts.yml — SLO Alerts (5 rules)

Все SLO-алерты используют recording rules из `slo_recording_rules.yml` и фильтруются по `(workflow_id, env)` или `(connector_id, env)`.

| Alert | SLO Target | Условие | for | Severity |
|---|---|---|---|---|
| `SLO_DagSuccessRateBreach` | >=95% | rate30m <0.95 | 10m | warning |
| `SLO_DagSuccessRateCritical` | >=80% | rate30m <0.80 | 5m | critical |
| `SLO_DagLatencyP99High` | <300s | p99 >300s | 15m | warning |
| `SLO_SimulationNanRateBreach` | <0.1% | NaN rate >0.001 | 10m | warning |
| `SLO_ConnectorErrorRateBreach` | <1% | Error rate >0.01 | 10m | warning |

## Recording Rules

### recording_rules.yml — Operational (4 rules, 30s interval)

| Rule | Описание |
|---|---|
| `polisyos:llm_cost_per_hour:rate1h` | Estimated LLM cost в USD/hour |
| `polisyos:workflow_acceptance_rate:rate1h` | Доля успешных workflow runs |
| `polisyos:cas_cache_hit_ratio:rate5m` | CAS cache hit ratio |
| `polisyos:workflow_error_rate:rate5m` | Доля ошибок workflow |

### slo_recording_rules.yml — SLO (8 rules, 30s interval)

| Rule | Описание |
|---|---|
| `polisyos:slo_dag_runs:rate30m` | DAG run throughput by (workflow_id, env) |
| `polisyos:slo_dag_success_rate:rate5m` | DAG success rate 5m window |
| `polisyos:slo_dag_success_rate:rate30m` | DAG success rate 30m window |
| `polisyos:slo_dag_p99_latency_seconds:5m` | DAG p99 latency |
| `polisyos:slo_run_cost_usd_p95:5m` | Run cost p95 |
| `polisyos:slo_simulation_runs:rate30m` | Simulation throughput by env |
| `polisyos:slo_simulation_nan_rate:rate5m` | Simulation NaN rate |
| `polisyos:slo_connector_error_rate:rate5m` | Connector error rate by (connector_id, env) |

SLO recording rules используют `clamp_min(..., 1e-9)` для защиты от деления на ноль.

## Метрики PolicyOS

Все метрики имеют префикс `polisyos_`. Источник: `core/observability/metrics.py`.

**Workflow & Governance:**
- `workflow_runs_total{status, phase}` — counter
- `governance_pass_duration_seconds{pass_id}` — histogram
- `validation_issues_total{severity, pass_id}` — counter

**LLM:**
- `llm_calls_total{model, status}` — counter
- `llm_tokens_total{type}` — counter (type: prompt/completion)

**Simulation & HPC:**
- `simulation_steps_per_second` — gauge
- `simulation_duration_seconds` — histogram
- `simulation_compile_seconds` — histogram (JIT)
- `simulation_batch_size` — histogram
- `artifact_cache_hits_total`, `artifact_cache_misses_total` — counters
- `artifact_io_duration_seconds` — histogram

**Calibration:**
- `calibration_loss` — gauge
- `calibration_grad_norm` — gauge
- `calibration_step_duration_seconds` — histogram

**Connector Resilience:**
- `connector_cache_operations_total{operation, status}` — counter
- `connector_circuit_state{circuit_id}` — gauge (0=closed, 1=open, 2=half_open)
- `connector_circuit_trips_total` — counter
- `connector_retry_attempts_total` — counter
- `connector_rate_limit_throttled_total` — counter
- `connector_fallback_triggered_total`, `connector_fallback_success_total` — counters

**SLO:**
- `slo_dag_runs_total{status, workflow_id, env}` — counter
- `slo_dag_duration_seconds{workflow_id, env}` — histogram
- `slo_run_cost_usd{workflow_id, env}` — histogram
- `slo_simulation_nan_total{method, env}` — counter
- `slo_simulation_runs_total{status, method, env}` — counter
- `slo_connector_requests_total{status, connector_id, env}` — counter

## Кастомизация

**Добавление алерта:** добавить rule в `alerts.yml` (operational) или `slo_alerts.yml` (SLO) с `expr`, `for`, `labels{severity, team}`, `annotations`. Перезапуск: `docker-compose restart prometheus`.

**Изменение порогов:** править числовые значения в `expr`-выражениях alert rules.

**Новый recording rule:** добавить в соответствующий файл, убедиться что interval согласован (30s).

**Отладка:** Prometheus UI `/targets` (scrape status), `/rules` (active rules), `/alerts` (firing alerts), `/graph` (PromQL queries).
