# Helm Charts (`ops/helm`)

`ops/helm` содержит базовые chart'ы для инфраструктурного периметра PolicyOS.

## Состав

| Chart | Роль | Ключевые ресурсы |
|---|---|---|
| `polisyos-cell` | tenant/cell isolation baseline | Namespace + PSS labels, NetworkPolicy, ResourceQuota, RBAC, OPA ConfigMap, Linkerd policy, optional RuntimeClass |
| `spire` | SPIFFE/SPIRE identity plane baseline | SPIRE server Deployment, SPIRE agent DaemonSet, ConfigMap, ServiceAccounts |
| `keycloak` | OIDC identity baseline | Keycloak StatefulSet + Service + Namespace |

## `polisyos-cell` ключевые особенности

- `cell.id` обязателен (`required` в template helpers);
- namespace и имена ресурсов используют первые 8 символов `cell.id`;
- deny-by-default сетевой периметр задается через NetworkPolicy;
- Linkerd `Server`/`AuthorizationPolicy` рендерятся при `linkerd.enabled=true`, `linkerd.strictMtls=true` и наличии `linkerd.servers`;
- `RuntimeClass` для confidential workloads создается только при:
  - `confidentialCompute.enabled=true`;
  - `cell.tier=dedicated`;
- OPA-политики в ConfigMap берутся из `policies/*.rego` chart'а (если файлы присутствуют).

## `spire` особенности

- server использует sqlite в `emptyDir` (базовый вариант, без persistence);
- NodeAttestor настроен на `k8s_psat`;
- agent работает как DaemonSet с `hostNetwork: true`, `hostPID: true` и `hostPath` сокетом.

## `keycloak` особенности

- разворачивается в `start-dev` режиме;
- credential `admin.password` хранится в values;
- persistence/HA/ingress не настроены (baseline для интеграции и dev/test).

## Рекомендуемый порядок развертывания

1. `spire`
2. Linkerd (`ops/scripts/install-linkerd.sh`) при необходимости strict mTLS
3. `keycloak`
4. `polisyos-cell`

## Примеры рендера

```bash
# polisyos-cell
helm template cell-a policy-engine/ops/helm/polisyos-cell \
  --set cell.id=cell-00112233 \
  --set cell.tier=dedicated \
  --set confidentialCompute.enabled=true

# spire
helm template spire policy-engine/ops/helm/spire

# keycloak
helm template keycloak policy-engine/ops/helm/keycloak
```

## Связь с другими директориями

- `ops/opa/` — источник Rego-политик для OPA ConfigMap в `polisyos-cell`;
- `src/polisyos/core/security/identity.py` — runtime интеграция Keycloak + SPIFFE/SPIRE;
- `ops/terraform/modules/confidential_nodepool` — подготавливает узлы для confidential runtime (`kata-cc`, `sev-snp`).
