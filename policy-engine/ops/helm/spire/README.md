# spire chart

Baseline chart для SPIFFE/SPIRE identity plane в PolicyOS.

## Роль в системе

- поднимает trust domain `polisyos.io`;
- выдает SPIFFE identities для сервисов и нод;
- обеспечивает identity foundation для Linkerd strict mTLS и delegation checks.

## Что разворачивает

- `Namespace` (`spire-system` по умолчанию);
- `ServiceAccount` для server/agent;
- `ConfigMap` `spire-server-config`;
- `Deployment` `spire-server` + `Service` на `8081`;
- `ConfigMap` `spire-agent-config`;
- `DaemonSet` `spire-agent` (hostNetwork + hostPID + hostPath socket).

## Важные настройки

- datastore server: sqlite в `emptyDir` (`/run/spire/data/spire.sqlite3`), без persistence;
- NodeAttestor: `k8s_psat`, cluster alias `policyos`;
- server trust domain задается `server.trustDomain` (default `polisyos.io`).

## Ограничения baseline

- single-replica control plane (не HA);
- без внешнего SQL datastore;
- без отдельной ротации секретов через KMS/HSM.

## Связи с другими директориями

- `ops/scripts/install-linkerd.sh` — установка Linkerd в режиме SPIRE trust anchor.
- `src/polisyos/core/security/identity.py` — runtime проверка SPIFFE peer identity.
- `ops/helm/polisyos-cell` — strict mTLS policy для workload namespace.

## Быстрые команды

```bash
helm template spire policy-engine/ops/helm/spire
helm upgrade --install spire policy-engine/ops/helm/spire -n spire-system --create-namespace
kubectl get pods -n spire-system
```
