# keycloak chart

Baseline chart для Keycloak (OIDC identity provider) в PolicyOS.

## Роль в системе

- выдает JWT/OIDC identity для пользовательских и сервисных вызовов;
- используется runtime security-слоем для проверки tenant/role/MFA claims.

## Что разворачивает

- `Namespace` (`infra` по умолчанию);
- `StatefulSet` `keycloak`;
- `Service` `keycloak` (порт `8080` по умолчанию).

## Основные values

| Value | По умолчанию | Назначение |
|---|---|---|
| `namespace` | `infra` | namespace установки |
| `replicas` | `1` | количество pod'ов |
| `image` | `quay.io/keycloak/keycloak:26.0.7` | образ Keycloak |
| `service.port` | `8080` | HTTP-порт |
| `admin.username` / `admin.password` | `admin` / `change-me` | bootstrap admin credential |
| `resources.*` | preset | requests/limits |

## Ограничения baseline

- запускается в `start-dev` режиме;
- нет ingress/TLS/persistence/HA;
- admin password хранится в `values.yaml` (для production нужен Secret/Vault flow).

## Связи с другими директориями

- `src/polisyos/core/security/identity.py` — runtime JWT validation и обязательные claims.
- `ops/helm/spire` — дополняет identity plane для mTLS/SPIFFE сценариев.

## Быстрые команды

```bash
helm template keycloak policy-engine/ops/helm/keycloak
helm upgrade --install keycloak policy-engine/ops/helm/keycloak -n infra --create-namespace
kubectl get svc -n infra keycloak
```
