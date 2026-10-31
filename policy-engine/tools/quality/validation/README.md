# tools/quality/validation

Validation ratchets for docs, benchmark contours, CI policies, and quality baselines.

Use the unified entry point:

```bash
polisyos-tools validation --help
```

## Dynamic import inventory

`architecture/imports/dynamic.toml` records source-owned dynamic import patterns. The
`decomposition_preflight.py` gate derives its expected rows from `collect_dynamic_imports`
and rejects missing, stale, or malformed inventory. The collector analyzes syntax and
source bindings without importing or executing the inventoried modules.

For an immutable source-owned `MappingProxyType` with fully known builtin literal keys,
exact .get(...) and subscription lookups follow Python's key equality and duplicate-key
behavior: only the effective value selected by an exact key contributes an importer target. The bounded lookup keys are builtin hashable literals and recursive tuples of those literals.
Mapping membership is a separate source-analysis path and is not broadened by this exact-lookup
change: existing string-membership and tuple-route controls remain unchanged, while the probed
exact-integer-membership guard followed by lookup remains fail-closed because that path has not
established the selected value. Dynamic or unresolved keys, unknown mapping unpack, unhashable
literals, and user-defined key behavior remain ambiguous and do not become an empty/default allowlist. A finite target list is derived
from the selected source-bound importer values; it does not issue or renew owner review
metadata in `dynamic.toml`.

A selected source class can retain its nominal, unshadowed identity after an
opaque call or store invalidates its mutable-member summary. Deferred-call
analysis then conservatively treats every tracked importer/guarded root as
relevant: a later rebind still refuses inventory, while an unchanged namespace
is not rejected merely because an ordinary exception class escaped. The temporal
predicate follows the full finite selected-base closure, including every joined
alternative and nested binding carrier. Unknown bases, unsupported leaves,
decorators/metaclasses and bounded traversal uncertainty conservatively widen the
root set; they never establish absence of effects. Model, field and method
summaries remain invalidated and cannot authorize importer selection. This is a static selected-source/temporal guarantee, not proof of
arbitrary code injected by an external callback or of runtime class immutability.

The actual nominal-bridge discriminator starts with a passing finite fixture,
restores the former invalidated-summary proxy at the nominal lookup only,
requires the original class-resolution refusal, and then restores the passing
inventory. Removing only deferred dependency-name collection does not remove the
whole rebind protection: the independent unmodeled-call/module-time guard can
still refuse the changed root. That redundant refusal remains required; an
extracted state without the second guard is not evidence of a false-green full
collector. These controls retain compact per-case deciding receipts in scratch.

## Docs lifecycle removed-reference scan

`check_docs_lifecycle.py` keeps the lifecycle checker and CLI surface. Its removed-stub reference scan is implemented by `docs_lifecycle_reference_scan.py`; the facade supplies the current repository enumerator, reader, selector, finding type, and path formatter through a typed dependency value. This preserves injected test enumerators without mutating scanner module globals. The scan receipt remains scoped to this one check. Excluded, opaque, or malformed inputs continue to produce partial or ambiguous coverage rather than a complete lifecycle-gate claim.

The default `--reference-scope exhaustive` retains that full tracked-byte question:
opaque, excluded and malformed inputs leave it UNRUN. CI and the path-aware docs
gate explicitly use `--reference-scope live-authored` to check a different,
operational contract: known removed topology references in maintained authored
text, plus removed-directory presence across **all** tracked paths. The receipt
lists the selected suffix/name grammar and the complete path counts and digests.
Observed per-file-type counts reconcile tracked, selected and outside-scope paths;
the path-role counts reconcile the same complete denominator.
Markdown, MDX, reStructuredText and HTML remain selected inside test fixtures and
vendor trees. Source/config text and research scripts remain selected. Maintained
component roots take precedence over ambiguous output-directory
names such as a frontend feature named `runs`. True environment/dependency roots
remain outside the authored-reference claim. Test source literals, fixture
payloads, dependency locks, vendor payloads, non-documentary
research/archive records and named captured-source directories are outside this
authored-reference claim. No absence claim is made about their contents.
The text check runs after the existing editorial documentary-role projection
(journal records, declared historical audits, archive-member fields and columns).
Those role markers do not prove record authenticity, currentness or authority.

