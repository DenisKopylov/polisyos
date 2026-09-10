"""Enumerate the immutable L1 and exact request vocabulary without claiming semantic supply."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import duckdb

ROOT=Path.cwd()
PATH=ROOT/'production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb'
REQUEST=ROOT/'architecture/policy_design_case/layer3_gx_data_home/cases/ua-msme-affordable-loans-2022/layer3_gx_pinned_request.json'
MANIFEST=ROOT/'architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json'
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def normalized(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value).lower()).strip()
def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':'))
request=json.loads(REQUEST.read_text())
constructs={x['construct_ref'] for x in request['requested_constructs']}
terms={normalized(term) for x in request['requested_constructs'] for term in [x['construct_ref'],*x['broad_query_terms']]}
fixture=next(x for x in json.loads(MANIFEST.read_text())['fixtures'] if x['fixture_id']=='ua_msme_credit_worldbank_measurement')
expected=set(fixture['expected_catalog_binding_refs'])
before=digest(PATH)
c=duckdb.connect(str(PATH),read_only=True)
reports={}; errors=[]; exact=[]; lexical=[]; required_observations=[]; vocabulary={}
try:
    tables=[x[0] for x in c.execute('SHOW TABLES').fetchall()]
    table_inventory={x[0] for x in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
    assert set(tables)==table_inventory
    dataset_ids=set()
    for table in tables:
        info=c.execute(f"PRAGMA table_info('{table}')").fetchall()
        columns=[row[1] for row in info]
        primary=[row[1] for row in info if row[5]]
        count=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        independent_ids={row[0] for row in c.execute(f'SELECT rowid FROM {table}').fetchall()}
        cursor=c.cursor().execute(f'SELECT rowid,* FROM {table} ORDER BY rowid')
        seen=set(); semantics=set(); status=Counter(); current_vocab=Counter()
        while batch:=cursor.fetchmany(2048):
            for values in batch:
                physical_id=values[0]; seen.add(physical_id)
                row=dict(zip(columns,values[1:],strict=True))
                identity=tuple(row[x] for x in primary) if primary else (physical_id,)
                semantics.add(canonical(identity))
                try:
                    all_values=[]
                    for field,value in row.items():
                        if isinstance(value,str): all_values.append((field,value))
                        elif isinstance(value,list):
                            all_values.extend((field,x) for x in value if isinstance(x,str))
                    normalized_values=[(field,value,normalized(value)) for field,value in all_values]
                    literal_matches=sorted({(field,value) for field,value,norm in normalized_values if norm in terms})
                    locator_matches=(sorted({term for _,_,norm in normalized_values for term in terms if term in norm}) if table=='ds_datasets' else [])
                    if table=='ds_datasets':
                        dataset_ids.add(row['id'])
                        if locator_matches:
                            lexical.append({'identity':row['id'],'source':row['source'],'title':row['title'],'source_dataset_id':row['source_dataset_id'],'tier':row['execution_tier'],'terms':locator_matches,'coverage_countries':row['coverage_countries'],'time_start':row['coverage_time_start'],'time_end':row['coverage_time_end'],'metrics':row['polisyos_metrics'],'variables':row['variables']})
                    for field in ('metric_id','canonical_var','canonical_variable','raw_variable'):
                        if field in row:
                            current_vocab[(field,canonical(row[field]))]+=1
                    if literal_matches:
                        exact.append({'table':table,'identity':list(identity),'matches':literal_matches})
                    if table=='ds_observations' and row['canonical_var'] in constructs:
                        required_observations.append({'identity':row['observation_id'],'dataset_id':row['dataset_id'],'canonical_var':row['canonical_var'],'country_code':row['country_code'],'year':row['year'],'value_is_null':row['value'] is None})
                    status['readable']+=1
                except Exception as exc:
                    status['ambiguous']+=1
                    errors.append({'table':table,'identity':list(identity),'reason':f'{type(exc).__name__}: {exc}'})
        assert seen==independent_ids and len(seen)==count
        assert sum(status.values())==count
        if primary: assert len(semantics)==count
        reports[table]={'row_denominator':count,'streamed_identities':len(seen),'independent_rowid_identities':len(independent_ids),'identity_symmetric_difference':sorted(seen^independent_ids),'primary_key':primary,'status':dict(status)}
        for field in ('metric_id','canonical_var','canonical_variable','raw_variable'):
            if field in columns:
                independent=Counter({(field,canonical(value)):n for value,n in c.execute(f'SELECT {field},COUNT(*) FROM {table} GROUP BY {field}').fetchall()})
                first=Counter({key:n for key,n in current_vocab.items() if key[0]==field})
                assert first==independent
        if current_vocab:
            vocabulary[table]={'distinct_field_value_identities':len(current_vocab),'identity_digest':hashlib.sha256(canonical(sorted(current_vocab)).encode()).hexdigest(),'exact_request_matches':[{'field':field,'value':json.loads(value),'rows':n} for (field,value),n in sorted(current_vocab.items()) if normalized(json.loads(value)) in terms]}
    # Independent SQL lexical-locator identities over complete rows. Locator only,
    # never semantic supply, calibrated relevance, or admissible observations.
    dataset_info=c.execute("PRAGMA table_info('ds_datasets')").fetchall()
    scalar_columns=[row[1] for row in dataset_info if row[2]=='VARCHAR']
    array_columns=[row[1] for row in dataset_info if row[2]=='VARCHAR[]']
    values='list_concat(['+','.join(scalar_columns)+'],'+','.join(array_columns)+')'
    sql_terms=' OR '.join("contains(regexp_replace(lower(v.value), '[^a-z0-9]+', ' ', 'g'), ?)" for _ in sorted(terms))
    sql_lexical={row[0] for row in c.execute(f'SELECT DISTINCT id FROM ds_datasets d, UNNEST({values}) AS v(value) WHERE {sql_terms}',sorted(terms)).fetchall()}
    py_lexical={row['identity'] for row in lexical}
    assert py_lexical==sql_lexical, {'python_only':sorted(py_lexical-sql_lexical),'sql_only':sorted(sql_lexical-py_lexical)}
    sql_expected={row[0] for row in c.execute('SELECT id FROM ds_datasets WHERE id IN (SELECT UNNEST(?))',[sorted(expected)]).fetchall()}
    assert dataset_ids&expected==sql_expected
    after=digest(PATH); assert before==after
    print(json.dumps({'source':{'path':str(PATH.relative_to(ROOT)),'sha256':before,'size':PATH.stat().st_size,'unchanged':before==after},'request':{'path':str(REQUEST.relative_to(ROOT)),'sha256':digest(REQUEST),'constructs':sorted(constructs),'literal_locator_terms':sorted(terms)},'denominators':reports,'vocabulary':vocabulary,'expected_fixture_seed_intersection':sorted(sql_expected),'exact_request_literal_matches':exact,'literal_locator_candidates':lexical,'literal_locator_identity_reconciliation':{'python':len(py_lexical),'sql':len(sql_lexical),'symmetric_difference':sorted(py_lexical^sql_lexical)},'required_observation_rows':required_observations,'unreadable':errors,'limitations':['Literal matches are a complete locator census, not semantic supply or authority.','No missing keyword is interpreted as absence of real measurements.','A runtime producer still owes actual source/contract admission and complete bytes; neither declared metadata nor this census discharges J.']},indent=2,ensure_ascii=False,default=str))
finally:
    c.close()
