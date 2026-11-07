# Security and Compliance Operations

Related runbooks: [Key Rotation](../runbooks/key-rotation.md),
[Mutation Audit Investigation](../runbooks/mutation-audit-investigation.md).
Related reference: [Operations reference](operations/index.md), [platform acceptance audit](operations/platform-acceptance-audit.md), [security model](../explanation/security-model.md).

Owner: `@platform-owners`
Source pin: `8dd933600dd7a5a8a5b48432c6089d63b81ca641`
Source of truth: `architecture/control_plane_supply_chain.toml`,
`ops/security/**`, `src/polisyos/core/security/**`,
`src/polisyos/runtime/http/{csrf.py,jwt_auth_middleware.py,authz_middleware.py,fail_closed_middleware.py}`,
and the linked runbooks
Evidence status: source code and configuration were inspected at the source
pin; referenced test paths were checked and selected test bodies inspected, but
tests were not run and no deployment state was observed.

> This page records the repository's production-oriented operating requirements
> and procedures for runtime key rotation, CSRF posture, and audit-trail review.
> It does not attest that a production deployment has these controls configured.

## Evidence Map And Open Gaps

This page describes the operating controls that exist in the current repo. The
compliance evidence and the still-open program gaps live in these tracked
artifacts:

- `docs/fedramp/nist-800-53-mapping.json`
- `docs/fedramp/gap-analysis.md`
- `docs/fedramp/poam.json`
- `docs/archive/reports/platform-acceptance.md`
- `docs/archive/reports/core-runtime-closeout.md`

If a control is only partially evidenced today, the FedRAMP gap analysis or
POAM should remain the source of truth for that gap instead of this page
describing it as fully closed.

## CI Identity And Supply-Chain Policy

Workflow identity is governed by the active control-plane contract:

- default workflow permissions are least-privilege, with top-level
  `contents: read` and job-scoped write permissions only where required;
- every job-scoped write permission is declared in
  `workflow_write_permission`, and `id-token: write` is allowed only for exact
  OIDC-backed jobs such as GitHub Pages deployment, Sigstore/cosign keyless
  signing, and GitHub artifact attestations;
- long-lived cloud provider secrets are forbidden where OIDC, workload
  identity, or managed identity is supported;
- Sentry publication secrets remain an allowed non-cloud exception only in
  conditional main/push CI paths.
- the committed
  `docs/archive/reports/supply-chain-control-crosswalk.json` report maps
  OpenSSF Scorecard, SLSA provenance, SBOM, and signed-artifact controls to
  release phases, artifacts, and workflow evidence.

Run the contract check when workflow identity, signing, SBOM, dependency
scanning, or release provenance changes:

```bash
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py
```

Regenerate the reporting crosswalk after those changes:

```bash
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py \
  --crosswalk-json docs/archive/reports/supply-chain-control-crosswalk.json
```

## Secret and Trust-Anchor Rotation

### JWT signing keys

JWT signing keys are normally owned by the identity provider. The operator
trust-anchor manifest records active, next, retired, and revoked `kid` values;
the runtime verifier enforces the configured allowed and revoked sets.

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

Runtime bootstrap must construct the identity provider from `SecuritySettings`
via `SPIFFEIdentityProvider.from_settings(...)` and pass it to
`create_runtime_api_app(...)` so these rotation controls reach `JWTAuthMiddleware`.
The app requires that injected provider when security middleware is enabled; it
does not create one from settings automatically. This repository-level contract
does not establish that a deployment uses this wiring.

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

The app's explicit `enable_csrf_protection` argument takes precedence. If it is
unset, `POLISYOS_CSRF_ENABLED` takes precedence over
`POLISYOS_COOKIE_AUTH_ENABLED`. Passing `enable_csrf_protection=False` or
setting `POLISYOS_CSRF_ENABLED=false` disables the middleware even when cookie
authentication is enabled. Treat that combination as a production configuration
error.

Unsafe cookie-authenticated requests without a matching header fail with
`403 csrf_token_required`.

## Runtime Auth and Tenant Validation

Security/compliance review for the runtime API should link claims to current
middleware tests rather than only to architecture prose.

<!-- markdownlint-disable MD060 -->

| Control area               | Runtime behavior                                                                  | Validation anchor                                                                    |
| -------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| JWT claim normalization    | bearer tokens populate `request.state.access_scope` and `authenticated_tenant_id` | `tests/unit/core/security/test_auth_middlewares.py`                                       |
| Tenant/header binding      | authenticated tenant and `X-Tenant-ID` mismatch fails closed                      | `tests/unit/core/security/test_auth_middlewares.py`, `tests/unit/core/security/test_router.py` |
| Tenant context discipline  | code requiring tenant scope raises when context is absent                         | `tests/unit/core/security/test_tenant_context.py`                                         |
| Runtime read authorization | cross-tenant run/artifact access returns typed `403` problems                     | `tests/unit/runtime/http/test_runtime_api_authz.py`                                       |
| Property coverage          | run/artifact tenant guards fail closed across generated tenant combinations       | `tests/property/runtime/http/test_access_invariants_properties.py`                       |
| OPA dependency posture     | timeout or denial returns typed deny/timeout responses                            | `tests/unit/runtime/http/test_runtime_api_authz.py`                                       |

<!-- markdownlint-enable MD060 -->

Focused local check:

```bash
uv run pytest -q \
  tests/unit/core/security/test_auth_middlewares.py \
  tests/unit/core/security/test_router.py \
  tests/unit/core/security/test_tenant_context.py \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/property/runtime/http/test_access_invariants_properties.py
```

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

## Source-execution bootstrap boundary

`tools/authority` selects the committed `tools/authority_bootstrap.py` launcher.
The host records selected source execution and hands the captured runner to the
existing confidence-ledger owner. A recorded module, a matching source hash, or
a successful command is not itself an authority verdict. Locked-wheel Python
member selection remains distinct from provider, native, installer-state, and
through-use qualification.

The `diagnose` mode reports the owner diagnostic and observed provider-source
selection. If source selection or capture is unavailable, its profile has
`authority=false` and the owner status is `not_established`; diagnostic exit 0
only means the report was produced. Candidate test work can continue with that
declared limitation. Preserve the failed or unavailable diagnostic rather than
promoting it into a positive protected-action, publication, or custody claim.
The `test` mode explicitly loads the required pytest plugins with automatic
third-party plugin loading disabled; explicit loading does not qualify plugin
authority.

This section records the launcher contract from source inspection. It does not
claim a fresh installed/native execution or close the remaining qualification
boundaries. The source pin at the top of this page applies to the earlier
runtime operations review, not this additional bootstrap description.
