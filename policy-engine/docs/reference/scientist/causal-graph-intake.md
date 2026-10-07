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