Unknown file types are outside the explicitly named text grammar. Unreadable,
malformed JSON or opaque inputs **inside** that grammar remain blocking UNRUN;
non-text control bytes, including NUL in valid UTF-8, also leave it UNRUN.
Live stale document references and source/config path literals still fail. The
live-authored CLI prints compact counts/digests and all findings, avoiding copied
payloads and per-file operation arrays; Python callers can inspect the full
in-memory scan receipt. Other lifecycle checks and their failures are unchanged.

## Directory-health dashboard composition

`directory_health.py` remains the CLI and report facade. Its dashboard metrics and inventory
aggregation live in `directory_health_dashboard.py`; calls receive the active facade dependencies,
so report generation continues to use the same tracked-file, filesystem, contract, and finding
inputs as the CLI and imported API.

## Repository-structure inventory

`repository_structure_phase0.py` retains the CLI, gate composition, and compatibility facade. `repository_structure_phase0_inventory.py` owns the inventory scan; the facade passes its current helpers and policy constants as typed dependencies so existing callers and monkeypatch seams continue to work.

### Docs review, ADR compilation and production-quality inventory

`check_docs_review.py` keeps the review CLI and current facade configuration;
`docs_review_git.py` owns Git window selection, while `docs_review_artifacts.py`
owns review artifacts and retained command logs. Dependencies are supplied from
the facade for each call so current output roots and command callbacks remain active.

`generate_adr_index.py` keeps the CLI and current path configuration.
`adr_index_compiler.py` owns ADR parsing, classification and index compilation;
the facade supplies its current paths to the compiler. Generated output ownership
and check behavior remain unchanged.

`production_quality_evidence_inventory.py` keeps the inventory entry points.
Its `_bindings`, `_contracts` and `_reports` siblings own source binding resolution,
inventory contracts and producer report specifications. CI and Wave40 consume this
static inventory in their existing roles; the inventory does not establish that
those producers ran for a current transaction or authorize publication.

### Honest diagnostics and trust posture

`build_honest_diagnostics_coverage.py` owns the coverage CLI, rendering and current
configuration. `honest_diagnostics_coverage_metrics.py` owns metric definitions,
parsing and calculations; the facade supplies its current contract bindings and
keeps the existing one-argument validation callback.

`check_trust_claim_posture.py` remains the compiler facade. Its contracts, tokenizer,
source bindings, accessibility, semantics and artifact-lifecycle siblings own the
corresponding calculation families. The facade supplies current callbacks for each
call, including the probe-repository adapter used by source read-receipt checks.
The existing source owner, generated artifact contract and output paths remain in
place. These source extractions require behavioral and removal checks before any
native-gate completion claim.
`directory_health.py` remains the CLI and report facade, while `directory_health_dashboard.py` and `directory_health_inventory.py` own dashboard composition and bounded-retention path inventory. The inventory streams the existing tracked, ignored, raw, and filesystem scopes; consumers apply selectors during traversal and preserve required output rows and ordering. A Git iterator is complete evidence only after exhaustion, and the report-only Git fallback is not a completeness authority; native behavior and resource acceptance require focused tests and actual CLI-output readback.

`check_layer3_gy_promotion_contract.py` remains the CLI and compatibility facade. It passes the current confidence-ledger session, output path, and registered epoch-reissue callbacks into private owners so existing imports and monkeypatch seams remain active. `layer3_gy_n9_contract.py` builds the live contract through `polisyos.runtime.quality.promotion_sequence`; `layer3_gy_n9_comparison_custody.py` owns frozen comparison identity and authorized epoch transitions; `layer3_gy_n9_promotion_mutations.py` owns behavioral and source-flip probes; and `layer3_gy_n9_contract_inputs.py` owns typed synthetic inputs. The artifact path, schema, CLI, promotion authority, and registered tests remain at their existing surfaces.

`check_layer3_gy_openalex_artifacts.py` remains the CLI and validation facade. `openalex_span_evidence.py` owns recorded-provider population, extractor-accuracy recomputation, and candidate SKG proof production; the facade supplies its active source paths, readers, provider callback, digest, strangle check, and storage factories per call. The existing literature, SKG, generated-artifact lifecycle, history-integrity, and adjudicator-authority owners remain authoritative. The extraction does not promote accuracy or change generated-artifact identity; its bounded recorded-response population must not be described as the global/live OpenAlex population.

