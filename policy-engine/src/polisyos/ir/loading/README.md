# IR Loading

`polisyos.ir.loading` owns load-time boundaries and compatibility surfaces for
turning external payloads into IR contracts. It contains:

- `loaders.py` for Trinity bundle loading.
- `citations.py`, `fact_log.py`, `norm_pack.py`, and `portfolio.py` for
  ingestion-facing contract models.
- `migration_report.py` and `schema_catalog.py` for load-time reporting and
  reflection compatibility.

Schema wrapper code remains under `polisyos.ir.schemas`; this package only
exposes the loading-side view.
