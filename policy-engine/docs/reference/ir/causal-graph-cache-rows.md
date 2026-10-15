# Causal graph export rows

Freshness: 2026-10-14
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/analytics/causal_graph.py`, `src/polisyos/ir/analytics/causal_graph_kuzu.py`, `tests/unit/ir/test_causal_graph_cache_rows.py`
Snapshot and evidence level: the Python row-export and cache/copy paths were inspected at commit `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; the named test file was read but not executed for this audit. The evidence covers local row preparation and consumer values, not a live Kuzu database.

`CausalGraphModel.kuzu_node_rows` and `kuzu_edge_rows` retain their tuple-of-dictionaries
interface. Each read returns detached ordinary dictionaries. A consumer may mutate its
parameters without changing later exports, the graph dump or cached ancestry.

The graph prepares each row set once per graph version and stores immutable serialized
rows internally. `model_copy(update=...)` discards these derived caches before preparing
the new version. Published graph topology and nested metadata remain immutable; the
adjacency and component caches retain their weak-reference cleanup.

The native checks exercise row mutation, dictionary base aliases, warm/cold/copy coherence,
the actual CSV exporters and the actual `to_kuzu` parameter boundary. These checks cover
local preparation and consumer values. They do not establish execution against a live
Kuzu database.
