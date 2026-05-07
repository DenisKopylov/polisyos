# Add Public Facade

> Добавьте или измените поддерживаемый import surface так, чтобы он прошел через
> `__all__`, guardrails и published public-surface docs.

## Inputs

- модуль или package root, который вы хотите сделать supported surface;
- решение, это новый package entrypoint или новый export внутри уже публичного
  facade;

- понимание, нужен ли этому symbol long-term compatibility contract.

## Output

- обновленный package facade в `src/polisyos/**/__init__.py`;
- при необходимости обновленный `architecture/public_surface.toml`;
- synchronized `docs/reference/public-surface.md`.

## Commands

```bash
cd policy-engine
uv run polisyos-tools architecture guardrails sync
uv run polisyos-tools architecture guardrails check
```

## 1. Decide if the path should really be public

Supported public surface means:

- path appears in docs;
- compatibility/deprecation policy now applies;
- release and migration notes may need to mention future changes here.

If the symbol is temporary, deeply nested, or strongly tied to one internal
implementation detail, keep it internal.

## 2. Update the package facade

For an existing public package, edit its `__init__.py` and expose the symbol via
the package `__all__` policy already used there.

Typical cases:

- root package facades such as `polisyos.ir`, `polisyos.runtime`, `polisyos.lex`;
- IR package facades such as `polisyos.ir.analytics` or `polisyos.ir.world`.

Preserve the existing facade mode:

- `lazy_facade` packages should stay lazy;
- `module_doc_only` packages should not suddenly become eager export bags
  without an intentional manifest change.

## 3. Update the manifest when the package-level contract changes

If you are introducing a new package root or changing its classification, edit
`architecture/public_surface.toml`.

That manifest is the source of truth for:

- classification (`public_stable`, `public_experimental`, `internal`);
- expected facade mode;
- owner and README/reference linkage.

If you are only adding one new export inside an already listed package root,
the manifest usually stays unchanged and the work lives in `__init__.py` plus
tests/repo_quality/architecture/docs.

## 4. Regenerate and review the public-surface docs

Run:

```bash
uv run polisyos-tools architecture guardrails sync
```

This refreshes generated public-surface inventories and docs. Review:

- `docs/reference/public-surface.md`;
- package README for the affected subsystem;
- any package-specific public-surface doc, such as IR public-surface pages.

## 5. Verify before landing

Minimum checks:

```bash
uv run polisyos-tools architecture guardrails check
```

Useful focused tests when the change touches IR facades:

```bash
uv run pytest -q tests/unit/ir/test_public_surface.py
```

## Rollback

- remove the symbol from `__all__` if it should stay internal;
- revert manifest edits if you accidentally promoted a package root;
- regenerate guardrail artifacts again so docs and inventories return to the
  last intended state.

## Troubleshooting

- guardrails complain about missing `__all__`: the package declares a public
  facade mode but does not actually expose one;

- docs counts drift: rerun `guardrails sync` and review the generated reference
  page;

- temptation to document a deep import instead: if the supported path is not a
  package facade, it probably should not be public yet.
