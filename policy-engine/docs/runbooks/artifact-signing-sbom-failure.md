# Artifact Signing or SBOM Failure

Related explanation: [Security Model](../explanation/security-model.md). Related
reference: [Ownership](../reference/ownership.md). Related how-to:
[Installation](../how-to/install.md).

> Используйте этот runbook, когда ломается artifact signing, audit package
> verification, SBOM generation/verification либо SLSA payload validation.

Owner: `@platform-owners`
Last tested: `2026-04-17` against current signing/SBOM regressions and release-evidence docs.
Evidence path: `docs/reference/security-compliance.md`; `docs/archive/reports/platform-acceptance.md`; `tests/core/security/test_sbom.py`
Rollback path: return to the last trusted signer and trust-store state, block promotion, and only time-box any temporary allowlist or grace-window exception.

## Symptom

- `runtime-signing` surface не проходит в `polisyos-tools workspace doctor`;
- CI/release gate сообщает про unsigned artifacts, invalid signature, untrusted
  key или revoked signer;
- Sigstore/cosign verification of release assets or `SHA256SUMS` fails;
- SBOM gate уходит в deny, появляются `critical` CVE или растёт
  `polisyos_sbom_deployment_gate_total{decision="deny"}`;
- audit verifier жалуется на отсутствие `slsa/attestation.json`,
  `slsa/signature.json` или `provenance/prov.json`.

## Likely Causes

- отсутствует или неверен `POLISYOS_SIGNING_KEY` /
  `POLISYOS_SIGNING_KEY_FILE`;
- GitHub OIDC-based Sigstore signing step не получил identity token или был
  выполнен вне canonical release workflow;
- trust store и `identities.json` не синхронизированы после rotation;
- артефакт был собран вне canonical signing path;
- `cyclonedx-py`, `syft` или `grype` недоступны либо дали malformed output;
- vulnerability threshold или allowlist изменились и начали deny законно.

## Timeline Capture Expectations

Зафиксируйте:

- UTC timestamp первого failed verification;
- commit/release candidate/build ID;
- exact failing step: signing, provenance, SLSA, SBOM generation или SBOM gate;
- какой artifact family затронут: CAS blobs, audit package, release bundle,
  runtime image;
- key ID, signer identity, trust-dir revision и vulnerability threshold;
- если deny связан с CVE, зафиксируйте package, version, CVE ID и CVSS.

## First Triage Steps

1. Подтвердите optional surface readiness:

   ```bash
   cd policy-engine
   uv run polisyos-tools workspace doctor --surface runtime-signing
   ```

2. Проверьте signing inputs:

   - что private key доступен и читается текущим process;
   - что trusted и revoked key sets актуальны;
   - что rotation не оставила старый key активным после revoke.
   - что Sigstore signing сохранил `.sig` и `.pem` sidecars рядом с release
     assets.

3. Прогоните focused security tests:

   ```bash
   cd policy-engine
   uv run pytest \
     tests/core/phase0/test_cli_signing.py \
     tests/core/phase0/test_store_signing.py \
     tests/core/security/test_sbom.py
   ```

4. Если проблема в audit package, проверьте наличие:

   - `provenance/prov.json`
   - `slsa/attestation.json`
   - `slsa/signature.json`
   - signature sidecars under `signatures/sha256/`

5. Если это SBOM deny, отделите tooling failure от legitimate vulnerability:
   сначала проверьте, сломан ли generator/scanner, затем решайте, нужен ли
   allowlist или dependency patch.

## Rollback / Mitigation

- если signing path сломан tooling/config drift-ом, вернитесь к последнему
  known-good signer config и trust store;
- если проблема в key rotation, временно оставьте предыдущий public key trusted
  до завершения grace period;
- если SBOM deny законный, не продвигайте promotion; fix or pin dependency
  вместо bypass;
- временный allowlist CVE допустим только по security review и с expiry date;
- отсутствие provenance/signature никогда не замалчивается ad hoc “green button”.

## Escalation Owner

- primary: `@platform-owners`;
- security review and policy approval: security/compliance owner path;
- supporting: subsystem owner, если unsigned artifacts produced only there.

## Follow-up Checklist

- доказано, был ли failure tooling-related или policy-correct;
- rotation artifacts и trust store synchronized;
- allowlist, если применялся, имеет owner и expiry date;
- post-incident обновлён [Key Rotation](../key-rotation.md), если именно он был
  источником drift;
- security alert routing и dashboard ownership актуализированы.

## Blameless Postmortem

### What Went Well

- какой verifier или metric дал first accurate signal;
- какие safeguards остановили bad artifact до promotion;
- где trust model оказалась понятной и проверяемой.

### What Went Poorly

- где signing/SBOM path зависел от tacit knowledge;
- какие env vars, keys или trust files были слишком неявными;
- где policy обходили вручную вместо понятного runbook path.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Fix the broken signing, verification, or SBOM generation path | `@platform-owners` | YYYY-MM-DD | open |
| Remove or time-box any temporary exception introduced during mitigation | security owner | YYYY-MM-DD | open |
| Improve visibility of trust store, provenance, or vulnerability gating | `@platform-owners` | YYYY-MM-DD | open |
