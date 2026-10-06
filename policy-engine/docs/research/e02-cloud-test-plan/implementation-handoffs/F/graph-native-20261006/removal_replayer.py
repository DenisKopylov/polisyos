import inspect,sys,pytest
from polisyos.foundry.methods.catalog.causal import admg_ops
name=sys.argv[1]
function=getattr(admg_ops,name)
source=inspect.getsource(function)
if name=="m_separation":
 anchor="is_collider = incoming_mark is EdgeMark.ARROW and mark_at_node is EdgeMark.ARROW"
 assert source.count(anchor)==1
 source=source.replace(anchor,"is_collider = False")
 selector="tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py::test_b216_complete_three_node_domain_matches_latent_dag_oracle"
else:
 anchor="if e.src in intervention_set or e.dst in intervention_set:"
 assert source.count(anchor)==1
 source=source.replace(anchor,"if False:")
 selector="tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py::test_b217_perfect_do_matches_latent_dag_for_all_action_sets"
exec(compile(source,admg_ops.__file__,"exec"),admg_ops.__dict__)
raise SystemExit(pytest.main([selector,"-o","addopts=","-q"]))
