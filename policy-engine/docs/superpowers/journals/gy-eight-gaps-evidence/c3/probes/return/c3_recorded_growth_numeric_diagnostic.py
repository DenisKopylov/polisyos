"""Reconcile every canonical-population group using raw Parquet and exact sums."""
from __future__ import annotations
import hashlib
import json
import math
import platform
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from pathlib import Path


def _number(value):
    if value is None: return None
    if math.isnan(value): return 'NaN'
    if math.isinf(value): return '+Infinity' if value>0 else '-Infinity'
    return {'decimal':repr(value),'hex':value.hex(),'round6':round(value,6)}


def main():
    import duckdb
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    from polisyos.runtime.quality import data_forge_binding as owner

    recipe=owner.RecordedPanelRecipe()
    source,source_hash,source_size,manifest_hash=owner._validated_recorded_source(None)
    parameters=[str(source.parquet_path),recipe.family,recipe.metric_id,list(recipe.entity_ids)]
    predicate=''' FROM read_parquet(?) WHERE family = ? AND metric_id = ?
        AND observed_value IS NOT NULL
        AND CAST(entity_id AS VARCHAR) IN (SELECT UNNEST(?))'''
    query='SELECT CAST(entity_id AS VARCHAR), CAST(period_start AS DATE), SUM(CAST(observed_value AS DOUBLE)), COUNT(*)'+predicate+' GROUP BY 1,2'
    with duckdb.connect(database=':memory:') as connection:
        threads=connection.execute("SELECT current_setting('threads')").fetchone()[0]
        first=connection.execute(query,parameters).fetchall()
        repeated=connection.execute(query,parameters).fetchall()
        compensated=connection.execute('SELECT CAST(entity_id AS VARCHAR), CAST(period_start AS DATE), FSUM(CAST(observed_value AS DOUBLE))'+predicate+' GROUP BY 1,2',parameters).fetchall()
        declared_complete={row[0] for row in connection.execute('SELECT CAST(period_start AS DATE)'+predicate+' GROUP BY 1 HAVING COUNT(DISTINCT CAST(entity_id AS VARCHAR)) = ?',[*parameters,len(recipe.entity_ids)]).fetchall()}
        declared_count=connection.execute('SELECT COUNT(*)'+predicate,parameters).fetchone()[0]
    groups=defaultdict(list);null_groups=defaultdict(int);unreadable=[]
    dataset=ds.dataset(source.parquet_path,format='parquet')
    scanner=dataset.scanner(columns=['entity_id','period_start','observed_value'],filter=(ds.field('family')==recipe.family)&(ds.field('metric_id')==recipe.metric_id),batch_size=65536,use_threads=False)
    physical_type=str(dataset.schema.field('observed_value').type)
    for batch in scanner.to_batches():
        entities=pc.cast(batch.column('entity_id'),pa.string())
        mask=pc.is_in(entities,value_set=pa.array(recipe.entity_ids,type=pa.string()))
        selected=batch.filter(mask)
        if not selected.num_rows: continue
        entity_values=pc.cast(selected.column('entity_id'),pa.string()).to_pylist()
        values=pc.cast(selected.column('observed_value'),pa.float64()).to_pylist()
        for entity,period,value in zip(entity_values,selected.column('period_start').to_pylist(),values,strict=True):
            if isinstance(period,datetime): period=period.date()
            elif isinstance(period,str): period=date.fromisoformat(period[:10])
            if not isinstance(period,date):
                unreadable.append({'entity':entity,'period':repr(period),'reason':'period_not_date'})
                continue
            if value is None:null_groups[(entity,period)]+=1
            else:groups[(entity,period)].append(value)
    primary={(e,p):(v,n) for e,p,v,n in first}
    second={(e,p):(v,n) for e,p,v,n in repeated}
    fsum_sql={(e,p):v for e,p,v in compensated}
    def ids(keys):return [{'entity_id':e,'period':str(p)} for e,p in sorted(keys)]
    identity_delta={'sql_only':ids(primary.keys()-groups.keys()),'arrow_only':ids(groups.keys()-primary.keys())}
    count_delta=[];differences=[];repeat_delta=[];nonfinite=[];outside_bound=[];all_round_deltas=[]
    for key in sorted(primary.keys()&groups.keys()):
        sql_value,sql_count=primary[key];values=groups[key]
        identity={'entity_id':key[0],'period':str(key[1])}
        if sql_count!=len(values):count_delta.append({**identity,'sql':sql_count,'arrow':len(values)})
        if any(not math.isfinite(v) for v in values) or not math.isfinite(sql_value):
            nonfinite.append({**identity,'nonfinite_rows':sum(not math.isfinite(v) for v in values),'sql':_number(sql_value)})
            continue
        regular=sum(values);accurate=math.fsum(values)
        with localcontext() as context:
            # Every binary64 can be represented exactly within this precision;
            # the extra count digits cover accumulation without Decimal rounding.
            context.prec=1200+len(str(len(values)))
            exact=sum((Decimal.from_float(v) for v in values),Decimal(0))
            absolute=sum((abs(Decimal.from_float(v)) for v in values),Decimal(0))
            unit=Decimal(2)**-53
            operations=max(0,len(values)-1)
            gamma=(Decimal(operations)*unit)/(1-Decimal(operations)*unit)
            bound=gamma*absolute
            error=abs(Decimal.from_float(sql_value)-exact)
            exact_round=exact.quantize(Decimal('0.000001'),rounding=ROUND_HALF_EVEN)
            row={**identity,'raw_row_count':len(values),'sql_row_count':sql_count,
                 'sql_sum':_number(sql_value),'python_sum':_number(regular),'math_fsum':_number(accurate),
                 'sql_fsum':_number(fsum_sql[key]),'sql_repeated_sum':_number(second[key][0]),
                 'exact_binary64_sum':str(exact),'exact_sum_round6':str(exact_round),
                 'sql_absolute_error':str(error),'sequential_ieee754_gamma_n_bound':str(bound),
                 'within_bound':error<=bound,'min':min(values),'max':max(values),
                 'in_canonical_recipe':recipe.period_start<=key[1]<=recipe.period_end}
            if round(sql_value,6)!=round(regular,6):differences.append(row)
            if sql_value!=second[key][0]:repeat_delta.append(row)
            if error>bound:outside_bound.append(row)
            if Decimal(str(round(sql_value,6)))!=exact_round:all_round_deltas.append(row)
    complete=set.intersection(*({p for e,p in groups if e==entity} for entity in recipe.entity_ids))
    source_after=owner._recorded_file_sha256(source.parquet_path)
    manifest_after=hashlib.sha256(source.manifest_path.read_bytes()).hexdigest()
    assert source_after==source_hash and manifest_after==manifest_hash,'source changed during diagnostic'
    grouped_rows=sum(n for _,n in primary.values());arrow_rows=sum(len(v) for v in groups.values())
    report={'source':str(source.parquet_path),'source_sha256_before':source_hash,'source_sha256_after':source_after,'source_size_bytes':source_size,'manifest_sha256':manifest_hash,
            'owner_source_sha256':hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest(),
            'station':{'python':platform.python_version(),'duckdb':duckdb.__version__,'pyarrow':pa.__version__,'duckdb_threads':threads,'database':':memory:'},
            'population':recipe.model_dump(mode='json')|{'period_scope':'all recorded periods','observed_value_physical_type':physical_type},
            'denominators':{'sql_groups':len(primary),'arrow_groups':len(groups),'sql_rows':declared_count,'sql_group_rows':grouped_rows,'arrow_rows':arrow_rows,'null_rows_excluded_by_owner':sum(null_groups.values())},
            'identity_delta':identity_delta,'count_delta':count_delta,'unreadable_groups':unreadable,'nonfinite_groups':nonfinite,
            'complete_periods_sql':sorted(map(str,declared_complete)),'complete_periods_arrow':sorted(map(str,complete)),
            'round6_sql_vs_python_differences':differences,'sql_repeated_sum_differences':repeat_delta,
            'sql_round6_vs_exact_differences':all_round_deltas,'outside_ieee754_accumulation_bound':outside_bound,
            'arithmetic_basis':'Exact sum of every selected raw Arrow binary64; original SQL SUM repeated; Python sum, math.fsum, SQL FSUM; no tolerance or production algorithm changed.'}
    print(json.dumps(report,indent=2,allow_nan=False))
    assert not identity_delta['sql_only'] and not identity_delta['arrow_only'] and not count_delta and not unreadable
    assert grouped_rows==arrow_rows==declared_count and complete==declared_complete

if __name__=='__main__':main()
