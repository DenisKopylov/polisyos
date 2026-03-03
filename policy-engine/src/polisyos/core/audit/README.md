# Audit — переносимые аудит-пакеты

`core.audit` собирает проверяемый пакет `.polisyos-audit.tar.gz` из CAS + run metadata и верифицирует его офлайн.

## Что входит в пакет

- CAS artifacts/manifests (в зависимости от профиля экспорта)
- detached signatures и trusted public keys
- provenance (`prov.json` + merged core graph)
- run metadata (`manifest`, `trace`, `index`)
- checksums + опциональная подпись checksums
- standalone verifier template
- опционально SLSA/SBOM материалы

## Основные модули

| Файл | Роль |
|---|---|
| `assembler.py`, `_assembler_*.py` | сборка дерева пакета и детерминированного tar.gz |
| `verifier.py` | офлайн-проверки целостности, подписей, provenance, SLSA |
| `models.py` | `ExportOptions`, `AuditExportResult`, `VerificationReport` |
| `prov_json.py` | конвертер core graph <-> PROV-JSON |
| `safe_tar.py` | безопасная распаковка архива |
| `report.py` | markdown-рендер отчета |

## Сборка

```python
from pathlib import Path

from polisyos.core.audit import AuditPackageAssembler, ExportOptions, ExportProfile, SigningPolicy

assembler = AuditPackageAssembler(
    cas=store,
    runs_dir=Path(".polisyos/runs"),
    options=ExportOptions(
        profile=ExportProfile.FULL,
        signing_policy=SigningPolicy.WARN,
        include_visualization=True,
    ),
)

result = assembler.export("R_abc123", output_path=Path("audit_output.polisyos-audit.tar.gz"))
```

Профили:
- `FULL`: blobs + manifests + metadata
- `MANIFESTS_ONLY`: без blobs

Политики подписи:
- `STRICT`, `WARN`, `SKIP`

## Верификация

```python
from pathlib import Path

from polisyos.core.audit import AuditPackageVerifier, render_markdown

verifier = AuditPackageVerifier(trusted_keys_dir=Path(".polisyos/keys/trusted"))
report = verifier.verify(Path("audit_output.polisyos-audit.tar.gz"))
print(render_markdown(report))
```

Проверки в отчете:
- `Package Integrity`
- `CAS Integrity`
- `Signature Verification`
- `Provenance Validation`
- `Dependency Completeness`
- `SLSA Verification`

## Связи с core

- `core.artifacts`: source of truth для artifacts/manifests/signatures/graph
- `core.run` + `core.trace`: lifecycle metadata
- `core.contracts.provenance`: merged provenance model
- `core.security.slsa`: attestation/transparency интеграция (опционально)
