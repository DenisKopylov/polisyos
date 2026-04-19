# ADR-0010: CAS Artifact Signing (Ed25519)

- **Дата**: 2026-02-07
- **Статус**: Accepted
- **Roadmap label**: ADR-006

## Контекст

CAS в Policy OS уже гарантирует integrity (`sha256(blob)`), но не гарантирует authenticity и non-repudiation. Для government/audit сценариев этого недостаточно: артефакты должны иметь криптографически проверяемое происхождение.

## Решение

1. Ввести detached signatures в sidecar файлах `<artifact>.sig` рядом с `<artifact>.blob` и `<artifact>.manifest.json`.
2. Алгоритм подписи: **Ed25519** (через `cryptography`).
3. Подписывать canonical statement со следующими полями:
   - `artifact_id`
   - `blob_sha256`
   - `manifest_sha256`
   - `key_id`
4. Source of truth для подписи: `.sig` файл (manifest не переписывается).
5. Ввести trust store:
   - `.polisyos/keys/trusted/*.pub`
   - `.polisyos/keys/revoked/*.pub`
   - `.polisyos/keys/identities.json` (optional key_id -> identity binding)
6. Верификация возвращает статусную модель:
   `valid | unsigned | invalid | untrusted | revoked | error`.
7. Для bulk операций использовать `ThreadPoolExecutor`.
8. При `sign_on_put=true` подпись выполняется внутри `put_bytes` до возврата (`fail` policy по умолчанию).

## Последствия

### Плюсы

- Поддержка chain-of-custody на уровне CAS артефактов.
- Подготовка к Phase 7 (external audit export) с standalone verification.
- Масштабируемая batch verification/signing модель для CI.

### Минусы

- +1 sidecar файл на артефакт.
- Операционный overhead (trust store, rotation, revocation).

### Риски и митигации

- **Компрометация private key**: key rotation + revoked list.
- **Identity spoofing в signer_identity**: binding по `key_id`, strict identity mode.
- **Unsigned drift при sign_on_put**: fail-hard policy внутри `put_bytes`.

## Альтернативы

- Inline signature в manifest: отклонено (риски mutability/circularity).
- Signature as separate CAS artifact: отклонено (сложный lookup и связь).
- RSA/ECDSA: отклонено из-за размера/сложности/операционных tradeoff для этого use case.

## Related Decisions

- Extended by: ADR-0122 (lakehouse snapshot semantics), ADR-0123
  (ArtifactRef governance metadata), ADR-0128 (hermetic reproducibility).
- Related: ADR-0118 (release train and SemVer contracts).
