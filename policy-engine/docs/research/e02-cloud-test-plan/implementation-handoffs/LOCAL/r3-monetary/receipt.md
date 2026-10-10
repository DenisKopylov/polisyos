# R3 monetary verification receipt

This is a source-author readiness receipt for parent review. It makes no formal
finding closure and no external provider billing claim. Root owns Git
operations and the global freeze decision. This candidate is ready for an
independent delta review after the raw-input and owner-bound route falsifiers.

The LLM cost path retains four distinct origins: `reported`, `estimated`,
authenticated `reuse`, and `unknown`. Raw gateway reported zero stays zero;
negative, non-finite, malformed, and binary-float-underflowing amounts stay
invalid and settle as unknown. Missing cost is estimated only with valid usage.
Unknown is nullable through the producer event and local durable ledger.

`TracedLLMClient` emits an observer row when the physical producer event settles,
including when the initiating caller or cache owner is cancelled. All uncached
and unauthorized cache bypasses use the same producer begin/settle mechanism.
Authenticated reuse remains a separate zero-amount event linked to the physical
provider event. A `FileBudgetLedger` under
`core_runs_root/.runtime/llm-cost-ledger.json` is the ordinary runtime default;
NL runs use `nl-run:{run_id}` and include current tenant/cell scope in the
producer request digest. The ledger records observations and adds no spend
limit. The producer event's model and logical route are pinned before dispatch
from configured gateway intent. Response-declared labels remain
non-authoritative metadata and cannot alter event identity or estimate pricing.

The simulated NL producer test exercises reported zero, missing-cost estimate,
invalid-cost unknown, admitted cache reuse, and a same-key flight whose owner is
cancelled. It verifies persisted preflight/model-variant rows and reopened
ledger equality. A separate ordinary-route test submits a real NL POST, checks
the created event/outbox, dispatches the worker, binds the indexed run to its
persisted ControlJob owner, reopens the app ledger, and serves a fresh
`GET /api/v1/runs/{run_id}/agents`. It inserts a durable begin-only event at the
crash boundary and confirms fresh GET serves pending as unknown with null
amount and ledger durability. This is a crash-boundary simulation; it does not
kill a process between filesystem operations. The maintained insights consumer
fixture also starts from this real POST/job/run owner chain before writing
typed durable cost events.

The DTO/read-model projection preserves origin, nullable amount, settlement,
durability, receipts, payload digest, and pinned producer identity. Compiler/
preflight and model-variant events remain distinct steps. Identical event IDs
deduplicate across persisted sources; owner conflicts, payload conflicts, and
ledger-durable markers without a matching exact ledger row refuse the read.
CAS readers pass selected `ArtifactRef` values into verify/read operations.
ControlJob payload reads derive exact manifest profile from persisted CAS
metadata only after the manifest kind matches the server-owned job kind.

Funnel duration/configuration values remain `estimated`; the VOI consumer
retains unknown rows without training them as zero and labels heuristic cost
history separately. This does not establish native evaluator work/draw counts
or scientific price calibration.

## P40 classification

The first escape was producer status loss when only token recording notified the
NL observer. A second escape one level deeper was direct cache-bypass provider
work that skipped producer hooks. Both are the same status-loss class; the
mechanism was widened to settlement-time observation and one shared uncached
producer path. Review then found raw gateway JSON could collapse literal zero
via truthy fallback, clamp negative cost, and convert a nonzero `1e-1000` token
to binary `0.0`. The decoder now selects the first non-null field without
truthiness, retains underflowing numeric tokens until cost validation, and
marks unrepresentable values invalid/unknown. The distinguishing falsifier
passes: actual raw `1e-1000` through gateway request, trace settlement, and
ledger yields unknown/null; raw literal `0` yields reported zero. One lower-core
admission contract handles both gateway JSON and generic response mappings,
including explicit null and alias precedence. Usage parsing preserves
missing/invalid/fractional/negative values rather than normalizing them to zero.
Malformed status discriminators fail closed across producer acknowledgment and
DTO projection without hashing untrusted list/dict values. Treat any further
monetary status-loss escape as this bounded class; do not add per-site patches.

External gateway retries remain a separate bounded evidence gap. The local
client may issue multiple HTTP attempts with one idempotency key, but local
code/tests do not establish provider idempotency or invoice charge count. The
smallest closure is an authoritative provider idempotency/reconciliation
receipt. No such receipt is present; the implementation makes no invoice or
single-external-charge claim.

## Verification

The integrated light command and complete output are in
`final-integrated.log`, with JUnit counts in `final-integrated.xml`: 160
passed, zero failures/errors/skips, and two upstream Torch/Python 3.14
deprecation warnings. It includes the real raw-gateway-to-ledger cases, ordinary
POST→worker→reopened ledger→fresh GET, owner-bound pending projection, selected
CAS profile checks, and malformed status tests. The isolated raw gateway
contract matrix passed 77 cases; full output and JUnit are in
`gateway-raw-contract.log` and `gateway-raw-contract.xml`.

