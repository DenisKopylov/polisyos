"""Read-only complete Lex amendment-coordinate measurement; no authority adjudication."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import duckdb
from polisyos.lex.knowledge import store as owner

p=Path('production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb')
print('owner_source',owner.__file__,flush=True)
before=p.stat()
con=duckdb.connect(str(p),read_only=True)
con.execute('BEGIN TRANSACTION')
cols=con.execute('DESCRIBE lex_amendments').fetchall()
rows=con.execute('SELECT amendment_id, effective_from, created_at FROM lex_amendments ORDER BY amendment_id').fetchall()
sql_counts=con.execute("SELECT COUNT(*), COUNT(DISTINCT amendment_id), COUNT(*) FILTER(WHERE effective_from IS NULL OR TRIM(CAST(effective_from AS VARCHAR)) = ''), COUNT(*) FILTER(WHERE created_at IS NOT NULL) FROM lex_amendments").fetchone()
sql_bad=con.execute("SELECT amendment_id FROM lex_amendments WHERE TRY_CAST(SUBSTR(CAST(effective_from AS VARCHAR),1,10) AS DATE) IS NULL ORDER BY amendment_id").fetchall()
python_bad=[r[0] for r in rows if owner.LegalKnowledgeStore._parse_amendment_date(r[1]) is None]
assert [r[0] for r in sql_bad]==python_bad
assert len(rows)==sql_counts[0]
assert len(set(r[0] for r in rows))==sql_counts[1]
assert sum(r[1] is None or str(r[1]).strip()=='' for r in rows)==sql_counts[2]
con.execute('COMMIT')
con.close()
after=p.stat()
assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':'),default=str).encode()).hexdigest()
def retain(name, value):
 path=Path('docs/superpowers/journals/debt-survey/blocked-b/raw')/name
 data=json.dumps(value,ensure_ascii=False,separators=(',',':'),default=str).encode()
 if path.exists():
  assert path.read_bytes()==data, f'existing evidence differs: {path}'
 else:
  with path.open('xb') as f:
   f.write(data)
 return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'records':len(value)}
selected=retain('lex-current-rows-v2-selected.json',rows)
unresolved=retain('lex-current-rows-v2-unresolved-ids.json',python_bad)
print(json.dumps({'scope':'current locally held substrate, not tracked base data and not owner-adjudicated authority','database_path':str(p),'resolved_path':str(p.resolve()),'stat':{'size':after.st_size,'mtime_ns':after.st_mtime_ns},'schema':cols,'denominator':'complete lex_amendments table; SQL aggregates and independently parsed full row identities agree','selected_row_fields':['amendment_id','effective_from','created_at'],'row_count':len(rows),'distinct_ids':sql_counts[1],'blank_effective_from':sql_counts[2],'unparseable_effective_from':len(python_bad),'created_at_nonnull':sql_counts[3],'complete_selected_rows':selected,'complete_unresolved_id_sequence':unresolved,'second_derivation':'SQL TRY_CAST bad-ID sequence equals owner Python parser bad-ID sequence','complete_owner_adjudication_receipt':'not_established','source_time_substitution':'not performed'},indent=2,default=str))
