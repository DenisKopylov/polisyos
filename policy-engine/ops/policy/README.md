# OPA Policies (`ops/policy`)

- Owner: `team-security`
- Artifact type: `policy-as-code`

`ops/policy` contains policy-as-code for two areas: runtime authorization and the deployment security gate.

## Role in the System

- runtime authorization: `allow/deny` decisions for API requests;
- deployment gate: blocks deployments when SBOM/CVE risks are critical;
- shared audit contract (`audit_entry`, `deny_reasons`) for security telemetry.

## Contents

- `ops/policy/policies/` is the canonical inventory of tracked Rego policy
  and rule-test source files. Files ending in `_test.rego` are test modules;
  their file count does not represent the number of Rego test cases.

## Entry points

| Area          | Data path                       | HTTP path                           |
| ------------- | ------------------------------- | ----------------------------------- |
| Runtime authz | `data.polisyos.authz.decision`  | `/v1/data/polisyos/authz/decision`  |
| Deploy gate   | `data.polisyos.deploy.decision` | `/v1/data/polisyos/deploy/decision` |

## Modules

- `tenant_boundary.rego` — tenant-context isolation.
- `role_access.rego` — RBAC by method/path plus an MFA guard for sensitive paths.
- `data_classification.rego` — PII ceiling, anonymization, `allowed_columns`.
- `delegation_guard.rego` — validates delegation through peer SPIFFE identity.
- `decision.rego` — composite runtime entry point.
- `vulnerability.rego` — SBOM/CVE threshold + allowed CVE exceptions.
- `deploy.rego` — composite deployment entry point.

## Integrations

- `src/polisyos/core/security/authz.py` builds the input contract (`AuthzInput.to_opa_input`) and calls OPA.
- `src/polisyos/runtime/http/authz_middleware.py` applies the authorization decision on runtime paths.
- `src/polisyos/core/security/sbom.py` supplies data to the deployment gate.

## Operational Notes

- `OPAClient` fails closed at runtime when OPA returns an error.
- The policy copy packaged for Kubernetes is in `ops/cloud/helm/polisyos-cell/policies` and must stay synchronized with `ops/policy/policies`.

## Checks

```bash
opa test policy-engine/ops/policy/policies -v
```
