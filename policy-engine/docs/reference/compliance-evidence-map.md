# Compliance Evidence Map
Related reference: [Security and Compliance Operations](security-compliance.md),
[Operations](operations/index.md).

Freshness: 2026-04-17
Owner: `@platform-owners`
Backup owner: `@runtime-owners`
Source of truth: `docs/reference/security-compliance.md`, runtime/core security
code, repo-tracked workflows, and the tests/runbooks linked below

> Evidence map for security/compliance review: where a control claim lives in
> docs, code, tests, workflows, and retained operational artifacts.

## How To Use This Page

For one control area, collect all of:

1. the primary reference page;
2. the code surface that actually enforces it;
3. the validation anchor;
4. the retained evidence or runbook used during an incident/review.

## Control Matrix

| Control area | Primary docs | Code surface | Validation anchor | Evidence / runbook |
|---|---|---|---|---|
| JWT/OIDC identity and tenant binding | [Security and Compliance Operations](security-compliance.md) | `src/polisyos/runtime/http/{jwt_auth_middleware.py,authz_middleware.py,fail_closed_middleware.py}` | `tests/core/security/test_auth_middlewares.py`, `tests/core/security/test_router.py`, `tests/core/security/test_tenant_context.py`, `tests/runtime/http/test_runtime_api_authz.py` | [runtime-api-outage.md](../runbooks/runtime-api-outage.md), platform acceptance evidence |
| Artifact signing and trust anchors | [Security and Compliance Operations](security-compliance.md), [Key Rotation](../runbooks/key-rotation.md) | `src/polisyos/core/security/**` | `tests/core/phase0/test_cli_signing.py`, `tests/core/phase0/test_store_signing.py`, `.github/workflows/signatures.yml` | [artifact-signing-sbom-failure.md](../runbooks/artifact-signing-sbom-failure.md) |
| SBOM and supply-chain posture | [Security and Compliance Operations](security-compliance.md) | `src/polisyos/core/security/sbom.py`, release/build workflow surfaces | `tests/core/security/test_sbom.py`, `.github/workflows/build-and-push.yml`, `.github/workflows/signatures.yml` | committed audit/report artifacts and SBOM failure runbook |
| Runtime authorization fail-closed behavior | [Security and Compliance Operations](security-compliance.md), [Security Model](../explanation/security-model.md) | `src/polisyos/runtime/http/authz_middleware.py`, `src/polisyos/runtime/http/security.py` | `tests/runtime/http/test_runtime_api_authz.py`, `tests/runtime/http/test_access_invariants_properties.py` | [cas-opa-outage.md](../runbooks/cas-opa-outage.md) |
| Audit retention, replay, and restore | [Retention and Recovery](operations/retention-and-recovery.md) | artifact/audit retention code and archive tooling | replay and archive drills, acceptance/recovery checks | [replay-or-restore.md](../runbooks/replay-or-restore.md), [retained-artifact-recovery.md](../runbooks/retained-artifact-recovery.md) |
| Platform acceptance and release evidence | [Platform Acceptance Audit](operations/platform-acceptance-audit.md), [Operate the CI/CD Platform](../how-to/operate-ci-cd-platform.md) | `tools/devx/workspace/acceptance_audit.py`, workflow inventory | `python3 -m tools.cli workspace acceptance-audit`, repo-tracked workflow runs | `docs/archive/reports/platform-acceptance.*` |

## Minimal Review Packet

When you need a quick review packet for one control family, start with:

```bash
cd policy-engine
python3 -m tools.cli workspace doctor --surface runtime-signing --surface runtime-oidc
uv run pytest -q \
  tests/core/phase0/test_cli_signing.py \
  tests/core/phase0/test_store_signing.py \
  tests/core/security/test_sbom.py \
  tests/core/security/test_tenant_context.py \
  tests/runtime/http/test_runtime_api_authz.py \
  tests/runtime/http/test_access_invariants_properties.py
```

Then add the linked runbook or retained evidence pack for the control area under
review.