The explicit, nonempty Ruff path guard passed; its complete output is in
`final-ruff-ready.log`. Exact path lists and test commands are in
`ready-manifest.md`. No heavy numerical fit, install, or full backend suite was
run in this readiness turn. The commands in this turn did not generate or edit
the public-surface inventory.

## Owner and merge boundary

R3 owns the monetary bootstrap hunk in `runtime/http/container.py`: typed
`llm_producer_settlement_store` override, default durable `FileBudgetLedger`,
and pass-through to `ControlPlaneService`. R4 separately owns the shared
executor capacity/profile fields and early configure call in that same file;
preserve both hunk sets. V1 owns runtime contract/lifecycle/generation-cycle,
DebugService DTO/read-model, dependencies/route, and dashboard consumer source
changes. The R3 tests exercise the resulting producer-to-GET bridge but do not
replace V1's review. The `run_lifecycle.py` payload reader now matches the
persisted manifest against server-owned expected kind, derives and verifies its
exact profile, and passes the full ref to `get_bytes`.

See `ready-manifest.md` for exact source, test, documentation, release, and
held Linux-wave paths. See
`../reviews/f-original-criteria/F-original-criteria-review.md` for the
read-only, source-bound F 33-ID / 34-occurrence discriminator matrix. Its old
receipts remain bounded to their exact source/profile/input/consumer and do not
formally close any finding.

## Selected-reference receiver delta

This delta was made at source checkpoint
`00c200c2ec33786a80dd41209eca46a2539dac5c` (tree
`5ba74fcb78e28d61be21f3208ee7a4b42665b6fe`, per the root checkpoint note).
That checkpoint is navigation evidence, not a clean R3 slice base and is not
used to classify inherited failures. Before this delta, the working-tree hashes
were `debug.py` `1dd2279882d396196aa9f49c7c4c2b1f6527f8072395c7271cbfce5a1c808ba6`
and `nl_pipeline.py`
`87acb4a2d42af1423f907f09566ebfd1b83a241c003dd7af0617f86e675b12b9`.

The five authorized reads now pass the caller's typed ref through unchanged:
`_agent_steps_from_compiled_cycle` and
`_agent_steps_from_n4_candidate_proposal` each pass the complete ref to both
`verify` and `get_bytes`; `_publish_runtime_quality_report` passes the typed
`authority_envelope_ref` to `get_bytes`. Paired-profile tests store identical
bytes under sibling tenant profiles, exercise the actual debug reader paths,
and assert the selected ref reaches both CAS operations. The existing simulated
NL pipeline test now creates same-content sibling authority-envelope profiles
and asserts its actual publication read receives the writer-issued `ArtifactRef`.
The authority writer persists the profile returned by its envelope `put_json`
call. A producer regression inserts a same-byte sibling view before the
selected view and asserts the payload manifest and idempotent readback retain
the exact producer-issued profile. When a store returns a profileless default
ref, the optional field is omitted and readers use the explicit legacy branch;
readers never compute or substitute a profile.

The paired DebugService test first failed at the expected `ArtifactID` versus
selected `ArtifactRef` assertion for both readers. With the NL call reverted,
the actual simulated pipeline test independently failed on the same receiver
identity mismatch. After the five-call patch, the focused suite below passed.

```text
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA \
  --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/selected-ref-paired.xml \
  tests/unit/runtime/http/test_debug_api.py::test_debug_artifact_reads_preserve_selected_manifest_profile \
  tests/unit/runtime/http/test_debug_api.py::test_debug_cost_readers_preserve_exact_selected_profile \
  tests/unit/runtime/http/test_nl_pipeline_cost_projection.py::test_simulated_nl_producer_costs_settle_and_capture_four_origins \
  > docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/selected-ref-paired.log 2>&1
```

Result: 4 passed, 0 failures/errors/skips, 2 upstream Torch/Python 3.14
warnings, 3.56 seconds. The complete log SHA-256 is
`3238ae045fcef5cb79f28dccbaf7dc0f3e6629730b1cce784543ffbfb2b94da1`; JUnit
SHA-256 is `3467908cb281e32c1c5c81249f8911e3ce5e6a413e865812a4e0b11e5e82e3ef`.
The explicit Ruff check on the two source and two test files passed (`All
checks passed!`). No broad suite or heavy numerical test was run.

Post-delta SHA-256 values: `debug.py`
`d4372f54109d05a8bad797b5ed836e7c67ca2b5984dec4bdb856922015b30ac1`,
`nl_pipeline.py`
`7b5876ceec50ba5a483c097b97f851f8af9c23d5899872de4ee1fe82716f8ab5`,
`test_debug_api.py`
`2fc2b380f46f402e772964a86a22df685964a1571563dc28b2f643c34c13b60c`, and
`test_nl_pipeline_cost_projection.py`
`194364b3bce4d2631ff89a3754931d3cda6c36f06a7d54cb45363dc67117cc5c`.

## Authority-envelope selected-view delta

