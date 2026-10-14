# keycloak chart

Baseline Helm chart for Keycloak, the OIDC identity provider used by PolicyOS.

## Role in the System

- issues JWT/OIDC identities for user and service calls;
- is used by the runtime security layer to validate tenant, role, and MFA claims.

## Resources Deployed

- `Namespace` (`infra` by default);
- `StatefulSet` `keycloak`;
- `Service` `keycloak` (port `8080` by default).

## Main Values

| Value                               | Default                            | Purpose                    |
| ----------------------------------- | ---------------------------------- | -------------------------- |
| `namespace`                         | `infra`                            | Installation namespace     |
| `replicas`                          | `1`                                | Number of pods             |
| `image`                             | `quay.io/keycloak/keycloak:26.0.7` | Keycloak image             |
| `service.port`                      | `8080`                             | HTTP port                  |
| `admin.username` / `admin.password` | `admin` / `change-me`              | bootstrap admin credential |
| `resources.*`                       | preset                             | requests/limits            |

## Baseline Limitations

- runs in `start-dev` mode;
- has no ingress, TLS, persistence, or HA;
- the admin password is stored in `values.yaml` (production requires a Secret/Vault flow).

## Related Directories

- `src/polisyos/core/security/identity.py` — runtime JWT validation and required claims.
- `ops/cloud/helm/spire` — extends the identity plane for mTLS/SPIFFE scenarios.

## Quick Commands

```bash
helm template keycloak policy-engine/ops/cloud/helm/keycloak
helm upgrade --install keycloak policy-engine/ops/cloud/helm/keycloak -n infra --create-namespace
kubectl get svc -n infra keycloak
```
