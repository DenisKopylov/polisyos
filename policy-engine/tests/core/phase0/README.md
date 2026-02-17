# Core Phase0 Tests

`tests/core/phase0` покрывает фундаментальные примитивы `polisyos.core`: CAS/артефакты, canonical JSON, signing, run context и observability.

Актуально на **17 февраля 2026**.

## Состав

- `21` файл `test_*.py`
- `1` `conftest.py`

## Ключевые группы

### CAS и артефакты

- `test_artifact_store.py`
- `test_artifact_export_import.py`
- `test_artifact_graph.py`
- `test_provenance_contract_shims.py`

Проверяются: content-addressing, экспорт/импорт, граф связей артефактов, совместимость provenance-контрактов.

### Подпись и доверие

- `test_signing.py`
- `test_store_signing.py`
- `test_cli_signing.py`

Проверяются: Ed25519 signing/verify, sidecar-подписи в CAS, CLI-поток keygen/sign/verify.

### Canon / environment / run lifecycle

- `test_canon_json.py`
- `test_environment_manifest.py`
- `test_run_context.py`
- `test_registry_bundle.py`
- `test_cli.py`, `test_cli_resume.py`

Проверяются: детерминизм канона, воспроизводимость окружения, контекст запуска, registry bundle, базовые CLI сценарии.

### Audit и наблюдаемость

- `test_audit_export_verify.py`
- `test_audit_manifest_compat.py`
- `test_tracer.py`, `test_metrics.py`, `test_logs.py`
- `test_decorators.py`, `test_propagation.py`, `test_observability.py`

Проверяются: audit export/verify контракты, OTEL-трассировка, метрики, корреляция логов и propagation trace context.

## Связи с другими директориями

- `policy-engine/src/polisyos/core/artifacts`
- `policy-engine/src/polisyos/core/canon`
- `policy-engine/src/polisyos/core/observability`
- `policy-engine/src/polisyos/core/run`

## Запуск

```bash
pytest tests/core/phase0 -q

# точечно
pytest tests/core/phase0/test_artifact_store.py -q
pytest tests/core/phase0/test_canon_json.py -q
pytest tests/core/phase0/test_observability.py -q
```