The canonical `core.artifacts.resolve_authority_envelope_ref` resolver selects
the profile stored on the authority link through `resolve_manifest_by_profile`,
checks the fixed envelope kind, media type, schema name, and schema version,
and returns a typed `ArtifactRef`. Profileless historical links explicitly
resolve the default manifest view. The control writer/readback,
evaluation-safety verifier, N9 legacy source reader, generation-cycle source
reader, Data Forge source verifier, and generic authority surface now pass
that typed ref to manifest, byte, and integrity reads. The writer stores the
profile returned by the envelope `put_json` call in the payload manifest;
missing legacy profiles remain omitted rather than being materialized by a
reader.

The tested source files are:

- `src/polisyos/core/artifacts/{manifest.py,protocol.py,__init__.py,README.md}`
- `src/polisyos/runtime/http/services/control/{artifacts.py,evaluation_safety.py}`
- `src/polisyos/runtime/quality/{promotion_sequence.py,generation_cycle.py,data_forge_binding.py,authority.py}`
- `src/polisyos/runtime/http/services/debug.py` and
  `src/polisyos/runtime/http/services/control/nl_pipeline.py` retain the five
  selected-ref receiver changes recorded above.

Current source SHA-256 values for this delta are:

- `manifest.py` `35b827e49070f9bd664f041c185277c9a059617c54ddd2715b92ace4604f0f9e`
- `protocol.py` `48142e837245c6504b0333f7ce3900201fa4608b1693b3ed64afe8c0985a77b2`
- `__init__.py` `5be402216fdecb5c8e60b6c1822da3befd8e12e6653a3f179d93e2bf533ab904`
- `core/artifacts/README.md` `15c44ef4e5aeced5101577138a5432017cc3aa8826e4badff8b6b86df5eab6fa`
- control `artifacts.py` `f7b78eff841aef105cf22bfdfa8e0b7b9b020a1a8f8eaed053b83878398e6807`
- `evaluation_safety.py` `ae0d901bff26ca6b77e4e1e762916e966c1b61e0c368841af12002a5a55be0f4`
- `promotion_sequence.py` `a6109ef62d9db1c48bb6b2b3ba675d58476a501d714210f0c4dbae04355e2473`
- `generation_cycle.py` `20d53fd7a234abddbd4fc7a2d9169bdc25732c10433ad56670f2ea86a08e3bc3`
- `data_forge_binding.py` `e5608bdfc0a4f218e15e3aad9d9e61783d9a33d58a43646a086093b99b5a2bd5`
- `authority.py` `7e72d6a641a392b72987968c8a72f06d2a9be68d833fe16f201144fd0addb19b`
- `debug.py` `d4372f54109d05a8bad797b5ed836e7c67ca2b5984dec4bdb856922015b30ac1`
- `nl_pipeline.py` `7b5876ceec50ba5a483c097b97f851f8af9c23d5899872de4ee1fe82716f8ab5`

Behavioral coverage stores identical envelope bytes under sibling manifest
profiles and proves that the real generic authority surface reads the exact
profile in its payload link. Controls reject stale profile digests and wrong
kind/media/schema name/schema version. Other selectors prove the legacy
profileless serialized shape, producer `put_json` profile persistence,
idempotent readback, evaluation-safety use, a measurement-root producer path,
and the typed-ref wrong-kind diagnostic.

From `policy-engine/`, the deciding command was:

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest -v --tb=short -rA \
  --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/authority-selected-view.xml \
  tests/unit/core/artifacts/test_authority_envelope_ref.py \
  tests/unit/core/artifacts/test_ir_adapter.py::test_profileless_authority_link_keeps_legacy_manifest_hash_shape \
  tests/unit/runtime/quality/test_authority_reconciliation.py \
  tests/unit/runtime/quality/test_workspace_loop.py::test_measurement_root_producer_resolves_catalog_and_persists_cas \
  tests/unit/runtime/http/services/test_evaluation_safety.py::test_blocked_non_simulation_persists_ordered_chain_without_certificate \
  tests/unit/runtime/quality/test_data_forge_binding.py::test_recorded_panel_binding_ref_kind_is_consumed
```

Result: 18 passed, zero failures/errors/skips, two upstream Torch/Python 3.14
warnings. Complete log and JUnit are `authority-selected-view.log` and
`authority-selected-view.xml`; their SHA-256 values are
`8138e3307327d4f297663b3f62b6dccdcd165cd01e6fb249ca5cb5fd55a66f42` and
`4b35f1017e85be3768f286a8b2df84be36d3ac340f609c950d1eb781f6f86389`.
The explicit Ruff source/test command and source `py_compile` passed.

The separate N9 promotion probe
`test_real_measurement_root_resolves_and_binds_into_n9` failed before the
promotion authority-link reader: fixture construction raised
`CatalogSelectionError: catalog_run_profile_unresolved`. It is retained as a
bounded candidate test limitation and is not included in the passing count.
The public-surface inventory was not regenerated in this delta; root must run
the final ABI/public-surface generator against the whole candidate. This is a
source-ready delta, not a global freeze or formal finding closure.
