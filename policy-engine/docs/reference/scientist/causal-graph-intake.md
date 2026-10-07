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
graphs, alignment report, and mapping, reconstructs the complete composed graph,
and compares it to the cached graph before evaluating preservation. Newly
supplied source content follows reconciliation instead of the old shortcut.

The reconciler supports known contemporaneous directed and bidirected relations.
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
