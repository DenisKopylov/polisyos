# spire chart

Baseline Helm chart for the SPIFFE/SPIRE identity plane in PolicyOS.

## Role in the System

- establishes the `polisyos.io` trust domain;
- issues SPIFFE identities for services and nodes;
- provides the identity foundation for Linkerd strict mTLS and delegation checks.

## Resources Deployed

- `Namespace` (`spire-system` by default);
- `ServiceAccount` for the server and agent;
- `ConfigMap` `spire-server-config`;
- `Deployment` `spire-server` + `Service` on port `8081`;
- `ConfigMap` `spire-agent-config`;
- `DaemonSet` `spire-agent` (hostNetwork + hostPID + hostPath socket).

## Important Settings

- server datastore: SQLite in `emptyDir` (`/run/spire/data/spire.sqlite3`), with no persistence;
- NodeAttestor: `k8s_psat`, cluster alias `policyos`;
- the server trust domain is set by `server.trustDomain` (default `polisyos.io`).

## Baseline Limitations

- single-replica control plane (not HA);
- no external SQL datastore;
- no separate secret rotation through KMS/HSM.

## Related Directories

- `ops/cloud/helm/install-linkerd.sh` — installs Linkerd with SPIRE as the trust anchor.
- `src/polisyos/core/security/identity.py` — runtime verification of SPIFFE peer identity.
- `ops/cloud/helm/polisyos-cell` — strict mTLS policy for the workload namespace.

## Quick Commands

```bash
helm template spire policy-engine/ops/cloud/helm/spire
helm upgrade --install spire policy-engine/ops/cloud/helm/spire -n spire-system --create-namespace
kubectl get pods -n spire-system
```
