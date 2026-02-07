# Audit — Портативные аудит-пакеты

Сборка и офлайн-верификация портативных аудит-пакетов (`.polisyos-audit.tar.gz`) с полным provenance tracking в формате W3C PROV-JSON. Пакет содержит все артефакты, подписи, метаданные запуска и standalone-верификатор.

## Архитектура

```
audit/
├── assembler.py                     # AuditPackageAssembler — сборка пакетов из CAS и run metadata
├── verifier.py                      # AuditPackageVerifier — офлайн-верификация (5 шагов)
├── models.py                        # ExportOptions, VerificationReport, StepResult, enums
├── prov_json.py                     # ProvJsonConverter — конвертация в W3C PROV-JSON, DOT
├── report.py                        # render_markdown() — markdown-отчет верификации
├── safe_tar.py                      # safe_extract_tar() — безопасная распаковка архивов
└── standalone_verifier_template.py  # Self-contained Python верификатор (без зависимостей от polisyos)
```

## AuditPackageAssembler

Собирает портативный пакет из CAS-артефактов и метаданных запуска:

```python
from polisyos.core.audit import AuditPackageAssembler, ExportOptions, ExportProfile, SigningPolicy

assembler = AuditPackageAssembler(
    cas=store,
    runs_dir=Path("/artifacts/runs"),
    options=ExportOptions(
        profile=ExportProfile.FULL,           # FULL или MANIFESTS_ONLY
        signing_policy=SigningPolicy.WARN,     # STRICT, WARN, SKIP
        include_visualization=True,
    ),
)
result = assembler.export("R_abc123", output_path=Path("audit_output.tar.gz"))
```

**Что делает:**
1. Загружает RunManifest (из manifest.json или trace.jsonl)
2. Разрешает transitive closure зависимостей через `resolve_dependency_graph`
3. Собирает Ed25519-подписи и публичные ключи
4. Строит merged provenance graph из CAS-манифестов и trace events
5. Конвертирует в W3C PROV-JSON
6. Генерирует детерминированный `.polisyos-audit.tar.gz`

**Структура пакета:**
```
├── index.json                        # Индекс: метаданные, статистика, файлы
├── artifacts/sha256/                  # CAS-артефакты (.blob + .manifest.json)
├── signatures/sha256/                 # Detached Ed25519 подписи (.sig)
├── signatures/public_keys/            # Публичные ключи + identities.json
├── provenance/prov.json               # W3C PROV-JSON
├── provenance/prov-core.json          # ProvenanceCoreGraph
├── metadata/run_manifest.json         # Run metadata
├── metadata/trace.jsonl               # Trace записи
├── visualization/provenance_graph.dot # Graphviz DOT (+ SVG если dot доступен)
└── verification/                      # verify.py, checksums.sha256, instructions.md
```

## AuditPackageVerifier

Офлайн-верификация пакета — 5 шагов:

```python
from polisyos.core.audit import AuditPackageVerifier

verifier = AuditPackageVerifier(
    trusted_keys_dir=Path(".polisyos/keys/trusted"),
    allow_package_keys=False,  # не доверять ключам из пакета
    fail_unsigned=False,
)
report = verifier.verify(Path("audit_output.polisyos-audit.tar.gz"))
print(report.overall_status)  # "PASS" или "FAIL"
```

**Шаги верификации:**

| Шаг | Проверяет |
|-----|-----------|
| Package Integrity | checksums.sha256, index.json файлы, подпись checksums |
| CAS Integrity | SHA256 блобов == artifact_id, размеры, manifest integrity |
| Signature Verification | Ed25519 подписи vs trusted keys, signer identity |
| Provenance Validation | PROV-JSON структура, dangling entities, циклы в wasDerivedFrom |
| Dependency Completeness | Полнота closure — все usedEntity/generatedEntity присутствуют |

## VerificationReport

```python
from polisyos.core.audit import render_markdown

report = verifier.verify(package_path)
markdown = render_markdown(report)  # Человекочитаемый markdown-отчет
```

**Поля:** `overall_status`, `package_integrity`, `cas_integrity`, `signature_verification`, `provenance_validation`, `dependency_completeness`, `failures`, `warnings`, `environment`.

## W3C PROV-JSON

Конвертация ProvenanceCoreGraph в стандартный W3C PROV-JSON:

```python
from polisyos.core.audit import ProvJsonConverter, prov_json_to_dot

converter = ProvJsonConverter(run_id="R_abc123", include_bundle=True)
prov_json = converter.convert(core_graph)
dot_content = prov_json_to_dot(prov_json)  # для Graphviz
```

## Конфигурация

| Параметр | Описание |
|----------|----------|
| `ExportProfile.FULL` | Включить blob-файлы артефактов |
| `ExportProfile.MANIFESTS_ONLY` | Только манифесты (меньший размер) |
| `SigningPolicy.STRICT` | Fail если есть неподписанные артефакты |
| `SigningPolicy.WARN` | Warning для неподписанных |
| `SigningPolicy.SKIP` | Игнорировать подписи |

## Зависимости

- `core.artifacts` — CAS, signing, graph, manifest
- `core.run` — RunManifest
- `core.trace` — TraceRecord (парсинг trace.jsonl)
- `core.canon` — десериализация артефактов
- `fabric.provenance.core` — ProvenanceCoreGraph, entity/activity/agent types
- `runtime.manifest` — Legacy RunManifest (fallback)
