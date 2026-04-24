# OPA Policies (`ops/opa`)

`ops/opa` хранит policy-as-code для двух контуров: runtime authorization и deploy security gate.

## Роль в системе

- runtime authz: решение `allow/deny` для API-запросов;
- deploy gate: блокировка deployment при критичных SBOM/CVE рисках;
- единый audit contract (`audit_entry`, `deny_reasons`) для security telemetry.

## Состав

- `policies/*.rego` — 7 policy modules;
- `policies/*_test.rego` — 7 unit tests.

## Entry points

| Контур        | Data path                       | HTTP path                           |
| ------------- | ------------------------------- | ----------------------------------- |
| Runtime authz | `data.polisyos.authz.decision`  | `/v1/data/polisyos/authz/decision`  |
| Deploy gate   | `data.polisyos.deploy.decision` | `/v1/data/polisyos/deploy/decision` |

## Модули

- `tenant_boundary.rego` — изоляция tenant контекста.
- `role_access.rego` — RBAC по method/path + MFA guard для sensitive path.
- `data_classification.rego` — PII ceiling, anonymization, `allowed_columns`.
- `delegation_guard.rego` — проверка делегации через peer SPIFFE identity.
- `decision.rego` — композитный runtime entrypoint.
- `vulnerability.rego` — SBOM/CVE threshold + allowed CVE exceptions.
- `deploy.rego` — композитный deploy entrypoint.

## Интеграции

- `src/polisyos/core/security/authz.py` формирует input contract (`AuthzInput.to_opa_input`) и вызывает OPA.
- `src/polisyos/runtime/http/authz_middleware.py` применяет authz decision на runtime-пути.
- `src/polisyos/core/security/sbom.py` поставляет данные для deploy gate.

## Операционные заметки

- `OPAClient` в runtime работает fail-closed при ошибках OPA.
- Копия политик для Kubernetes packaging находится в `ops/helm/polisyos-cell/policies` и должна быть синхронна с `ops/opa/policies`.

## Проверка

```bash
opa test policy-engine/ops/opa/policies -v
```
