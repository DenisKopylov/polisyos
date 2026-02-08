# OPA Policies (Phase 2 Zero Trust)

Rego policies for per-request authorization in PolicyOS.

## Files

- `policies/tenant_boundary.rego` — hard tenant boundary checks.
- `policies/role_access.rego` — method/path RBAC checks.
- `policies/data_classification.rego` — PII-tier checks and allowed column derivation.
- `policies/delegation_guard.rego` — delegation safety checks for inter-service user context.
- `policies/decision.rego` — composite decision entrypoint used by runtime middleware.

## Evaluation entrypoint

The runtime OPA client calls:

- `data.polisyos.authz.decision`

Expected fields in decision result:

- `allow` (boolean)
- `deny_reasons` (set/list)
- `audit_entry` (object)
- `allowed_columns` (set, when applicable)

## Policy tests

Run Rego unit tests locally:

```bash
opa test ops/opa/policies -v
```
