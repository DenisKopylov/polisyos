# Helm Charts (`ops/helm`)

`ops/helm` содержит базовые chart'ы инфраструктурного периметра PolicyOS.

## Что здесь

| Chart | Назначение | Ключевые ресурсы |
|---|---|---|
| `polisyos-cell` | tenant/cell isolation baseline | Namespace, NetworkPolicy, ResourceQuota, RBAC, OPA ConfigMap, Linkerd policy, optional RuntimeClass |
| `spire` | SPIFFE/SPIRE identity plane | server Deployment, agent DaemonSet, ConfigMap, ServiceAccounts |
| `keycloak` | OIDC identity provider baseline | Keycloak StatefulSet + Service + Namespace |

## Порядок применения

1. `spire`
2. Linkerd (при использовании strict mTLS)
3. `keycloak`
4. `polisyos-cell`

## Интеграции

- `ops/opa/` — источник Rego-политик, которые пакуются в `polisyos-cell` ConfigMap.
- `ops/terraform/modules/confidential_nodepool` — подготавливает ноды/taints/labels для confidential RuntimeClass из `polisyos-cell`.
- `src/polisyos/core/security/identity.py` — runtime-валидация identity из Keycloak и SPIFFE/SPIRE.

## Быстрый рендер

```bash
helm template spire policy-engine/ops/helm/spire
helm template keycloak policy-engine/ops/helm/keycloak
helm template cell-a policy-engine/ops/helm/polisyos-cell --set cell.id=cell-00112233
```

## Подробности по chart'ам

- [polisyos-cell/README.md](polisyos-cell/README.md)
- [spire/README.md](spire/README.md)
- [keycloak/README.md](keycloak/README.md)
