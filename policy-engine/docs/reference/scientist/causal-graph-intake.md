# Current causal graph intake

The Scientist reconciliation node resolves supplied graph references through the
actual CAS manifest and bytes before using a cached graph or a query-preservation
shortcut. A well-shaped reference, an `ok` status, confidence, and a DAG label do
not establish the current graph content.

For data reconciliation the node reads the current method-result artifact and
any explicitly supplied graph. Both must agree when supplied together. Invalid
supplied graphs, references, literature priors, hints, or fragment sources fail;
they do not become an absent input and activate a fallback. Missing input still
produces the existing skip blocker when no graph or cached graph was supplied.

The node recomputes the complete typed reconciliation request. Reuse requires
full graph equality and matching source lineage, including a selected manifest
profile. The request digest in graph metadata records the actual typed inputs;
it is never sufficient on its own to authorize reuse. Changed direction or
parameters are therefore reflected in the newly persisted graph. A valid cached
graph without current source content is refused.

Query-preservation replay can use a genuine composition certificate without
re-supplying the original fragment list. The node resolves its source fragments,
graphs, alignment report, and mapping, reconstructs the complete composition
result, and compares both the graph and the complete producer certificate to the
cached content before evaluating preservation. Actual failure-card bodies are
also reconciled. A changed source report can invalidate the composition even
when the graph geometry stays the same. Query caches are operational outputs:
they are cleared and recomputed from the reconciled source/result, never accepted
as causal source authority. All selected source references retain their actual
manifest view for CAS resolution. Newly
supplied source content follows reconciliation instead of the old shortcut.

The prior reconciler and fragment composer admit the declared static DAG/ADMG
graph families before confidence filtering, edge merging, cycle rewrites or
persistence. CPDAG, PAG and MGraph are distinct semantic profiles; even empty or
fully oriented edges cannot authorize conversion into DAG/ADMG. They receive
the existing typed `ValueError` refusal. An original MGraph remains readable by
its missingness consumer; refusal publishes no reconciled graph. This support
boundary applies equally to direct input, supplied method-result content and
selected cached graph references. Other partial/missingness consumers retain
their own contracts; this is not a global ban on partial graphs.

The declared family must also agree with known typed profile contracts. The
reserved `metadata["mgraph"]` payload is an MGraph contract, so static DAG/ADMG
reconciliation refuses it even after a caller retags the graph. A malformed or
null supplied payload receives the same refusal; it cannot become an absent
input. The original metadata is retained, never deleted to make admission pass.
This check uses the existing MGraph contract, not `R_`/`_star` node names or
arbitrary metadata as a missingness classifier. A clean ADMG with those names
and no MGraph contract remains supported. Unknown metadata stays uninterpreted;
this boundary does not establish its semantics or scientific authority.

When discovery requests prior/hint reconciliation for an unsupported graph
profile, it retains the discovered graph and reports the unapplied request in
`DiscoveryPipelineReport.warnings` and its reconciliation metadata. Report
readers must retain that limitation; the request is not successful reconciliation.
Discovery without a reconciliation request receives no reconciliation warning.

Within its admitted families the reconciler supports known contemporaneous
directed and bidirected relations.
Reverse-stored arrows are normalized by exchanging their endpoints; bidirected
relations remain bidirected, including parallel directed and bidirected edges.
Unresolved circle/tail-tail endpoints and compact nonzero lags raise the existing
`ValueError` static-profile refusal before confidence filtering or rewriting.
The node also refuses a lagged candidate produced by cycle reconciliation for
static admission. It does not silently remove lag or orient an unresolved edge.

Callers previously relying on presence-only cache success must retain the current
source artifact or provide the actual typed source content. Handle node failure
or the method's unsupported-profile exception explicitly. A temporal application
must supply an established temporal transformation and consumer separately;
these checks do not implement time-unrolled identification or PAG completion.

These are synthetic structural/content-custody properties. They do not establish
empirical discovery correctness, identification assumptions, human approval,
policy readiness, or real-data causal authority.

## Graph source and DAG-only admission

