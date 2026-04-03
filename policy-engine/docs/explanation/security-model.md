# Security Model

## Threat Model

Policy recommendations affect real people, budgets, and regulated decisions. That means the platform cannot rely on notebook-grade security assumptions. The PolicyOS security model is built around zero-trust identity, deny-by-default authorization, tamper-evident artifacts, chained audit, and deployment postures that become stricter in production.

The threat model is therefore broader than "protect the API." It includes unauthorized data access, cross-tenant leakage, artifact tampering, weak provenance, model or supply-chain compromise, and audit gaps that would make a published recommendation impossible to defend after the fact.

## Authentication: JWT

User authentication is based on validated OIDC/JWT claims, while service identity is handled separately through SPIFFE.

- ``UserIdentityClaims`` (`../../src/polisyos/core/security/identity.py`) normalizes user-facing claims into PolicyOS fields such as `sub`, `tenant_id`, `cell_id`, `roles`, `mfa_verified`, `iss`, `aud`, `exp`, and `jti`.
- ``SPIFFEIdentityProvider`` (`../../src/polisyos/core/security/identity.py`) validates JWTs against the configured issuer, JWKS endpoint, and expected audience.
- Role mapping is explicit through `map_roles_from_claims()`, and MFA is derived through `infer_mfa_verified()`.
- Tokens missing `tenant_id`, violating cell binding, or failing MFA requirements for high-privilege roles are rejected.

In other words, PolicyOS mostly delegates issuance to an external IdP such as Keycloak/OIDC, but it performs strict validation, claim normalization, and tenant/cell binding locally.

### Key Rotation

Artifact-signing rotation is documented in [`docs/key-rotation.md`](../key-rotation.md).

- Ed25519 key pairs are generated per rotation window.
- Public keys move through `trusted/` and `revoked/` trust-store directories.
- `identities.json` binds `key_id` fingerprints to signer identities.
- Old keys remain trusted for a grace period and then move to `revoked/`.
- Verification can fail on unsigned, untrusted, revoked, or identity-mismatched artifacts.

## Authorization: OPA

Authorization is policy-as-code and deny-by-default.

- ``OPAClient`` (`../../src/polisyos/core/security/authz.py`) sends structured `AuthzInput` payloads to OPA and caches decisions with a TTL cache.
- When OPA is unreachable, authorization returns `DENY` rather than silently allowing access.
- `AuthzInput` includes request metadata, normalized identity, peer SPIFFE identity, resource tenant, artifact identifiers, PII tier, and anonymization requirements.

The runtime recognizes three authorization modes through `POLISYOS_AUTHZ_MODE`.

- `off`
- `shadow`
- `enforce`

Shadow mode is useful in development because denials are still logged and measured without blocking the request path. Enforce mode is the production posture.

## Identity: SPIFFE

Service-to-service identity is separate from end-user authentication.

- ``ServiceIdentityInfo`` (`../../src/polisyos/core/security/identity.py`) carries verified SPIFFE metadata such as trust domain, cell ID, service name, and certificate lifetime.
- ``SPIFFEIdentityProvider`` (`../../src/polisyos/core/security/identity.py`) parses SPIFFE IDs, verifies peers, and prevents unapproved cross-cell communication.
- `AccessScope.for_service()` binds SPIFFE identity into the same request-scoped authorization context used by OPA and observability.

This split matters because internal service identity should not piggyback on user JWT semantics. The system treats them as different security domains with different proofs.

## Artifact Integrity: CAS and Ed25519

Content-addressable storage already gives PolicyOS tamper evidence through hashes. The signing layer adds authenticity and non-repudiation.

- [`ADR-0010`](../adr/0010-cas-artifact-signing-ed25519.md) defines detached Ed25519 signatures in `<artifact>.sig` sidecars.
- The canonical signed statement covers `artifact_id`, `blob_sha256`, `manifest_sha256`, and `key_id`.
- Verification returns typed statuses such as `valid`, `unsigned`, `invalid`, `untrusted`, `revoked`, or `error`.
- The trust store is externalized under `.polisyos/keys/`.

This creates a usable chain of custody: source ingestion produces CAS artifacts, later analytical stages consume those artifacts by ID, and signature verification can prove not only that the bytes were unchanged, but also which trusted signer produced them.

## Compliance: FedRAMP and NIST 800-53

The FedRAMP documentation in `docs/fedramp/` currently maps PolicyOS to 17 NIST SP 800-53 Rev. 5 controls. The mapping file is [`nist-800-53-mapping.json`](../fedramp/nist-800-53-mapping.json), and the active gap narrative is in [`gap-analysis.md`](../fedramp/gap-analysis.md).

Controls currently marked implemented include:

- `AC-2`, `AC-3`, `AC-4`
- `AU-2`, `AU-10`
- `CM-14`
- `IA-2`
- `RA-5`
- `SC-8`, `SC-28`
- `SI-7`
- `SR-4`

Controls currently tracked as partial include:

- `CA-8`
- `CP-9`
- `IR-4`
- `PL-2`
- `SC-12`

The current POAM in [`poam.json`](../fedramp/poam.json) tracks six open milestones, including HSM-backed root signing, penetration testing, backup/restore evidence, incident-response evidence, and formal ISA agreements for external providers.

## Trusted Execution and Supply Chain

The security model also includes deployment-time hardening beyond JWT and OPA.

- Trusted execution is modeled in ``tee.py`` (`../../src/polisyos/core/security/tee.py`) and enforced through ``TEEGatekeeper`` (`../../src/polisyos/core/security/tee_middleware.py`).
- The current implementation supports attestation models for `sev-snp`, `tdx`, and `nitro`, with strict policy checks on measurement, host data, TCB version, report age, and signature validation.
- SBOM generation and verification live in ``sbom.py`` (`../../src/polisyos/core/security/sbom.py`).
- Supply-chain attestation clients for Fulcio/Rekor and SLSA material live under ``core/security/slsa/`` (`../../src/polisyos/core/security/slsa/`).

This is why the FedRAMP gap analysis now treats the remaining security debt as mostly operational evidence rather than missing architecture primitives.

## Audit Trail

Audit is not an append-only log in name only; it is a chained model with tamper verification.

- ``ChainedAuditSink`` (`../../src/polisyos/core/security/audit_sink.py`) writes append-only local entries and can replicate them to hot and cold tiers.
- ``ChainVerifier`` (`../../src/polisyos/core/security/audit_verifier.py`) checks sequence continuity and hash chaining.
- `AuditEventType` includes governance decisions, access grants and denials, PII detection, signing events, tool events, checkpoints, and general audit actions.
- The audit adapter can attach OpenTelemetry trace and span identifiers so security and execution events stay correlated.

The result is an audit trail that captures data access, authorization outcomes, governance decisions, checkpoint events, and artifact-signing activity in a form that can be verified later for tamper evidence.
