# Installed causal graph source reconciliation

The 2026-10-07 reconciliation chooses the graph producer and reader contract in
`8236d9c368336a5ea20c1586f29aea7321db6536`. The competing installed-worker
carrier `3dde887e22592cdd7c1fe8865707afdfd72dc6fb` remains a separate history.
The two installed profiles with 199 passing cases were built from 8236; their
results do not assert a whole-head result for 3dde.

The complete Git walk from reviewed implementation
`ab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5` to 3dde contains nine commits and
221 changed tracked paths: 214 evidence paths and seven source, test, reference
documentation, or release-fragment paths. The committed reconciliation receipt
binds every path and each defining `ir/analytics/causal_graph.py` blob, rather
than selecting a representative commit.

| Defining graph blob | Contract |
| --- | --- |
| `8787cd95d63b342b5d9f5e760ffc8d73b1b8985d` | Original cached mutable row dictionaries |
| `342d416961ec817441574253320a9054c00d969e` | Private immutable JSON preparation; detached tuple/plain-dict reader values |
| `f2635665550259d20323d29a784faf11dc8896b7` | Canonical 8236 version, with two formatting hunks and identical whole-module AST to the preceding row |

The cache correction keeps graph schema 1.0 and existing consumer values. Each
row read decodes fresh dictionaries; a reader may mutate them without changing
subsequent exports. A warmed `model_copy(update=...)` removes old derived row
preparations. The graph model remains the source of truth for CSV output,
NetworkX parallel edges and endpoint/lag metadata, and typed CAS persistence.
This is an internal provider contract, as the canonical release fragment says;
the older carrier's public-surface label does not promote this provider.

The other runtime delta replaces two GCM reader imports with the maintained
Core `artifacts.ArtifactRef` facade. Their final bytes match 8236. The DoWhy
release-metadata change does not change worker execution, protocol, or math.
No graph, schema, backend, or public facade is changed by this reconciliation.

The narrow installed test executes the real parameter-emission and CSV
consumers, persists the mixed or updated graph in FileSystemCAS, then starts a
fresh isolated reader from the same installed distribution. It checks complete
NetworkX edge payloads, multiplicity, endpoint marks, lags, static ancestor sets,
explicit static-inference refusal for a temporal graph, schema version, and
installed origins. Its parameter recorder verifies the ordinary
dictionary consumer ABI; it is not a live Kuzu database witness. The source
receipt names the distribution SHA separately from the new test-carrier SHA.

LA007 and LA019 concern retired empty filename siblings while keeping their
real packages. LA020 concerns the explicit causal-engine and interference
facades and their supported compatibility window. The maintained 8236 census
and installed direct/star/private/FQN/pickle/pydoc/monkeypatch/loader checks
support that finite window. Computed external clients are outside that census;
the 38 incomplete static export declarations remain explicit unknowns with
unknown total counts. Neither observation is a repository-wide absence claim
or a completed static export inventory.
