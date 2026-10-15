# Helm Charts (`ops/cloud/helm`)

`ops/cloud/helm` contains baseline charts for the PolicyOS infrastructure perimeter.

## Contents

| Chart           | Purpose                         | Key resources                                                                                       |
| --------------- | ------------------------------- | --------------------------------------------------------------------------------------------------- |
| `polisyos-cell` | tenant/cell isolation baseline  | Namespace, NetworkPolicy, ResourceQuota, RBAC, OPA ConfigMap, Linkerd policy, optional RuntimeClass |
| `spire`         | SPIFFE/SPIRE identity plane     | server Deployment, agent DaemonSet, ConfigMap, ServiceAccounts                                      |
| `keycloak`      | OIDC identity provider baseline | Keycloak StatefulSet + Service + Namespace                                                          |

## Application Order

1. `spire`
2. Linkerd (when using strict mTLS)
3. `keycloak`
4. `polisyos-cell`

## Integrations

- `ops/policy/` — source of the Rego policies packaged into the `polisyos-cell` ConfigMap.
- `ops/cloud/terraform/modules/confidential_nodepool` — prepares nodes, taints, and labels for the confidential RuntimeClass used by `polisyos-cell`.
- `src/polisyos/core/security/identity.py` — runtime validation of identities from Keycloak and SPIFFE/SPIRE.

## Quick Rendering

```bash
helm template spire policy-engine/ops/cloud/helm/spire
helm template keycloak policy-engine/ops/cloud/helm/keycloak
helm template cell-a policy-engine/ops/cloud/helm/polisyos-cell --set cell.id=cell-00112233
```

## Chart Details

- [polisyos-cell/README.md](polisyos-cell/README.md)
- [spire/README.md](spire/README.md)
- [keycloak/README.md](keycloak/README.md)
