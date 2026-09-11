# Invocation diagnostics that disclose framework boundaries

Date: 2026-09-11. Lane: `codex/instrument-honesty`; merge base: `cc74d6581`.
Workstream: `invocation-checker-cannot-resolve-http-and-callback-receivers`.
Stage 1 decision, committed and read back before source or test changes.

## Decision and claim boundary

Extend the existing source-derived checker. Choose the admissible explicit
`unresolved_by_construction` route. Registration is evidence of a boundary the
checker cannot resolve; it is never evidence that the receiver executes. A
framework-independent conservative AST classifier is preferable here to a
FastAPI-only call-graph extension: knowing that a decorator syntactically exists
does not establish that its router is mounted, its service container is selected,
or its callback is ever dispatched. Runtime receiver resolution remains outside
this bounded instrument and must remain visible on every invocation.

The instrument measures static reachability of concrete public `src/**/*.py`
callables from project script entries and non-test `__main__` guards, using all
tracked Python files under `src`, `tools`, and `tests`. Helpers participate in
traversal; tests are identified but cannot establish a production terminus.
Imports, annotations, class construction, and registration are not method
execution. A clean delta can establish only the absence of new unresolved direct
paths within this source model. It cannot establish runtime execution, persisted
business receipts, the substance of a gate, complete receiver types, router
mounting, DI selection, event delivery, or callback invocation.

The stdout summary and persisted/read-back receipt will share a measured-scope
sentence and a named omissions list, including HTTP router dispatch, dependency
injection/container dispatch, event-bus dispatch, registered callbacks, reflection
and dynamic receiver/factory resolution. These omissions are unconditional:
absence of a recognizable syntax witness does not establish their absence.

## Repository evidence and composed owners

All tree claims here come from source at the lane merge base, not debt prose.

| Finding | Pinned owner | Observed mechanism and consequence |
| --- | --- | --- |
| INV-01 | `src/polisyos/runtime/quality/production_invocation.py@cc74d6581`, `_graph.walk` | Function/class nodes traverse only their body and return before decorators, defaults, and annotated dependency registrations; framework entry conditions are therefore absent from the graph. |
| INV-02 | Same owner, `_resolve`, `_graph.walk`, `_paths` | Calls require a statically resolved `ast.Call.func`. Passing a callable value into a dispatcher is not a call edge. Concrete construction binds receivers without invoking arbitrary methods. |
| INV-03 | Same owner, `audit_sources` | Unreached candidates are `deferred` or `uninvoked`; framework-mediated uncertainty has no distinct class. A changed framework receiver can therefore look identical to an unused direct-call helper. |
| INV-04 | Same owner, `main` | stdout prints regressions, receipt path, and false runtime-invocation flag, but keeps its detailed limitations only inside the receipt. A zero exit does not name the omitted boundaries. |
| INV-05 | `src/polisyos/runtime/http/routes/public_decisions.py@cc74d6581`, `verify_public_decision_record`, `issue_public_decision_record`, `_service` | Router decorators and `Depends(get_runtime_api_context)` coexist with `_service(request).verify` and `.issue`; a decorator-only fix cannot resolve the request-held service receiver. This is an explicit divergent case, not evidence of runtime invocation. |
| INV-06 | `tools/registry.py@cc74d6581`, `_discover_specs`, `_extract_module_metadata`; `tools/cli.py@cc74d6581` | A `main` forwarding module under `tools/quality/validation` is auto-discovered as a `polisyos-tools validation` command. No static registry or package-script edit is needed. |
| INV-07 | `tests/unit/runtime/quality/test_production_invocation.py@cc74d6581` | Existing behavior covers CLI persistence/recomputation/drift rejection, orphan/test-only calls, construction versus invocation, removed calls, deferrals, lexical shadowing, false branches, project entries, and nested statement containers. AST enumeration supplies exact test nodes; text grep is not a node inventory. |

Composed chain: canonical `_graph` producer -> `audit_sources` diagnostic artifact
-> `audit_repository` complete tracked denominator -> existing `main` persistence
and readback -> unified `tools.cli` invocation and stdout/receipt consumer.
`tools/quality/validation/check_production_invocation.py` will be the thin
non-test bridge, forwarding existing `main`; the production runnable terminus is
`polisyos-tools validation check-production-invocation --base REF --receipt PATH`.
The legacy `python -m polisyos.runtime.quality.production_invocation` entry remains
valid. The wrapper is required for discovery, not a competing implementation.

Surface classification: internal diagnostic CLI and receipt, not public policy
or runtime authority. There is no new API, gate, framework adapter, or service.

## Classification and output semantics

