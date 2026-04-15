# Contributor Start Here

> Быстрый индекс по принципу “если вы меняете X, начните отсюда”.

## First Contributor Journey

1. Confirm the supported host surface in [Environment Matrix](environment-matrix.md).
2. Follow the canonical install path in `docs/how-to/install.md`:
   `python3 -m tools.cli workspace bootstrap` ->
   `python3 -m tools.cli workspace doctor`.
3. Pick the nearest role track in `docs/how-to/onboarding/index.md`.
4. Run the scoped local gate with `python3 -m tools.cli workspace verify`.
5. If the change spans governance, release, onboarding, or repo-wide policy
   surfaces, finish with `python3 -m tools.cli workspace acceptance-audit`.

| You need to change... | Start here | Then verify |
| --- | --- | --- |
| Public package facade / supported import path | `architecture/public_surface.toml`, `src/polisyos/*/__init__.py` | `uv run polisyos-tools architecture guardrails check` |
| Deep cross-package import | `architecture/deep_import_baseline.json` and `architecture/guardrail_exceptions.toml` | `uv run polisyos-tools architecture guardrails check` |
| ABI-visible IR / Fabric contract | `schemas/abi_models.py`, `src/polisyos/ir/**`, `src/polisyos/fabric/**` | `uv run --extra ml polisyos-tools diagnostics gen-schema --check` |
| Runtime HTTP route or DTO | `src/polisyos/runtime/http/routes/`, `src/polisyos/runtime/http/services/` | `uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract` |
| Generated runtime client / dashboard API types | `docs/reference/generated-artifacts.md` and the relevant family entry | `uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract` and `cd frontend/runtime-dashboard && npm run generate:api` |
| New connector | `uv run polisyos-tools architecture scaffold connector --name MySource --type REST --dry-run` | `uv run polisyos-tools lint lint-connectors` |
| New governance pass | `uv run polisyos-tools architecture scaffold governance-pass --name my_pass --output ... --test-output ... --dry-run` | `pytest tests/scientist/governance/...` |
| New runtime route | `uv run polisyos-tools architecture scaffold runtime-route --name my_route --output ... --dry-run` | runtime contract drift checks |
| New benchmark | `uv run polisyos-tools architecture scaffold benchmark --suite causal --name my_case --output ... --dry-run` | `docs/how-to/run-benchmarks.md` flow |
| New ADR | `uv run polisyos-tools architecture scaffold adr --number 0097 --slug my-decision --title "My Decision" --output ... --dry-run` | update `docs/adr/index.md` when applicable |
| New runbook | `uv run polisyos-tools architecture scaffold runbook --name dependency-upgrade --title "Dependency Upgrade" --output ... --dry-run` | link it from the relevant subsystem README |
| New subsystem / major surface | `docs/reference/ratchet-policy.md` plus `uv run polisyos-tools architecture scaffold package-readme --module ... --output ... --dry-run` | `python3 -m tools.cli workspace acceptance-audit` |
| Platform-wide closeout / repo policy integration | `docs/reference/operations/platform-acceptance-audit.md` | `python3 -m tools.cli workspace acceptance-audit --require-manual-evidence --manual-evidence ...` |
| Temporary architecture guardrail exception | `architecture/guardrail_exceptions.toml`, `architecture/guardrail_exceptions_registry.md` | `uv run polisyos-tools architecture guardrails check` |
