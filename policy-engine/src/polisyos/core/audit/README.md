# Audit — портативные аудит-пакеты и офлайн-верификация

`core.audit` собирает воспроизводимый `.polisyos-audit.tar.gz` пакет из CAS + run metadata и проверяет его без доступа к исходной среде.

Пакет объединяет:

- артефакты и манифесты CAS;
- подписи/публичные ключи;
- provenance (`prov.json` + core graph);
- run/trace metadata;
- standalone verifier + checksums;
- опционально SLSA attestation bundle.

## Основные компоненты

| Файл | Назначение |
|---|---|
| `assembler.py` / `_assembler_*.py` | сборка пакета, provenance merge, deterministic archive |
| `verifier.py` | офлайн проверка целостности/подписей/provenance/SLSA |
| `models.py` | `ExportOptions`, `AuditExportResult`, `VerificationReport` |
| `prov_json.py` | конвертация между core graph и W3C PROV-JSON |
| `report.py` | markdown-render отчета проверки |
| `safe_tar.py` | безопасная распаковка архива |
| `standalone_verifier_template.py` | self-contained Python verifier для пакета |

## Сборка пакета

```python
from pathlib import Path

from polisyos.core.audit import AuditPackageAssembler, ExportOptions, ExportProfile, SigningPolicy

assembler = AuditPackageAssembler(
    cas=store,
    runs_dir=Path("/artifacts/runs"),
    options=ExportOptions(
        profile=ExportProfile.FULL,
        signing_policy=SigningPolicy.WARN,
        include_visualization=True,
    ),
)
result = assembler.export("R_abc123", output_path=Path("audit_output.polisyos-audit.tar.gz"))
```

Что делает assembler:

1. читает `RunManifest` и trace;
2. строит dependency closure через `core.artifacts.graph`;
3. собирает подписи и trust-метаданные;
4. строит merged provenance graph и экспортирует W3C PROV-JSON;
5. при включении добавляет SLSA bundle;
6. формирует checksums + опциональную подпись checksum файла;
7. создает детерминированный tar.gz архив.

## Офлайн-верификация

```python
from pathlib import Path

from polisyos.core.audit import AuditPackageVerifier, render_markdown

verifier = AuditPackageVerifier(trusted_keys_dir=Path(".polisyos/keys/trusted"))
report = verifier.verify(Path("audit_output.polisyos-audit.tar.gz"))
markdown = render_markdown(report)
```

Проверки в `VerificationReport`:

- `Package Integrity`
- `CAS Integrity`
- `Signature Verification`
- `Provenance Validation`
- `Dependency Completeness`
- `SLSA Verification`

## Export/verify параметры

| Опция | Значение |
|---|---|
| `ExportProfile.FULL` | включает blobs + manifests |
| `ExportProfile.MANIFESTS_ONLY` | только manifests и метаданные |
| `SigningPolicy.STRICT` | fail при неподписанных артефактах |
| `SigningPolicy.WARN` | предупреждение при неподписанных |
| `SigningPolicy.SKIP` | пропуск проверки подписей |
| `ExportOptions.slsa_mode/slsa_policy` | включает режим сборки SLSA материалов |

## Зависимости

- `core.artifacts`: CAS/manifest/graph/signing
- `core.run` + `core.trace`: run lifecycle metadata
- `core.contracts.provenance`: canonical provenance graph
- `core.security.slsa`: attestation/signing/transparency (опционально)
