# tools/data

Data-prep and fixture-capture commands that used to live under `scripts/`.

Canonical entry points:

```bash
uv run polisyos-tools data --help
uv run polisyos-tools data build-academic-gold-candidates --help
uv run polisyos-tools data build-expert-review-bundle --help
uv run polisyos-tools data generate-wvs-registry --help
uv run polisyos-tools data record-fixtures --help
```

Legacy `scripts/*.py` paths remain as thin compatibility wrappers during the
consolidation window.
