# polisyos-cell chart

Helm chart for isolating a PolicyOS cell through namespaces, network policy, quotas, RBAC, and a policy pack.

## Role in the System

- creates a minimal isolation boundary for a tenant/cell;
- publishes Rego policies as a ConfigMap for an OPA sidecar or OPA service;
- optionally creates a RuntimeClass for the confidential workload path.

## Chart Resources

- `Namespace` with `pod-security.kubernetes.io/*` labels;
- `NetworkPolicy` (deny ingress/egress by default + allow internal + allow configured egress);
- `ResourceQuota`;
- `ServiceAccount` + `Role` + `RoleBinding` (when `rbac.create=true`);
- `ConfigMap` with OPA policies (when `opa.enabled=true`);
- Linkerd `Server` + `AuthorizationPolicy` (when strict mTLS is enabled);
- `RuntimeClass` `kata-cc` (conditional; only for the dedicated confidential tier).

## Key Values

| Value                                    | Required | Default               | Purpose                                              |
| ---------------------------------------- | -------- | --------------------- | ---------------------------------------------------- |
| `cell.id`                                | yes      | `""`                  | Cell identifier used in namespace and resource names |
| `cell.tier`                              | no       | `shared`              | Affects rendering of the confidential RuntimeClass   |
| `networkPolicy.allowedEgress`            | no       | preset DNS/monitoring | Allowed egress                                       |
| `opa.enabled`                            | no       | `true`                | Enables the ConfigMap containing Rego policies       |
| `linkerd.enabled` + `linkerd.strictMtls` | no       | `true` + `true`       | Renders the Linkerd Server/AuthorizationPolicy       |
| `confidentialCompute.enabled`            | no       | `false`               | Enables the `kata-cc` RuntimeClass                   |

## Operational Notes

- `cell.id` is required (`required` in `_helpers.tpl`); the namespace format is `polisyos-cell-<first8(cell.id)>`.
- The `RuntimeClass` requires all of the following:
  - `confidentialCompute.enabled=true`;
  - `cell.tier=dedicated`;
  - nodes with the label `polisyos.io/tee=sev-snp` and taint `polisyos.io/confidential=true:NoSchedule`.
- The Linkerd policy is created from the `linkerd.servers` list; without it, the strict mTLS policy is not rendered.

## OPA Policies and Synchronization

The chart contains a copy of the policies in `policies/*.rego` (tenant boundary, role access, data classification, delegation guard, decision, vulnerability, and deploy).

The source of truth for development is `ops/policy/policies/*.rego`; the chart copy must be synchronized before release.

## Related Directories

- `ops/policy/` — source policy modules and tests.
- `ops/cloud/terraform/modules/confidential_nodepool/` — infrastructure provisioning for the confidential node pool.
- `src/polisyos/core/security/authz.py` and `src/polisyos/runtime/http/authz_middleware.py` — runtime calls to OPA.

## Render Check

```bash
helm template cell-a policy-engine/ops/cloud/helm/polisyos-cell \
  --set cell.id=cell-00112233

helm template cell-dedicated policy-engine/ops/cloud/helm/polisyos-cell \
  --set cell.id=cell-00112233 \
  --set cell.tier=dedicated \
  --set confidentialCompute.enabled=true
```
