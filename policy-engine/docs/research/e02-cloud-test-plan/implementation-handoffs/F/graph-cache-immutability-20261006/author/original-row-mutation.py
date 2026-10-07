import hashlib,json
from pathlib import Path
from polisyos.ir.analytics.causal_graph import CausalGraphModel,CausalEdge,GraphType
from polisyos.foundry.methods.catalog.causal.admg_ops import ancestors
import polisyos.ir.analytics.causal_graph as module
print('source',module.__file__,hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest())
g=CausalGraphModel(graph_type=GraphType.DAG,nodes=['X','Y'],edges=[CausalEdge(src='X',dst='Y')]);before=g.model_dump(mode='json');assert ancestors(g,frozenset({'Y'}))==frozenset({'X','Y'});rows=g.kuzu_edge_rows;print('before',json.dumps(before,sort_keys=True));print('warm_rows',json.dumps(rows,sort_keys=True));rows[0]['src']='Y';print('after_rows',json.dumps(g.kuzu_edge_rows,sort_keys=True));print('after_dump',json.dumps(g.model_dump(mode='json'),sort_keys=True));assert g.model_dump(mode='json')==before
cold=CausalGraphModel.model_validate(g.model_dump(mode='json'));print('cold_rows',json.dumps(cold.kuzu_edge_rows,sort_keys=True));assert g.kuzu_edge_rows==cold.kuzu_edge_rows,'cached export differs from canonical immutable graph after caller mutation'
