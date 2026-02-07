# Key Rotation for CAS Artifact Signing

## Scope

Документ описывает ротацию Ed25519 ключей для подписи CAS артефактов (Phase 6).

## Trust Store Layout

```text
.polisyos/keys/
  trusted/
    signer-2026q1.pub
    signer-2026q2.pub
  revoked/
    signer-2025q4.pub
  identities.json
```

`identities.json`:

```json
{
  "sha256:<full_key_fingerprint>": "ci-prod"
}
```

## Rotation Procedure

1. Сгенерировать новую пару:
   `polisyos keygen --output ~/.polisyos/keys/signer-2026q2`
2. Добавить новый публичный ключ в `trusted/`.
3. Обновить CI secret `POLISYOS_SIGNING_KEY` новым private key PEM.
4. Обновить `identities.json` (новый `key_id -> identity`).
5. Подписывать новые артефакты новым ключом (`polisyos sign --all`).
6. Оставить старый публичный ключ в `trusted/` минимум на один release cycle.
7. После grace period перенести старый публичный ключ в `revoked/`.
8. Проверить, что `polisyos verify --all --fail-unsigned` не содержит `untrusted/revoked` для активного периода.

## Operational Notes

- Private keys не коммитятся в репозиторий.
- Для локальной разработки private key должен иметь mode `0600`.
- `signer_identity` в `.sig` используется как hint; доверие определяется `key_id` из trust store.
- В строгом режиме (`--strict-identity`) mismatch между `signer_identity` и `identities.json` считается ошибкой.
