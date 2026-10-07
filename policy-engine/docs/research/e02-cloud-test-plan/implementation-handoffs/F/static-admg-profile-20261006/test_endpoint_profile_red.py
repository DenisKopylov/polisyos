"""Actual valid CPDAG separation/rewrite escape before graph-profile repair."""
import pytest
from polisyos.foundry.methods.catalog.causal import admg_ops, do_calculus
from polisyos.ir.analytics.causal_graph import CausalGraphModel, CausalEdge, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import DistributionRef, DistributionDomain

def test_valid_cpdag_does_not_become_independence_or_rule1_rewrite():
    graph = CausalGraphModel(graph_type=GraphType.CPDAG, nodes=['Y','Z'], edges=[CausalEdge(src='Y',dst='Z',mark_src=EdgeMark.TAIL,mark_dst=EdgeMark.TAIL)])
    dist = DistributionRef(domain=DistributionDomain.SOURCE,variables=('Y',),conditioning=('Z',))
    separation = admg_ops.m_separation(graph,frozenset({'Y'}),frozenset({'Z'}),frozenset())
    rewritten = do_calculus.apply_rule1(dist,graph,frozenset({'Z'}))
    print({'graph':graph.model_dump(mode='json'),'admg_origin':admg_ops.__file__,'separation':separation,'input':dist.model_dump(mode='json'),'rewrite':None if rewritten is None else [x.model_dump(mode='json') for x in rewritten]})
    assert not separation and rewritten is None, 'Unresolved CPDAG edge silently disappeared and enabled observation deletion; must refuse unsupported profile.'