Preserve direct static paths and existing direct-call regression semantics.
Add conservative uncertainty witnesses from the AST rather than a list of
framework names: decorated functions, known callable values passed/stored as
values, and known callable or class registrations. Trace their downstream known
call edges as uncertain too. A witness records its source location and reason;
its claim is only that source contains unresolved indirection. Decorators may be
ordinary wrappers and callback-valued arguments may never be used: that is why
the status is unresolved rather than invoked. Annotations alone remain non-call
evidence; dependency calls embedded in annotations need their expression
inspected without promoting the annotation's type to an invocation.

Status precedence is `static_path`, then `unresolved_by_construction`, then a
valid named `deferred`, then `uninvoked`. A separately recorded deferral does not
hide unresolved framework evidence. `uninvoked` means no resolved direct path
and no recognized indirect witness in this static model, never proof that the
world does not call the function. Every result explicitly says so. The unknown
receiver limitation stays named even when no target symbol can be identified.

`regressions` remains the direct-call regression list. A separate
`unresolved_by_construction` inventory is emitted, with a changed/lost-path
subset that remains loud and deciding. Proposed exit composition: 2 for an
incomplete audit/receipt refusal (UNRUN; no complete verdict), 1 for direct
regressions even when uncertainty also exists, 3 for newly changed or regressed
uncertain mechanisms without a direct regression, 0 for a bounded clean delta.
Every complete verdict says partial coverage and names the omitted boundaries;
zero is never a claim of measured framework dispatch. Existing unresolved
receivers stay in the receipt and summary inventory count, even when unchanged.

Static-path precedence is limited: a receiver can have one resolved direct
entry and an additional unresolved framework entry. The latter remains in its
boundary evidence and the unconditional omissions; a direct path never proves
all possible registrations. A decorator must not create a call edge that
upgrades a handler to `static_path`.

Malformed/unreadable source must produce UNRUN rather than a traceback or a
clean delta. The negative constructs a syntax error in a tracked Python file;
its lack of a complete graph is not an empty finding set.

## Falsifiers and red-first execution

1. Register an async handler through a router decorator and register a plain
   handler by passing it into `add_api_route`. With no direct invocation, each
   must be `unresolved_by_construction`, never `uninvoked` or `static_path`.
2. Pass a concrete receiver method to a callback/event bus/container. Do not
   dispatch it. The receiver stays uncertain; registration must not establish
   invocation. Use an opaque dispatcher name as an adversarial synonym, proving
   the mechanism is not keyed to a hand-enumerated framework list.
3. Bind a dependency through an annotation/default registration expression and
   place a real direct callee behind a decorated handler. Both the registration
   target and that downstream known callee remain uncertain.
4. Include an unrelated uncalled verifier alongside those registrations. It
   remains the direct `uninvoked` class, and the mixed result exits 1 while still
   showing unresolved coverage. Test-only registration cannot exempt a source
   mechanism from direct regressions.
5. Remove the only direct call while preserving a callback registration. The
   mechanism leaves `static_path` and becomes a newly unresolved regression
   (exit 3), rather than quietly passing because a reference remains.
6. Run the actual unified CLI on a tiny committed fixture repository. Read the
   receipt and stdout and verify the named omissions at a bounded zero exit;
   construct an uncertainty-only delta and verify exit 3. Corrupt a deciding
   receipt field and require recomputation refusal (exit 2).
7. Construct malformed tracked source and require UNRUN/exit 2 with explicit no
   complete verdict and no traceback. Preserve the original direct-call removal
   and construction-vs-method negatives.

The predicate for source witnesses, source path changes, and direct graph
reachability is `recomputed`. The predicate for actual framework execution is
`not_established` and never carries an invocation claim. Removal probes exercise
the real checker path, not markers or constructor shape.

## Seams, shared files, and acceptance

Owner edits: `src/polisyos/runtime/quality/production_invocation.py`, its package
README, `tests/unit/runtime/quality/test_production_invocation.py`, the thin
validation CLI module, and a discovery/CLI behavioral test if the existing test
file can invoke the unified CLI directly. No HTTP route/service/container code
changes. No invocation authority, callback-runtime implementation, class-type
inference subsystem, or universal Python control-flow solver is being added.

No planned edits to pyproject, lockfiles, lefthook, workflows, or architecture
artifacts. Their effects on other lanes are therefore unchanged by this
workstream. The auto-discovered tools surface can affect generated tool docs or
architecture findings; root owns any required shared repair. Deep-import creep
is reported for an architect decision, never accepted through guardrails sync.

Only named test nodes and named changed-file lint run locally. Root owns the
integrated architecture gate, with complete output retained. The real whole
tracked-source invocation census is permitted (it is this instrument's unit of
measurement, not a broad test suite); persist its complete receipt/log under
ignored `docs/superpowers/journals/instruments/invocation/raw/`. Compare finding
classes and members after traceback/provisioning checks, never bare totals.

