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
dispatch. An exact profile-bound binding set with `bindings=[]` enables capture
of actual method dispatch and bounded returned-slot/artifact inventory only. It
establishes no scalar law, selected output payload, metric vector, or verified
projection; scalar admission remains `verification_missing` until explicitly
selected bindings pass the existing verifier. The executor records all plan
positions and invocation outcomes. One
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


The selected plan adapter permits only PURE method returns in its current capture
path. Their exact registered return slots remain bound by the source plan and
metric-binding artifacts, but they are not ProgramGraph state patches. The current
bridge rejects a planned method or lowered mechanism that consumes such a return,
including a dependency-reachable alias, before persisting the graph; it also rejects
non-PURE methods and method reads from lowered mechanism outputs. The dispatcher
captures only the selected output occurrence for the existing fresh point/unit
consumer. This limitation is explicit; no general method-to-method dataflow is
claimed.

## Opt-in method artifact sidecars

Public `execute(..., artifact_output_codec="bounded_v3")` selects only the existing
`MethodResult.artifacts` → `MethodArtifactOutputPayload@1.0` sidecar chain. Its
normal default is `legacy`; metric input capture, returned outputs, bundle, state,
cache and journal writers keep their current profiles. The explicit request is
not a readiness boolean: Core recomputes the scoped source/backend/value/profile
and real selected readback before publication. Unsupported artifacts retain an
`unavailable` row with a limitation; inventory `captured` means keys were inventoried,
not that each sidecar succeeded. Counters charge successful actual wire bytes.

The existing logical payload domain is at most 1,024 nodes and depth 8, with
4,096-bit integers, 65,536 wire bytes, 4 MiB aggregate sidecars and 8,192 refs.
The explicit policy `foundry.method_artifact_output.canon3/1` derives physical wire
node budget `7N-2+2*field_count = 7,178` and wire container depth
`1+3*(L+1) = 28`; `CanonSpec.max_depth = L+1 = 9` remains logical. The source
resource owner adds a 4,096-byte output-manifest cap, with exactly three selected
source input roles and its revision in existing ProducerInfo. These quantities
are separate and are enforced against actual bytes/structure, not only formulas.

The cohort accepts exact primitive JSON objects/lists/scalars, finite floats
except signed negative zero, and nonempty exact string keys. Tuple, Decimal,
bytes, models/carriers/custom mappings are unqualified and refuse before callback
or fallback. It does not replace the distinct Foundry static-parameter
float-hex/bytes/array descriptor projection or enable other `.3` cohorts.
Public `read_method_artifact_output_bounded` reopens the selected typed sidecar
even with writes disabled; Inspector uses that source-owned consumer.
