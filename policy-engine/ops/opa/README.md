# OPA Policies (`ops/opa`)

Rego-политики для runtime authorization и deploy gate в PolicyOS.

## Что здесь есть

- `policies/*.rego` — 7 policy-модулей.
- `policies/*_test.rego` — 7 unit-тестов.

## Точки входа (entrypoints)

- Runtime authz: `data.polisyos.authz.decision`  
  HTTP path для OPA API: `/v1/data/polisyos/authz/decision`
- Deployment gate: `data.polisyos.deploy.decision`  
  HTTP path: `/v1/data/polisyos/deploy/decision`

## Модули

- `tenant_boundary.rego` — tenant boundary deny-by-default.
- `role_access.rego` — RBAC по method/path + MFA для sensitive paths.
- `data_classification.rego` — PII-tier ceiling, anonymization/mfa checks, `allowed_columns`.
- `delegation_guard.rego` — защита делегированного user context по SPIFFE peer identity.
- `decision.rego` — композитная runtime policy (`allow` только если все sub-policy allow).
- `vulnerability.rego` — CVE/SBOM gate по CVSS threshold + allowlist exceptions.
- `deploy.rego` — композитный deploy entrypoint над vulnerability policy.

## Контракт входных данных

Политики ожидают поля:

- `request`: `method`, `path`, `headers`
- `identity`: `tenant_id`, `roles`, `principal_type`, `mfa_verified`, `cell_id`, `sub`, `spiffe_id`
- `peer`: `spiffe_id`
- `resource`: `tenant_id`, `kind`, `artifact_id`, `pii_tier`, `metric_id`, `columns`, `requires_anonymization`

Этот контракт формируется в `src/polisyos/core/security/authz.py` (`AuthzInput.to_opa_input()`) и используется в `src/polisyos/runtime/http/authz_middleware.py`.

## Формат результата decision

Ожидаемые поля:

- `allow` (boolean)
- `deny_reasons` (list/set)
- `audit_entry` (object)
- `allowed_columns` (optional; для data classification)

## Локальные проверки

```bash
opa test policy-engine/ops/opa/policies -v
```

## Важно про Helm

В `ops/helm/polisyos-cell/policies/` лежит копия policy-файлов для ConfigMap внутри chart.
При изменении Rego в `ops/opa/policies/` синхронизируйте дубли в `ops/helm/polisyos-cell/policies/`.