Pattern pass: existing P03 (hidden omissions), P10/P18/P38 (direct source proxy
mistaken for invocation coverage), P01/P02 (CLI discoverability), and P35
(complete AST denominator) guide the change. The target pattern is one bounded
producer with one classification and output contract, consumed by both CLI
surfaces, with negative tests and persisted/read-back evidence. At Stage 1 the
new uncertainty surface is `verification_missing` and `semantic_test_missing`;
framework resolution remains `surface_out_of_scope` for this instrument, with
runtime quality as the destination for any future receiver-resolution work.
P40 bucket rule: a newly missed registration syntax is the same uncertainty
class, not a new runtime feature request. After a second escape widen the
syntax mechanism or document/falsify the bounded residual; do not add an endless
framework-name list. Explicit dynamically selected/string-based registrations
are the declared residual, always named in output. The smallest full closure
would require runtime/framework-specific provenance, which this AST instrument
does not supply.

Acceptance is the CLI/receipt distinction under these negatives, preservation
of direct-call detection, a real diagnostic run with readback, and the root
completion journal stating the exact emitted omission sentence. No hosted CI
claim follows from this work.

## Execution refinement after Stage 1

The first original subprocess CLI test exceeded its 180-second ceiling during
recomputation while eager `runtime.quality` package imports were still running.
That is a harness non-receipt, not a changed checker finding set. Pure AST and
CLI-main semantic tests will load the exact canonical stdlib-only module through
`importlib.util`; this does not stand in for packaging evidence. One separate
real `polisyos-tools validation check-production-invocation` process supplies
registered-command integration and a persisted/read-back repository receipt.
No eager package facade is refactored. The completion journal retains the
original timed-out output and the interrupted import run separately from the
completed isolated red/green gates.

A self-generated adversarial callback probe found the same deferred-dispatch
class one level deeper: a registered lambda's body was previously traversed in
the enclosing entry scope, incorrectly creating a direct path. The mechanism
now gives lambdas and generator expressions separate unresolved scopes rather
than evaluating their bodies as surrounding calls. Generator first-iterable
evaluation is conservatively unresolved in this model; generator resumption
and deferred lambda execution are explicitly named in every omissions list.
This is one widening of the deferred-body class under P40, not a framework-name
patch. The retained negative registers each deferred expression without running
it and requires its downstream verifier to remain unresolved.

Root review identified generator functions and unawaited coroutine functions as
the second finding of this same deferred-body class. Under P40 the final
mechanism separates execution scopes structurally: async functions, lexical
yield/yield-from functions, lambdas, and generator expressions stop direct-path
traversal and seed only unresolved-body traversal. Yield detection excludes
nested lexical scopes. Explicit await/next resumption is deliberately not
resolved; it remains named as unmeasured instead of introducing a runtime
resolver. The acceptance adversary also places a nested generator inside an
ordinary function, proving that an inner yield cannot taint the outer body's
otherwise direct call. This is the stopping boundary for the class; further
examples of actual dispatch/resumption remain the declared unresolved class.


## Final-census refinement: declaration/walk domain parity

The first full registered repository run failed internally with KeyError and
produced no receipt. It is UNRUN/no complete measurement, never a finding
comparison. A one-file direct audit retained the traceback in
`journals/instruments/invocation/raw/conditional-declaration-traceback.log`:
`src/polisyos/berl/adapters/_linear.py:95` uses a generator expression in an
`if` predicate. The declaration pass omitted every `If.test`, while the call
pass visited it and required the missing deferred scope. Object lifetime is
not the demonstrated cause.

P40 bucket: this is a NEW construction-completeness class (two traversals with
different AST domains), distinct from the already-bounded runtime resumption
class. Close it structurally: both traversals consume one grammar-derived
active-child selector for statement/expression containers, with the same
intentional literal-condition/TYPE_CHECKING pruning. Lexical scope entry remains
owned by the existing declaration/register mechanism. Deferred conditions stay
explicitly unresolved; this does not teach the graph how any generator resumes.
No parser, framework resolver, package facade or production caller changes.

The internal child selector is consumed only by existing `_graph`, whose
non-test caller is `audit_repository` through the registered
`polisyos-tools validation check-production-invocation` command. It is not a
new command or public capability. CLI measurement inability, including internal
exceptions while constructing/recomputing the report, must print UNRUN, a named
exception class/reason and no complete verdict, returning 2 rather than escaping
to the wrapper as an ordinary failed measurement. No stale success receipt may
be presented as the result of that attempt.

Falsifiers: generator and lambda expressions in conditional predicates (also
nested/conditional-expression forms), preserving direct orphan findings in the
same input; constant-pruned and TYPE_CHECKING branches remain excluded under the
existing scope; ordinary direct predicate calls remain discoverable. Inject an
internal construction exception and require UNRUN/2 with no produced receipt,
while complete direct/unresolved diagnostics retain their distinct exits. Run
the focused explicit tests and the original one-file witness first. Only after
review/freeze may root repeat the expensive registered full denominator. Shared
config, architecture, lockfiles and other lanes remain unchanged by this repair.
