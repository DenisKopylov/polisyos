# Security and Compliance Operations

Related runbooks: [Key Rotation](../runbooks/key-rotation.md),
[Mutation Audit Investigation](../runbooks/mutation-audit-investigation.md).

> This page defines the production operating contract for runtime key rotation,
> CSRF posture, and audit-trail compliance review.

## Secret and Trust-Anchor Rotation

### JWT signing keys

JWT signing keys are normally owned by the identity provider, but runtime must
still know which `kid` values are active, staged, retired, or revoked.

Use the operator manifest command during rollout:

```bash
polisyos security rotate-jwt \
  --manifest .polisyos/security/jwt-trust-anchors.json \
  --issuer https://issuer.example \
  --jwks-uri https://issuer.example/protocol/openid-connect/certs \
  --audience polisyos-web \
  --active-kid kid-2026q2 \
  --next-kid kid-2026q3 \
  --rotated-by platform-oncall \
  --json
```

Runtime enforcement is controlled by:

- `POLISYOS_JWT_ALLOWED_KIDS`: comma-separated active/next `kid` values accepted
  during the rotation window;
- `POLISYOS_JWT_REVOKED_KIDS`: comma-separated `kid` values rejected even when
  present in JWKS;
- `POLISYOS_JWKS_CACHE_TTL_SECONDS`: JWKS client/cache lifetime.

Runtime bootstrap should construct the identity provider from
`SecuritySettings` via `SPIFFEIdentityProvider.from_settings(...)` so these
rotation controls are applied consistently in tests and production.

Operational sequence:

1. Add the new `kid` to `POLISYOS_JWT_ALLOWED_KIDS` before the identity provider
   starts signing with it.
2. Rotate the identity provider signer.
3. Keep the previous `kid` allowed through the compatibility window.
4. Move the previous `kid` out of allowed and into revoked only after the window
   or immediately during compromise response.

### Ed25519 CAS signing keys

Generate and trust a new signer with:

```bash
polisyos security rotate-ed25519 \
  --output ~/.polisyos/keys/signer-2026q3 \
  --identity ci-prod \
  --trust-dir .polisyos/keys/trusted \
  --revoked-dir .polisyos/keys/revoked \
  --identities .polisyos/keys/identities.json \
  --json
```

The command creates a private key with mode `0600`, writes the public key,
copies the public key into the trust store, and updates identity bindings.

## CSRF Policy

Bearer-token runtime deployments do not use CSRF protection because browsers do
not attach bearer tokens automatically across origins.

If runtime enables cookie-authenticated sessions, CSRF protection must be on.
The runtime supports double-submit token enforcement for unsafe methods:

- session cookie: `POLISYOS_SESSION_COOKIE_NAME` (default `polisyos_session`);
- CSRF cookie: `POLISYOS_CSRF_COOKIE_NAME` (default `polisyos_csrf`);
- CSRF header: `POLISYOS_CSRF_HEADER_NAME` (default `X-CSRF-Token`);
- enablement: `POLISYOS_CSRF_ENABLED=true` or
  `POLISYOS_COOKIE_AUTH_ENABLED=true`.

Unsafe cookie-authenticated requests without a matching header fail with
`403 csrf_token_required`.

## Audit Retention and Export

Runtime audit trails live under:

```text
.polisyos/runtime/audit/
  access.jsonl
  mutations.jsonl
```

Retention command:

```bash
polisyos audit runtime-retention \
  --cas-root .polisyos \
  --retention-days 365 \
  --archive-dir .polisyos/runtime/audit/archive \
  --json
```

Entries older than the window are archived as gzip JSONL and removed from the
active stream through atomic rewrite.

## Compliance Queries

Answer "who read / who changed / when / in which tenant" with:

```bash
polisyos audit runtime-query \
  --cas-root .polisyos \
  --tenant-id tenant-a \
  --actor alice@example.gov \
  --since 2026-04-01T00:00:00+00:00 \
  --until 2026-04-12T00:00:00+00:00 \
  --format json \
  --output compliance-report.json
```

Supported filters:

- stream: `access`, `mutation`, or `all`;
- tenant;
- actor;
- resource ID;
- endpoint;
- operation;
- outcome;
- timezone-aware time range.

The JSON report includes both matching entries and summary groupings by actor,
tenant, operation, outcome, and touched resources.
