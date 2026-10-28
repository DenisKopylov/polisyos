# Foundry Method Selection

`polisyos.foundry.methods.selection` owns method lookup, version resolution,
selection advice, registry persistence, and execution-history feedback.

## Home

- `registry.py` is the canonical method registration path.
- `resolution.py` owns version policies and semver helpers.
- `advisor.py` owns planner-facing ranking and recommendation APIs.
- `history.py` owns execution-history telemetry used by the advisor.
- `cache.py` owns registry persistence cache helpers.
- `cost_model.py` owns selection cost estimates and budgets.

## Registration Path

Builtin catalog families register through `catalog/*/_registry_boot.py` and
call `selection.registry.MethodRegistry.register()` or `register_lazy()`.
`foundry/extensions/registry.py` exposes
`bootstrap_foundry_method_registry()`; when invoked, it discovers external
entry points through `foundry/extensions/discovery.py` under
`polisyos.foundry_methods`. The registry passes the component index through
`methods/components/bridge.py`, which registers valid method classes with
`selection.registry.MethodRegistry`. Selection remains the owner of method
registration and version resolution; extension discovery and component
validation stay at the extension boundary.

## Observation route constraints

`MethodRouteConstraint` is a candidate search constraint. It does not certify a
manifest, observed data, or method validity. The selector rechecks every allowed
method against its actual input contract and preserves the native value-output
gate. The runtime manifest owner derives the constraint from source; direct raw
nested manifests refuse rather than becoming empty hints. An explicit requested
method cannot escape the allowed route.

Cross-component consumers import `MethodRouteConstraint` and
`method_accepts_input_contract` through the stable `polisyos.foundry` facade.
The facade lazily exposes these exact existing owner objects; it adds no wrapper,
parser, evidence authority, or change to this internal implementation's maturity.

Selector context v4 binds the complete effective constraint. Selection receipt v2
retains its existing shape and authority labels. Prior context hashes remain
historical; replay requiring current semantics recomputes the v4 context from source.

## Persistent selection history

The process-global execution history is runtime learning telemetry. It is durable user state, not a disposable cache or an authority record. Its default output location is independent of the checkout and installed package:

- macOS: `~/Library/Application Support/PolicyOS/foundry/selection_history/executions.jsonl`
- Linux: `$XDG_STATE_HOME/polisyos/foundry/selection_history/executions.jsonl` when `XDG_STATE_HOME` is absolute; otherwise set it to an absolute path or leave it unset to use `~/.local/state/polisyos/foundry/selection_history/executions.jsonl`.
- Windows: `%LOCALAPPDATA%/PolicyOS/foundry/selection_history/executions.jsonl`; `LOCALAPPDATA` must be set to an absolute path.

Set `POLISYOS_FOUNDRY_STATE_HOME` to an absolute root to choose a different location. The history owner appends `foundry/selection_history/executions.jsonl` beneath that root. Set the override before the first `get_global_selection_history()` call in each process. Empty, relative, unexpandable, or physically unresolvable roots raise a typed error; they never fall back to another directory. Existing symlink roots resolve to their physical target. Missing output directories are created only by the existing persistence writer.

The getter does not discover or import history from an earlier checkout path. To adopt old rows, stop all writers, verify the destination does not already exist, explicitly import the old JSONL with `SelectionHistoryStore.import_jsonl(path=...)`, and export to the new store. Verify the count and representative successful, failed, and telemetry fields; compare the old file hash and retain the original. `import_jsonl()` is append-oriented, so review before repeating it. Existing explicit `persist_path` and `MethodDispatcher(runtime_history=...)` behavior is unchanged. Failed appends remain visible through the store's persistence issues instead of selecting a fallback path.


## Registry typing ABI

`registry.py` is the canonical runtime contract, and its `registry.pyi` is a member
of the single Foundry method-stub generated family. Regenerate it together with
base, canonical composer and both compatibility facades using
`polisyos-tools foundry generate-stubs`; never hand-fix a missing provider symbol.
The generator derives source signatures, actual public exports and Enum semantics;
strict staged consumers check lifecycle exports, entry/factory types, snapshots,
context managers and audit-export path inputs. The former provider stub omitted
`MethodLifecycle` and lagged source defaults/fields/frozen snapshot behavior;
regeneration follows actual source while preserving supported useful API shapes.