Discovery reports and Scientist hypotheses retain the complete source graph,
including its `GraphType`, endpoint marks, and a typed `GraphProjectionDisposition`.
A DAG-only consumer uses a declared DAG directly or accepts a resolved DAG only
when the receipt binds the complete source and resolved graph payloads and the
canonical profile projector recreates that exact result. Unsupported and
unavailable sources stay attached to the report and do not become actionable
DAGs. Historical reports without a receipt receive a typed fail-closed receipt;
a historical resolved graph is admitted only after exact replay. Explicit null
or malformed receipts are rejected, not treated as legacy absence. The
historical adapter runs only for an unversioned input mapping or explicit schema
1.0 with the disposition field absent; the existing projector recomputes the
candidate and unresolved partial graphs remain typed unsupported. Persisted
GraphHypothesis artifacts bind the schema version in the CAS manifest to the
payload before defaulting or migration. Current writes are exactly schema 1.1;
a version-1.0 artifact is readable only when both its manifest and payload say
1.0 and the historical disposition field is absent. A 1.0 manifest/payload
mismatch, a complete 1.0 shape, a missing current payload version, or an
unsupported version is refused before analysis. The legacy adapter produces a
current typed candidate/refusal; it never turns an unresolved PAG or CPDAG into
an identified DAG. A current schema 1.1 payload with the required receipt
omitted is invalid. Before a current write, the producer reconstructs every
declared nested Pydantic model from its actual field storage, recursively
snapshots standard containers, rejects undeclared model storage, and strictly
revalidates the complete GraphHypothesis tree. It writes that rebuilt object, so
a nested model-copy or model-construct value cannot pass the writer and then
fail the reader's ordinary schema validation. This path does not trust nested
`model_dump` output. Shared analysis and projection entrypoints reconstruct the
full model-field snapshot (including nested edges and disposition) before
choosing identity or projection; only class-declared cached-property entries
are omitted from the content hash. Consumers receive that detached canonical
snapshot rather than the caller-owned object that was checked.

The current projection profile preserves only source graphs whose existing
endpoint representation fully determines one supported DAG conversion. Directed
PAG/CPDAG edges retain their known direction, reverse-stored arrows normalize by
swapping endpoints, and static ADMG bidirected edges use explicit latent parents.
Circle endpoints, undirected CPDAG edges, M-graphs, lagged projections, and
unknown endpoint profiles remain unsupported. This is a source-integrity gate;
it does not select valid-completion, invariance, or probability semantics for
PAG/CPDAG identification and does not establish graph truth.

### Shared cache and candidate-constraint boundary

Static cached adjacency consumers rebuild the full graph snapshot and refuse unadmitted graph tags and validate every endpoint pair, lag, and metadata before even no-op cache paths. Reuse is keyed by SHA-256 over the complete strictly revalidated canonical graph content, not caller identity; an equivalent fresh graph may reuse the entry, while any changed field yields a distinct key. The adjacency and c-component least-recently-used caches each hold at most 128 entries, and their values retain only detached canonical data, never the source object. This is an entry-count bound, not a byte-size claim. Discovery audits derive graph CI and automatic trek-rank diagnostics only from the content-bound identity-DAG snapshot. Typed constraint families, their persisted references, and hydrated preview rows drive scope derivation; marker warnings and block-ID prefixes do not. Whenever graph-derived constraint evidence affects a score, unknown assumption status and ranking-only falsification scope continue with that hypothesis into the prior and emitted need. Automatically inferred trek-rank diagnostics cannot become blockers from their graph-declared assumption regime alone. DownstreamUtilityReport and GraphPriorBundle producers bind schema 1.2 in both payload and manifest, and source-identification replay requires those matching versions before recomputing support. Exact manifest-bound schema-1.1 utility or prior artifacts remain labeled 1.1 and are readable only as historical routing evidence with unknown assumptions and ranking-only scope; they cannot enter current source-proof replay. Unknown/future versions and manifest/payload mismatches fail closed. The report warns that source completeness, population, temporal scope, selection, and the distribution Markov assumption remain unknown. This candidate-ranking signal does not pass the separate protected-promotion gate. PAG/CPDAG, projected, and other non-identity graph sources retain a typed skipped-family limitation; explicit algebraic blocks remain separately auditable. Partial-graph CI remains held for the G decision, with no inference from graph labels or endpoint shape alone.
