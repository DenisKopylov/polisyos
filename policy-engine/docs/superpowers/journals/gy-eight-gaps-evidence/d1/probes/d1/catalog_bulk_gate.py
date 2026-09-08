"""Complete real-owner binding census; no overridden lookup or hash predicate."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import duckdb
from polisyos.data_forge.read_api import catalog as owner

ROOT=Path.cwd(); PATH=ROOT/"production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
c=duckdb.connect(str(PATH),read_only=True)
cursor=c.execute("SELECT * FROM ds_metric_bindings ORDER BY metric_id,dataset_id,distribution_id")
columns=[d[0] for d in cursor.description]
rows=[dict(zip(columns,row,strict=True)) for row in cursor.fetchall()]
raw_keys={(r["metric_id"],r["dataset_id"],r["distribution_id"]) for r in rows}
independent=set(c.execute("SELECT metric_id,dataset_id,distribution_id FROM ds_metric_bindings GROUP BY ALL").fetchall())
assert raw_keys==independent and len(rows)==c.execute("SELECT count(*) FROM ds_metric_bindings").fetchone()[0]
requests=[];submitted=[];outcomes=[]
for row in rows:
    key=(row["metric_id"],row["dataset_id"],row["distribution_id"])
    try:
        raw_filters=row["default_filters"]
        filters=json.loads(raw_filters) if isinstance(raw_filters,str) else raw_filters
        request=owner.CatalogFetchRequest(metric_id=row["metric_id"],connector_id=row["connector_id"],
            request_dataset_id=row["request_dataset_id"],profile_id=row["profile_id"] or None,
            filters=filters)
        requests.append(request);submitted.append((key,row["execution_tier"]))
    except Exception as exc:
        outcomes.append((key,"ambiguous",f"request_unreadable:{type(exc).__name__}:{exc}"))
graph=owner.DatasetCatalogGraph(PATH,PATH.parent)
try:
    resolved=graph.bind_fetch_targets(requests)
    assert len(resolved)==len(requests)
    basis=graph._store._fetch_source_identities()
    for (key,tier),request,result in zip(submitted,requests,resolved,strict=True):
        assert result.request==request
        outcomes.append((key,result.status,result.reason))
    assert {key for key,_,_ in outcomes}==raw_keys and len(outcomes)==len(rows)
    grouped=Counter(status for _,status,_ in outcomes)
    cross={status:sum(value==status for _,value,_ in outcomes) for status in sorted(grouped)}
    assert grouped==cross
    by_tier=Counter((tier,result.status) for (_,tier),result in zip(submitted,resolved,strict=True))
    assert sum(by_tier.values())==len(submitted)
    out={"station":"Actual unmodified DatasetCatalogGraph.bind_fetch_targets; full raw-source hashes before/after inside real owner",
        "source":{"path":str(PATH.relative_to(ROOT)),"identity":basis[0].model_dump(mode="json"),
                  "overlay_path":basis[1],"overlay":basis[2]},
        "denominator":{"binding_rows":len(rows),"requests_submitted":len(requests),"ordered_outcomes":len(outcomes)},
        "independent_identity_reconciliation":{"raw_unique_keys":len(raw_keys),"grouped_unique_keys":len(independent),"symmetric_difference":sorted(raw_keys^independent)},
        "status":dict(grouped),"by_declared_tier":[[tier,status,n] for (tier,status),n in sorted(by_tier.items())],
        "finding_identities":[[key,status,reason] for key,status,reason in outcomes if status!="bound"],
        "bound_identity_digest":hashlib.sha256(json.dumps(sorted(key for key,status,_ in outcomes if status=="bound")).encode()).hexdigest(),
        "limits":"Binding lookup custody only; catalog-only/ambiguous/non-admitted rows retained. Live connector execution and scientific truth are not inferred. Whole dataset/distribution denominator is independently reconciled in catalog-population.json and typed target classification is separately limited."}
    print(json.dumps(out,sort_keys=True,ensure_ascii=False,default=str))
finally:
    graph.close();c.close()
