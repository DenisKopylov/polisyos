"""Enumerate the entire canonical L1 relational population without live fetch claims."""
import hashlib
import json
from pathlib import Path
import duckdb

ROOT = Path.cwd()
PATH = ROOT / "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def identity(rows):
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda v:json.dumps(v,default=str)),
                                    separators=(",",":"),default=str).encode()).hexdigest()
before=digest(PATH)
c=duckdb.connect(str(PATH),read_only=True)
out={"source":{"path":str(PATH.relative_to(ROOT)),"sha256":before,"bytes":PATH.stat().st_size},
     "scope":"complete canonical L1 dataset/distribution/binding vocabulary; no fetch or scientific accuracy claim",
     "tables":{}}
for table in ("ds_datasets","ds_distributions","ds_metric_bindings"):
    columns=[r[0] for r in c.execute(f"DESCRIBE {table}").fetchall()]
    keys=["id"] if "id" in columns else columns
    names=",".join('"'+v+'"' for v in keys)
    rows=c.execute(f"SELECT {names} FROM {table}").fetchall()
    independent=c.execute(f"SELECT {names} FROM {table} GROUP BY ALL").fetchall()
    n=c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    left={json.dumps(r,default=str) for r in rows}; right={json.dumps(r,default=str) for r in independent}
    out["tables"][table]={"denominator":n,"walked":len(rows),"unique":len(left),
        "independent_grouped_count":len(independent),"identity_sha256":identity(rows),
        "independent_identity_sha256":identity(independent),
        "first_only":sorted(left-right),"second_only":sorted(right-left),"key_columns":keys}
    assert n==len(rows) and left==right
out["dataset_execution_tiers"]=c.execute("SELECT execution_tier,count(*) FROM ds_datasets GROUP BY execution_tier ORDER BY execution_tier").fetchall()
out["dataset_sources"]=c.execute("SELECT source,count(*) FROM ds_datasets GROUP BY source ORDER BY source").fetchall()
out["all_dataset_rows_independent_distribution"]=c.execute("SELECT execution_tier,source,id FROM ds_datasets").fetchall()
# Reconcile every group from a second complete row walk, retain only deltas.
from collections import Counter
walk=out.pop("all_dataset_rows_independent_distribution")
assert dict(Counter(r[0] for r in walk))==dict(out["dataset_execution_tiers"])
assert dict(Counter(r[1] for r in walk))==dict(out["dataset_sources"])
out["group_reconciliation"]="full-row Counter equals independent SQL GROUP BY; exact identity set reconciliation above"
out["distribution_parser_support"]=c.execute("SELECT parser_supported,count(*) FROM ds_distributions GROUP BY parser_supported ORDER BY parser_supported").fetchall()
assert dict(Counter(r[0] for r in c.execute("SELECT parser_supported FROM ds_distributions").fetchall()))==dict(out["distribution_parser_support"])
out["binding_orphan_dataset_identities"]=c.execute("SELECT b.metric_id,b.dataset_id,b.distribution_id FROM ds_metric_bindings b LEFT JOIN ds_datasets d ON b.dataset_id=d.id WHERE d.id IS NULL ORDER BY ALL").fetchall()
out["binding_orphan_distribution_identities"]=c.execute("SELECT b.metric_id,b.dataset_id,b.distribution_id FROM ds_metric_bindings b LEFT JOIN ds_distributions d ON b.distribution_id=d.id WHERE d.id IS NULL ORDER BY ALL").fetchall()
out["dataset_missing_all_distributions"]=c.execute("SELECT d.id FROM ds_datasets d LEFT JOIN ds_distributions x ON d.id=x.dataset_id WHERE x.id IS NULL ORDER BY d.id").fetchall()
out["limitation"]="Relational vocabulary census, not successful bind_fetch_target coverage or live execution. Missing/null values preserved by raw SQL tuples."
c.close()
after=digest(PATH)
out["source_unchanged"]=before==after
assert before==after
print(json.dumps(out,sort_keys=True,ensure_ascii=False,default=str))
