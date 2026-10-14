# Key Rotation for CAS Artifact Signing

Related ADR: [ADR-0102](adr/0102-key-rotation-lifecycle-and-trust-store-policy.md).
Related runbook: [Key Rotation](runbooks/key-rotation.md).

Owner: `@platform-owners`
Source of truth: `policy-engine/src/polisyos/core/security/rotation.py`, `policy-engine/src/polisyos/core/components/_cli_security.py`, `policy-engine/src/polisyos/core/artifacts/signing.py`, and [Security and Compliance Operations](reference/security-compliance.md).

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

1. Проверьте deployment-specific trust store, подписывающий secret и область CAS; этот документ не сообщает текущее состояние ключей в deployment.
2. Сгенерируйте ключ и добавьте его публичную часть в trust store штатным CLI:

   ```bash
   polisyos security rotate-ed25519 \
     --output ~/.polisyos/keys/new-signer \
     --identity ci-prod
   ```

   На source pin ниже команда создаёт пару ключей, записывает private key с mode `0600`, копирует public key в `trusted/` и обновляет `identities.json`. По умолчанию эти каталоги находятся относительно текущего рабочего каталога в `.polisyos/keys/`; укажите абсолютные пути для другого deployment (CLI не раскрывает `~` в `--trust-dir`, `--revoked-dir` и `--identities`). Команда не переключает CI/runtime secret и не доказывает, что выбранный deployment принял новый ключ.
3. Передайте новый private key в управляемый secret store и переключите signer отдельной контролируемой операцией. Не коммитьте ключ.
4. Подписывайте только назначенную область. `polisyos sign --all` затрагивает все unsigned артефакты в выбранном CAS, а не только новые артефакты; укажите и проверьте правильный CAS scope.
5. При плановой ротации сохраняйте старый public key в `trusted/` на весь согласованный release/grace period.
6. После grace period поместите старый public key в `revoked/` и сохраните запись о периоде действия. Verifier проверяет revoked key до trusted key. Опция `--revoke-public-key` у `polisyos security rotate-ed25519` копирует указанный ключ в `revoked/`, но не удаляет его копию из `trusted/`; каждый запуск также создаёт и доверяет новый ключ, поэтому не используйте повторный запуск только для отзыва, если новая ротация не назначена.
7. Проверьте нужные артефакты с `--strict-identity`. Полный `polisyos verify --all --fail-unsigned --strict-identity` охватывает весь выбранный CAS и завершится ошибкой, если среди них есть unsigned, revoked, untrusted, invalid записи или ошибки проверки. После отзыва исторические подписи старым ключом могут быть revoked; заранее определите ожидаемую область и не трактуйте ненулевой результат полного обхода как доказательство отказа нового signer.

## Operational Notes

- Private keys не коммитятся в репозиторий.
- Для локальной разработки private key должен иметь mode `0600`.
- `signer_identity` в `.sig` используется как hint; доверие определяется `key_id` из trust store.
- В строгом режиме (`--strict-identity`) mismatch между `signer_identity` и `identities.json` считается ошибкой.

Source inspection: `policy-engine/src/polisyos/core/security/rotation.py`, `policy-engine/src/polisyos/core/components/_cli_security.py`, `policy-engine/src/polisyos/core/components/_cli_crypto.py`, `policy-engine/src/polisyos/core/artifacts/signing.py`, and `policy-engine/tools/ops_runners/runtime_cli.py` at `8dd933600dd7a5a8a5b48432c6089d63b81ca641` (2026-10-14). Code inspected; CLI operations and tests were not run. These instructions describe a procedure, not evidence of a completed deployment rotation.
