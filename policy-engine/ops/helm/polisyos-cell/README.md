# polisyos-cell chart

Chart для изоляции PolicyOS cell на уровне namespace, сети, quota, RBAC и policy-pack.

## Роль в системе

- формирует минимальный изолированный периметр для tenant/cell;
- публикует Rego-политики как ConfigMap для OPA sidecar/OPA service;
- опционально создает RuntimeClass для confidential workload path.

## Ресурсы chart

- `Namespace` с `pod-security.kubernetes.io/*` labels;
- `NetworkPolicy` (deny ingress/egress by default + allow internal + allow configured egress);
- `ResourceQuota`;
- `ServiceAccount` + `Role` + `RoleBinding` (при `rbac.create=true`);
- `ConfigMap` с OPA policies (при `opa.enabled=true`);
- `Server` + `AuthorizationPolicy` Linkerd (при strict mTLS);
- `RuntimeClass` `kata-cc` (условно, только для dedicated confidential tier).

## Ключевые values

| Value                                    | Обязателен | По умолчанию          | Назначение                                                   |
| ---------------------------------------- | ---------- | --------------------- | ------------------------------------------------------------ |
| `cell.id`                                | да         | `""`                  | идентификатор cell; используется в именах namespace/ресурсов |
| `cell.tier`                              | нет        | `shared`              | влияет на рендер confidential RuntimeClass                   |
| `networkPolicy.allowedEgress`            | нет        | preset DNS/monitoring | разрешенный egress                                           |
| `opa.enabled`                            | нет        | `true`                | включение ConfigMap с Rego-политиками                        |
| `linkerd.enabled` + `linkerd.strictMtls` | нет        | `true` + `true`       | рендер Linkerd Server/AuthorizationPolicy                    |
| `confidentialCompute.enabled`            | нет        | `false`               | включает RuntimeClass `kata-cc`                              |

## Операционные особенности

- `cell.id` обязателен (`required` в `_helpers.tpl`), namespace формата `polisyos-cell-<first8(cell.id)>`.
- Для `RuntimeClass` нужно одновременно:
  - `confidentialCompute.enabled=true`;
  - `cell.tier=dedicated`;
  - ноды с label `polisyos.io/tee=sev-snp` и taint `polisyos.io/confidential=true:NoSchedule`.
- Linkerd policy создается по списку `linkerd.servers`; без него strict mTLS policy не рендерится.

## Политики OPA и синхронизация

Chart содержит копию политик в `policies/*.rego` (tenant boundary, role access, data classification, delegation guard, decision, vulnerability, deploy).

Источник истины для разработки — `ops/opa/policies/*.rego`; перед релизом chart копия должна быть синхронизирована.

## Связи с другими директориями

- `ops/opa/` — исходные policy modules и tests.
- `ops/terraform/modules/confidential_nodepool/` — инфраструктурная подготовка confidential node pool.
- `src/polisyos/core/security/authz.py` и `src/polisyos/runtime/http/authz_middleware.py` — runtime вызовы OPA.

## Проверка рендера

```bash
helm template cell-a policy-engine/ops/helm/polisyos-cell \
  --set cell.id=cell-00112233

helm template cell-dedicated policy-engine/ops/helm/polisyos-cell \
  --set cell.id=cell-00112233 \
  --set cell.tier=dedicated \
  --set confidentialCompute.enabled=true
```