`architecture/packages/*.toml` remains the primary package-row source; this nine-file R3 slice aligns twelve routine fields with the current public-surface aggregate. The `polisyos.runtime` / `polisyos.runtime.quality` G route choice remains unresolved, and the package-mirror writer plus its runtime/consumer path are outside this source slice and unverified.

### Phase 0 global registry validation

`repository_structure_phase0.py gate` reconciles active exception targets against the complete set of ordinary gate findings, even when `--gate` selects one gate. The `--package` and `--scope` options project local policy findings; global repository-input, name-registry, and exception-registry refusals remain visible and contribute to fail-closed status. An active exception must match a current ordinary gate finding, and registry-integrity findings cannot authorize exceptions. Filtered command output is scoped evidence, not a substitute for the complete-gate reconciliation.

### Q2 portable build-tool profile

`q2_build_tool_wheel_lock.py` validates the source-bound Hatchling backend profile, complete universal-wheel lock, PyPI release witnesses, exact wheel metadata and `RECORD`, and the selected source Git/archive bytes. The profile body lives at `architecture/packaging/q2_build_tools.toml`, selected by the exact `pyproject.toml` `[tool.policyos.q2_build_tools].profile_path` pointer. `hatch.toml` includes that profile in the sdist; the source-audit capsule and Q2 runner reconcile pyproject, profile, helper, and lock against all four exact Git and archive inputs before offline build-tool preparation. The Q2 runner owns the isolated offline installation and records the host interpreter, platform, uv, installed origins, and entry-point observations separately from portable artifact identity. This dedicated profile is not a claim that the general project `uv.lock` locks Hatchling. It does not validate the packaged-resource manifest or authorize installed-wheel consumers; run the full source audit's `prepare` and `check` after the final source/input freeze before that consumer wave.

`check_trust_claim_posture.py` remains the compiler, CLI, generated-output writer, and compatibility facade. The tokenizer, source bindings, accessibility, semantics, and artifact-lifecycle siblings own their corresponding calculations. The facade builds a typed dependency value for each owner call from its live readers, paths, selectors, predicates, and callbacks. The existing facade bindings remain present, including the `shutil` and `subprocess` module objects, `_minimal_probe_repo`, `evaluate_accessibility_evidence`, and `evaluate_scope_assumption`. The source compiler, generated-artifact contract, schema, CLI flags, and output paths remain at their existing surfaces.

The source-census gate now asserts the complete denied-site composition by category, source path, symbol, and values, then requires the independent AST and token walks to agree. The frozen-source focused census case passed on 2026-10-18. Full Trust, measurement, and custody suite completion is still required before any native-gate completion claim.


### Selected source code reconstitution

The dynamic-import collector retains selected function `__code__` captures as a distinct,
byte-bound code identity. A later mutation of the original function invalidates later function
lookups; it does not rewrite an earlier captured code origin. Plain selected class methods are
unbound code bodies: reconstructed invocation receives its explicit receiver through the normal
source-function parameter binder. Finite code alternatives join through the existing binding
algebra, and reconstructed bodies use the same selected-source invocation/effect interpreter.

The admitted constructor is the resolved standard-library `types.FunctionType` binding, with
same-origin live module globals, native construction-time builtins, no supplied defaults/closure,
and no free cells in the captured code. The original function's defaults are not copied. Rebinding
the globals `__builtins__` entry after construction does not replace the reconstructed callable's
saved native builtin namespace. Known global writes are read at invocation; unresolved namespace
effects, foreign globals, constructor replacement and opaque code remain refusals.

Nested selected callbacks may carry stable parameter cells through selected-source dispatch.
Mutable/unknown closure cells, reconstructed callable mutation, unsupported executable-value
escape, opaque executor/context dispatch and unknown callback targets fail closed. Original
function mutation and unsupported exposure share a code-identity invalidation owner; reached
opaque dispatch/mutation marks source effects unresolved for subsequent construction/invocation.
An uninvoked declaration's local effects do not mutate the module state. The supported unit is
selected body/callback effect transfer, not arbitrary Python runtime equivalence or executor
execution. In particular, the actual Runtime guard's opaque executor/context route is still a
bounded limitation; recognizing its constructor does not establish full collection clearance.

