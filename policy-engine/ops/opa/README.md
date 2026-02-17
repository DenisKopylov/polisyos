# OPA Policies (`ops/opa`)

Rego-политики для двух контуров:

- runtime authorization (`polisyos/authz/decision`);
- deploy gate на базе SBOM/CVE (`polisyos/deploy/decision`).

## Состав

- `policies/*.rego` — 7 policy-модулей;
- `policies/*_test.rego` — 7 unit-тестов.

## Entry points

| Контур | OPA data path | HTTP path |
|---|---|---|
| Runtime authz | `data.polisyos.authz.decision` | `/v1/data/polisyos/authz/decision` |
| Deploy gate | `data.polisyos.deploy.decision` | `/v1/data/polisyos/deploy/decision` |

## Модули политик

- `tenant_boundary.rego` — deny cross-tenant доступ.
- `role_access.rego` — RBAC по HTTP method/path и MFA-check для sensitive путей.
- `data_classification.rego` — проверка PII ceiling, anonymization, `allowed_columns`.
- `delegation_guard.rego` — валидация делегации user-контекста через SPIFFE peer identity.
- `decision.rego` — композитное runtime-решение (allow только при allow всех sub-policy).
- `vulnerability.rego` — SBOM/CVE gate (CVSS threshold + allow exceptions).
- `deploy.rego` — композитный deploy gate поверх `vulnerability`.

## Входной контракт

Runtime-политики ожидают:

- `request`: `method`, `path`, `headers`;
- `identity`: `tenant_id`, `roles`, `principal_type`, `mfa_verified`, `cell_id`, `sub`, `spiffe_id`;
- `peer`: `spiffe_id`;
- `resource`: `tenant_id`, `kind`, `artifact_id`, `pii_tier`, `metric_id`, `columns`, `requires_anonymization`.

Контракт формируется в `src/polisyos/core/security/authz.py` (`AuthzInput.to_opa_input()`) и применяется в `src/polisyos/runtime/http/authz_middleware.py`.

Deploy-политики используют `input.deployment` (image, sbom, vulnerabilities, overrides) и опционально `input.policy.cvss_threshold`.

## Выходной контракт

`decision`-модули возвращают:

- `allow` (`bool`);
- `deny_reasons` (`set/list`);
- `audit_entry` (`object`);
- `allowed_columns` (опционально, для data classification).

Fail-closed поведение при недоступности OPA реализовано в `src/polisyos/core/security/authz.py` (`OPAClient`).

## Проверка

```bash
opa test policy-engine/ops/opa/policies -v
```

## Синхронизация с Helm chart

`ops/helm/polisyos-cell/policies/` содержит копию Rego для ConfigMap в chart.
После изменения файлов в `ops/opa/policies/` синхронизируйте копии перед релизом chart.
