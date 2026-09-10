"""Explain every executable-tier refusal from the complete real owner census."""
import hashlib
import json
from pathlib import Path
import duckdb

ROOT=Path.cwd()
gate=json.loads(json.loads((ROOT/"_build/gy-gaps/d1/fabric/catalog-bulk-gate.json").read_text())["stdout"])
refused={tuple(key) for key,status,_ in gate["finding_identities"] if status=="not_admitted"}
path=ROOT/"production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
c=duckdb.connect(str(path),read_only=True)
q=c.execute("SELECT b.*,d.preferred_distribution_id,x.source_locator,x.connector_params "
            "FROM ds_metric_bindings b JOIN ds_datasets d ON b.dataset_id=d.id "
            "JOIN ds_distributions x ON x.id=b.distribution_id ORDER BY b.metric_id,b.dataset_id,b.distribution_id")
columns=[v[0] for v in q.description]
all_rows=[dict(zip(columns,r,strict=True)) for r in q.fetchall()]
selected=[r for r in all_rows if (r["metric_id"],r["dataset_id"],r["distribution_id"]) in refused
          and r["execution_tier"] in {"fetchable","transport_ready"}]
independent=c.execute("SELECT count(*) FROM ds_metric_bindings WHERE execution_tier IN ('fetchable','transport_ready')").fetchone()[0]
assert independent==sum(r["execution_tier"] in {"fetchable","transport_ready"} for r in all_rows)
print(json.dumps({"source":gate["source"],"complete_binding_denominator":len(all_rows),
    "executable_declared_denominator":independent,"finding_count":len(selected),
    "findings":[{"identity":[r["metric_id"],r["dataset_id"],r["distribution_id"]],
        "source":r["source"],"declared_request_dataset_id":r["request_dataset_id"],
        "actual_distribution_source_locator":r["source_locator"],
        "actual_distribution_connector_params":json.loads(r["connector_params"]),
        "is_declared_distribution_also_preferred":r["distribution_id"]==r["preferred_distribution_id"],
        "verdict":"not_admitted: declared CKAN resource differs from its actual catalog distribution"}
        for r in selected]},sort_keys=True,ensure_ascii=False))
c.close()