The binding constructor aggregates actual negative capability across immutable semantic
children and nested containers. Each child has already normalized its own payload, so the
aggregate is complete by construction without repeatedly walking the whole dependency graph.
A bound callable owns its receiver; a receiver retained only as analysis context for an
ordinary result does not become that result's executable payload. Shape ambiguity by itself
has no executable origin. Type-erasing projections preserve actual origin through the shared
unknown-projection/join law; a bare guarded fallback cannot manufacture code identity.

A verified selected class whose constructor or value protocol cannot be summarized retains
an opaque-payload capability when its inputs carry an actual importer, importer namespace,
executable source value or another opaque payload. That capability follows aliases, containers
and unknown joins and refuses selected-call intake even when the selected body ignores the
argument. An ordinary scalar payload and an unconsumed deferred object remain non-failing.
An unselected symbol is not promoted to a verified class merely because the existing abstract
interpreter represented its result as an object.

Unmodeled operator results retain a separate unresolved-callability fact for direct invocation.
During protected reconstructed-body transfer, unsupported unary, binary and rich-comparison
operator dispatch refuses rather than hiding implicit callbacks. This does not establish
arbitrary Python object-protocol equivalence in ordinary declaration analysis. The existing
opaque executor/context boundary remains unsupported and fail-closed before protected
reconstruction or invocation; constructor recognition alone does not clear Runtime resilience.

Unknown joins retain executable origin through the existing guarded-origin transfer, including
nested containers, reflective selections, return/storage escapes and unresolved call targets.
That private origin carrier is negative provenance: it requires refusal when body identity was
lost, and never admits code merely because an origin field is present. Proven pure extraction
and length projections may discard executable provenance because their values cannot execute
that code. A semantic join-transfer removal test preserves fields and source markers while
requiring the unknown-join refusal to disappear and restore.

Behavioral coverage is in `test_dynamic_code_reconstitution.py`. Its callback discriminator removes
only reconstructed body transfer while retaining captured-code, constructor, globals and import
source; the callback effect must disappear and the exact method/inventory must restore. Registry
schema, owner review dates and public authority remain owned by the existing registry workflow.


An ordinary selected source call that the collector deliberately does not transfer in a deferred
scope is an opaque source effect for any later protected reconstruction/invocation in that analysis
path. Nominal selected identity alone does not establish absence of mutation. Module-time and active
source-body calls keep the existing transfer engine; unknown deferred effects fail closed until a
sound transfer exists. This is a bounded limitation, not a claim that arbitrary cross-entrypoint
runtime ordering or externally injected code is modeled.

Protected selected source bodies pass a default-deny AST intake for implicit protocols. Unknown
expression, statement, and operator forms refuse; truth tests, formatting, hashing, subscripting,
iteration and other implicit effects are admitted only where their relevant literal operands are
immutable builtins. Explicit calls still use the existing call-transfer owner, and protected
context is carried into a selected helper in another module. The post-body intake also applies
its own syntax-bound refusal after explicit call transfer: module attributes are refused unless
their receiver is an immutable literal, even when the call transfer recognizes the importer. An
abstract module name and selected-source write census do not independently verify a runtime
module object's identity, attribute protocol, and slot stability at the use. Precise admission would
require such use-site evidence; it is not supplied by this source analysis. Direct imported-call
bindings remain a separate supported path. This bounded limitation is not native compatibility
clearance, and arbitrary object lifetimes, finalizers, ambient concurrency, and external protocols
remain unmodeled.

When finite carrier shape is erased, the sequence and mapping constructors retain actual member
origins. Comprehensions retain the produced element, key and value, not their control inputs. A
known mapping spread into a sequence contributes keys, never unrelated values. Exact pure scalar
projections retain their existing ability to drop origins. Bounded fixture checks do not establish
source-wide or native clearance.

Dictionary-display ordering remains unresolved: the collector currently visits a value before its
key, although Python evaluates the key first. A key assignment can consequently produce a stale
allowed target and a matching registry can validate it. Reversing the traversal alone is not a
complete repair: a selected helper's conditional global writes can leak from one analyzed branch
into another. A safe repair needs branch-local namespace effects and joins, with semantic controls
for both evaluation order and helper effects. Deferred generator consumption, mapping-spread
protocols, custom hashing and equality, exceptions, and external effects also remain unmodeled;
controlled examples of generator consumption and custom hashing produce a wrong concrete target
while the matching registry validates. These examples do not establish a repository-wide verdict.
