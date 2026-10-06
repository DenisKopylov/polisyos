import csv
import gc
import json
from copy import deepcopy

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal import admg_ops
from polisyos.ir.analytics.causal_graph import CausalEdge,CausalGraphModel,GraphType,EdgeSource,load_causal_graph_model,persist_causal_graph_model
from polisyos.ir.analytics.causal_graph_kuzu import _export_graph_edges_csv,_export_graph_nodes_csv

SRC='X,"\nnode'
DST='λY'

def graph():
 return CausalGraphModel(graph_type=GraphType.DAG,nodes=[SRC,DST],edges=[CausalEdge(src=SRC,dst=DST,sources=[EdgeSource.DATA],evidence_refs=['receipt:/x'],metadata={'nested':{'list':['a','b']}})],metadata={'nested':{'list':['g']}})

def test_plain_reader_mutation_and_fresh_cas_csv_remain_canonical(tmp_path):
 g=graph();dump=g.model_dump(mode='json');baseline=g.kuzu_edge_rows
 assert type(baseline) is tuple and type(baseline[0]) is dict
 assert baseline[0] is not g.kuzu_edge_rows[0]
 assert g.kuzu_node_rows[0] is not g.kuzu_node_rows[0]
 dict.clear(baseline[0]);baseline[0].update({'src':DST,'extra':{'nested':['wrong']}})
 assert g.model_dump(mode='json')==dump
 assert admg_ops.ancestors(g,frozenset({DST}))==frozenset({SRC,DST})
 expected={'src':SRC,'dst':DST,'mark_src':'tail','mark_dst':'arrow','lag':None,'combined_confidence':None,'graph_type':'dag','sources':'["data"]','evidence_refs':'["receipt:/x"]','metadata_json':'{"nested": {"list": ["a", "b"]}}'}
 assert g.kuzu_edge_rows==(expected,)
 store=FileSystemCAS(tmp_path/'cas');ref=persist_causal_graph_model(store,g);fresh=load_causal_graph_model(FileSystemCAS(tmp_path/'cas'),ref)
 assert fresh.model_dump(mode='json')==dump and fresh.kuzu_edge_rows==(expected,)
 _export_graph_nodes_csv(fresh,tmp_path/'nodes.csv');_export_graph_edges_csv(fresh,tmp_path/'edges.csv')
 with (tmp_path/'nodes.csv').open(newline='') as f: assert list(csv.DictReader(f))==[{'name':SRC},{'name':DST}]
 with (tmp_path/'edges.csv').open(newline='') as f: (record,)=list(csv.DictReader(f))
 assert record=={'FROM':SRC,'TO':DST,'mark_src':'tail','mark_dst':'arrow','lag':'','combined_confidence':'','graph_type':'dag','sources':'["data"]','evidence_refs':'["receipt:/x"]','metadata_json':'{"nested": {"list": ["a", "b"]}}'}

def test_actual_node_and_edge_consumer_mutations_are_reader_local():
 g=graph();expected=deepcopy((g.kuzu_node_rows,g.kuzu_edge_rows));observed=[]
 class Consumer:
  def execute(self,statement,parameters):
   assert type(parameters) is dict
   observed.append((statement,deepcopy(parameters)))
   dict.__setitem__(parameters,'name','hostile');dict.clear(parameters)
 g.to_kuzu(Consumer())
 assert [p for _,p in observed]==[*expected[0],*expected[1]]
 assert (g.kuzu_node_rows,g.kuzu_edge_rows)==expected
 assert len(observed)==3 and observed[-1][0].startswith('MATCH')

def test_preparation_once_copy_and_deepcopy_reset(monkeypatch):
 import polisyos.ir.analytics.causal_graph as owner
 native=owner._serialize_kuzu_edge_row;calls=[]
 def watched(*args,**kwargs):
  calls.append(args[0]);return native(*args,**kwargs)
 monkeypatch.setattr(owner,'_serialize_kuzu_edge_row',watched)
 g=graph();g.kuzu_edge_rows;g.kuzu_edge_rows;g.kuzu_edge_rows
 assert len(calls)==1
 old=g.__dict__['_kuzu_edge_rows_json'];assert type(old) is tuple and all(type(x) is str for x in old)
 changed=g.model_copy(update={'edges':[]},deep=True)
 assert '_kuzu_edge_rows_json' not in changed.__dict__ and changed.kuzu_edge_rows==()
 assert g.__dict__['_kuzu_edge_rows_json'] is old
 copied=g.model_copy(deep=True)
 assert '_kuzu_edge_rows_json' not in copied.__dict__
 assert copied.kuzu_edge_rows==g.kuzu_edge_rows and len(calls)==2
 assert copied.model_dump(mode='json')==g.model_dump(mode='json')

def test_actual_adjacency_components_weakref_cleanup():
 g=graph();key=id(g)
 admg_ops.ancestors(g,frozenset({DST}));adj=admg_ops._ADJ_CACHE[key]
 admg_ops.ancestors(g,frozenset({DST}));assert admg_ops._ADJ_CACHE[key] is adj
 admg_ops.c_components(g)
 assert key in admg_ops._CC_CACHE and key in admg_ops._GRAPH_REFS
 del g;gc.collect();gc.collect()
 assert key not in admg_ops._ADJ_CACHE and key not in admg_ops._CC_CACHE and key not in admg_ops._GRAPH_REFS
