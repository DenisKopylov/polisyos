# Contributor Start Here

> Быстрый индекс по принципу “если вы меняете X, начните отсюда”.

## First Contributor Journey

1. Confirm the supported host surface in [Environment Matrix](environment-matrix.md).
2. Follow the canonical install path in `docs/how-to/install.md`:
   `./scripts/bootstrap` -> `./scripts/doctor`.
3. Pick the nearest role track in `docs/how-to/onboarding/index.md`.
4. Run the scoped local gate with `./scripts/verify`.
5. If the change spans governance, release, onboarding, or repo-wide policy
   surfaces, finish with `./scripts/acceptance-audit`.

| You need to change... | Start here | Then verify |
| --- | --- | --- |
| Public package facade / supported import path | `architecture/public_surface.toml`, `src/polisyos/*/__init__.py` | `python3 tools/architecture/guardrails.py check` |
| Deep cross-package import | `architecture/deep_import_baseline.json` and `architecture/guardrail_exceptions.toml` | `python3 tools/architecture/guardrails.py check` |
| ABI-visible IR / Fabric contract | `schemas/abi_models.py`, `src/polisyos/ir/**`, `src/polisyos/fabric/**` | `uv run --extra ml python tools/diagnostics/gen_schema.py --check` |
| Runtime HTTP route or DTO | `src/polisyos/runtime/http/routes/`, `src/polisyos/runtime/http/services/` | `uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py` |
| Generated runtime client / dashboard API types | `docs/reference/generated-artifacts.md` and the relevant family entry | `uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py` and `cd frontend/runtime-dashboard && npm run generate:api` |
| New connector | `python3 tools/architecture/scaffold.py connector --name MySource --type REST --dry-run` | `python3 tools/lint/lint_connectors.py` |
| New governance pass | `python3 tools/architecture/scaffold.py governance-pass --name my_pass --output ... --test-output ... --dry-run` | `pytest tests/scientist/governance/...` |
| New runtime route | `python3 tools/architecture/scaffold.py runtime-route --name my_route --output ... --dry-run` | runtime contract drift checks |
| New benchmark | `python3 tools/architecture/scaffold.py benchmark --suite causal --name my_case --output ... --dry-run` | `docs/how-to/run-benchmarks.md` flow |
| New ADR | `python3 tools/architecture/scaffold.py adr --number 0097 --slug my-decision --title "My Decision" --output ... --dry-run` | update `docs/adr/index.md` when applicable |
| New runbook | `python3 tools/architecture/scaffold.py runbook --name dependency-upgrade --title "Dependency Upgrade" --output ... --dry-run` | link it from the relevant subsystem README |
| New subsystem / major surface | `docs/reference/ratchet-policy.md` plus `python3 tools/architecture/scaffold.py package-readme --module ... --output ... --dry-run` | `./scripts/acceptance-audit` |
| Platform-wide closeout / repo policy integration | `docs/reference/operations/platform-acceptance-audit.md` | `./scripts/acceptance-audit --require-manual-evidence --manual-evidence ...` |
| Temporary architecture guardrail exception | `architecture/guardrail_exceptions.toml`, `architecture/guardrail_exceptions_registry.md` | `python3 tools/architecture/guardrails.py check` |
