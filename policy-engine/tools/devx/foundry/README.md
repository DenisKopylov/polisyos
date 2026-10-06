# Foundry DevX (`tools/devx/foundry`)

## Purpose

`tools/devx/foundry` — публичная tooling surface для Foundry ABI maintenance:
генерация `.pyi` stubs и обновление signature baseline после одобренных
breaking/non-breaking API changes.

## Where to Start

- Stub generation: `tools/devx/foundry/generate_stubs.py`.
- Signature baseline refresh: `tools/devx/foundry/update_signature_baseline.py`.
- Written outputs:
  `src/polisyos/foundry/methods/{base,registry,composer}.pyi` and
  `src/polisyos/foundry/methods/components/composer.pyi`.

- Baseline artifact:
  `tests/_golden/foundry/signature_baseline.json`.

## Public Entrypoints

| Entrypoint                                                            | Purpose                                                     |
| --------------------------------------------------------------------- | ----------------------------------------------------------- |
| `uv run polisyos-tools foundry generate-stubs [--dry-run \| --check]`  | Регенерировать или сверить method stubs для Foundry facade. |
| `uv run polisyos-tools foundry update-signature-baseline [--dry-run]` | Пересчитать stable digests и обновить signature baseline.   |

## Depends On / Depended On By

- **Depends on:** `polisyos.foundry.methods.*`, `mypy.stubgen`, registry
  snapshotting в `MethodRegistry`, baseline fixture under `tests/unit/foundry`.

- **Depended on by:** Foundry public-surface reviews, signature compatibility
  tests, release closeout и manual ABI drift investigations.

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command                                                             | Purpose                                                              | Status                                                                                        |
| ------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools foundry generate-stubs --dry-run`            | Проверить stub generation без записи `.pyi` файлов.                  | `smoke-tested` (команда запускается, но текущая env-конфигурация не исполняет `mypy.stubgen`) |
| `uv run polisyos-tools foundry update-signature-baseline --dry-run` | Проверить signature diff без переписи baseline fixture.              | `smoke-tested` (сейчас падает на `RegistrySnapshot`/`.items()` mismatch)                      |
| `uv run polisyos-tools foundry generate-stubs`                      | Записать regenerated `.pyi` stubs в `src/polisyos/foundry/methods/`. | `conceptual` (изменяет checked-in artifacts)                                                  |
| `uv run polisyos-tools foundry update-signature-baseline`           | Обновить `tests/_golden/foundry/signature_baseline.json`.           | `conceptual` (изменяет checked-in artifact)                                                   |

## Test And Verification

| Command                                                                                            | What it verifies                                                   | Status         |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | -------------- |
| `uv run pytest -q tests/unit/foundry/contracts/test_signature_compat.py tests/repo_quality/tools/test_phase4_consolidation.py` | Signature drift contract и zoned-tooling compatibility.            | `conceptual`   |
| `uv run polisyos-tools list --by-zone`                                                             | Foundry tooling category корректно зарегистрирована в unified CLI. | `smoke-tested` |

## Reference Docs

- [Foundry README](../../../src/polisyos/foundry/README.md)
- [Public Surface Reference](../../../docs/reference/public-surface.md)
- [Tool Reference](../../../docs/reference/tools.md)
- [Causal Engine Explanation](../../../docs/explanation/causal-engine.md)

## Current State

- Stub generation сейчас покрывает `polisyos.foundry.methods.base`,
  `registry`, `composer` и canonical `components.composer`. Фасадные
  registry/composer stubs сохраняют re-export; canonical composer stub
  производится тем же `mypy.stubgen` owner, включая restoration API и
  private dataclass fields, нужные canonical artifact intake. Base stub
  также сохраняет typed private helpers, используемые canonical composer.

- Генератор строит ожидаемый stub каждой цели во временном каталоге,
  применяет `ruff check --select I --fix`, затем `ruff format` с repository
  `pyproject.toml`. Обычный режим атомарно записывает канонические bytes.
  `--check` строит те же bytes и сравнивает каждую из четырёх целей без записи
  checked-in файлов; missing/unreadable target, drift или ошибка producer
  возвращают ненулевой exit. Freshness command:
  `uv run polisyos-tools foundry generate-stubs --check`.
  `--dry-run` по-прежнему только описывает предполагаемые записи и не
  проверяет freshness; он несовместим с `--check`.

- Source of truth для base/canonical composer — соответствующие `.py`
  модули; registry/composer facade stubs производятся из заданных в
  `REEXPORT_STUBS` re-export recipes. Воспроизводимость проверки зависит от
  admitted Python, `mypy.stubgen`, Ruff и repository configuration; совпадение
  stubs само по себе не проверяет runtime execution или научную валидность.

- Signature baseline хранится в тестовых fixtures и нужен для осознанного ABI
  review, а не для silent drift.

- Канонический surface — `polisyos-tools foundry ...`; product-root
  `scripts/` retired during Repository SOTA closeout.

- Last updated: 2026-10-06 (старые smoke-status rows выше сохраняют свой профиль).
