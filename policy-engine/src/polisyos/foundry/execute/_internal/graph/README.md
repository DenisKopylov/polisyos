# Native program graph execution

This private package owns `execute_program_graph`, the orchestrator behind the
existing Foundry executor facade. Its public binding remains that single
function; Treasury admission and key-fold helpers are private implementation
details, with no new facade chain or runtime registry.

The compiler now selects `randomization:treasury_salts_v1` in `ExecPlan.notes`
and binds its persisted Treasury plan through the execution manifest. This
reader validates the selected CAS input views, program/lowered-IR lineage,
root seed and complete salt maps before native mechanisms or registered
methods execute. It folds each stream/node salt's low and high 32-bit words
into the effective base key. An explicit execution seed overrides that base
key while salts retain their compile-root binding.

Unmarked plans retain the historical sequential RNG law and low-level default
zero seed. Marked plans use the compiled seed when the low-level argument is
omitted. The public execute facade retains its existing posture resolution.
No timestep fold, slot identifier, economic model law or family-to-runtime
mapping is added. Recompilation intentionally selects the new versioned law;
historical artifacts remain replayable directly.

See the [profile and migration contract](../../../../../../docs/reference/foundry/randomization-profile.md)
and the [canonical salt owner](../../../compile/randomization.py).
Native compiler/CAS/state-consumer tests and independent word-order/selected-view
controls establish bounded synthetic determinism. They do not establish family
state activation, general randomness quality or economic validity on real data.

## Method-metric capture

When the selected ExecPlan manifest contains one `method_metric_bindings` edge,
the graph executor reconciles that edge with the binding-set payload and its
program-graph, policy, registry, metric-registry, and units-registry edges before
dispatch. It records all plan positions and invocation outcomes. One
`MethodExecutionCapture` can be carried across repeated graph calls so feedback
iterations and terminal execution retain distinct occurrence IDs in one
bundle. Selected scalar outputs and JSON sidecars are written once to CAS;
non-selected values are inventoried by bounded type/shape/codec metadata without
retaining their array contents. Unsupported or unbounded values remain explicitly
unavailable.

The selected bundle and output refs preserve their manifest profiles. A
pre-dispatch environment manifest is recorded separately from the actual
per-dispatch backend trace. Any binding-bearing graph call creates or joins the
same capture mechanism. The public Foundry API carries one capture across
feedback iterations and terminal execution; the program-graph horizon carries
one capture across each physical run and preserves full selected-profile refs
and occurrence inventories in its trajectory rows. The existing LocalBackend
consumer retains producer artifacts, while AD02 owns the JobResult projection.
The default WorkspaceLoop and registered S2 routes do not call this graph
producer, and no policy-authority claim follows from the capture.
