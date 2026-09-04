# Extraction-strength vocabulary split journal

## Task 1 — typed envelope and legacy absence adapter

### Capability state

This delivery is deliberately `contract_only`: it adds a strict, frozen v2
vocabulary envelope, an explicit one-way legacy-absence adapter, and semantic
contract tests. No v2 producer, persisted v2 artifact, orchestration bridge,
consumer migration, verification receipt, or external surface is present.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: collection failed with two expected `ImportError` failures because
`ClaimVocabularyAxisStatus` did not yet exist in
`polisyos.ir.analytics.literature`. This is the intended missing-contract
failure for C03--C06, rather than an environment or syntax failure.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: `17 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/ir/analytics/literature.py tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py
```

Result: `All checks passed!`.

### C03--C06 coverage

- C03: a strict v2 payload rejects generic `strength`; the named adapter retains
  the raw legacy label and the envelope survives JSON round-trip validation.
- C04: legacy `moderate` retains only `legacy_strength_label`; all four typed
  axes are null and all four statuses are `not_established`.
- C05: the adapter accepts no parent-study-design or record-confidence argument,
  so neither can fill a claim-level axis.
- C06: design and evidence axes may be supplied independently only as explicit
  typed candidates; neither derives the other, and a shared `rct` spelling is
  still rejected under generic `strength`.

The unactivated-scope test also confirms that `WorkRecord.causal_claims` stays
`list[dict]` and `CausalClaim.from_payload()` remains on its existing v1 path.

### Exclusions held

No changes were made to lineage, adjudication authority types, Runtime,
producers, stores, graph code, `docs/plans/active/`, or `production_data`.
No production-data read, hash, migration, producer run, or bound debt-checker
run occurred.

## Task 1 review-fix — strict legacy input and sidecar semantics

### Decision

The v2 envelope is explicitly a vocabulary sidecar, not a general occurrence
transport. Task 2 must embed it beside the original occurrence in a lossless
composite transport. The absence adapter now validates a frozen, strict exact
legacy contract with only `cause`, `effect`, `direction`, `strength`, and
`mechanism`; missing, unexpected, and rich fields fail rather than being
manufactured or silently dropped.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: collection failed with the expected `ImportError` for the absent
`LegacyFiveFieldClaimOccurrence` input contract. This was the intended
missing-contract failure, not environment or syntax noise.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: `18 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/ir/analytics/literature.py tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py
```

Result: `All checks passed!`; `git diff --check` also passed.

### Review-fix coverage

- The adapter rejects missing legacy fields, arbitrary extra fields, and rich
  claim fields, and validates no manufactured empty required input.
- A deliberately disagreeing design/evidence pair and all four candidate axes
  survive JSON round trip; changing any one axis leaves the other three stable.
- `WorkRecord.causal_claims` rejects a v2 envelope, while exact legacy JSON and
  `WorkRecord` JSON remain v1-shaped with no implicit adapter.

## Task 2 — inactive composite, serializers, and store preparation

### Capability state

This is `implemented_but_not_orchestrated` preparation. The frozen
`ClaimOccurrenceVocabularyTransport` retains the complete non-vocabulary
occurrence beside Task 1's strict `VersionedClaimVocabularyEnvelope`; no v2
artifact is emitted by a producer or persisted by a live writer.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py tests/unit/data_forge/domains/academic/batch/test_parser.py tests/unit/data_forge/mirror_contracts/test_llm_extractor.py tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py -q
```

Result: collection reported the expected missing transport and serializer
imports. Follow-up boundary tests failed for the intended reasons: the future
deterministic serializer silently accepted generic `strength`; the rich
serializer promoted omitted Pydantic defaults; the snapshot helper accepted
only an artificial legacy mapping; and the exact persistence constants/projector
did not exist. These were product-contract REDs, not environment failures.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py tests/unit/data_forge/domains/academic/batch/test_parser.py::test_future_deterministic_claim_serializer_keeps_abstract_basis_without_legacy_label tests/unit/data_forge/domains/academic/batch/test_parser.py::test_future_deterministic_claim_serializer_rejects_a_generic_strength_label tests/unit/data_forge/mirror_contracts/test_llm_extractor.py::test_future_llm_claim_serializer_keeps_named_candidate_axes_separate tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_rich_claim_serializer_preserves_metadata_and_does_not_borrow_record_confidence tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_rich_claim_serializer_keeps_omitted_pydantic_defaults_absent tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_graph_writer_inactive_preflight_uses_the_shared_vocabulary_admission_callable tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_span_writer_inactive_preflight_reuses_the_graph_vocabulary_boundary tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_splits_only_exact_legacy_claim_occurrences tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_revalidates_an_actual_future_composite tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_rejects_rich_generic_strength_before_copy tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_rejects_a_duplicated_typed_vocabulary_key tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py::test_existing_v1_work_record_and_causal_claim_paths_are_not_activated -q
```

Result: `27 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check [Task-2 source and test paths]
git diff --check
```

Result: both passed. `uv run polisyos-tools architecture guardrails check` was
started but did not complete after several minutes and was terminated; it is
not pass/fail evidence.

### Task 3 activation handshake

- Shared frozen transport and mechanical re-admission owner:
  `ClaimOccurrenceVocabularyTransport` and
  `admit_candidate_claim_vocabulary` in `knowledge/types.py`.
- Future-only serializers: `serialize_deterministic_claim_occurrence_vocabulary`,
  `serialize_llm_claim_occurrence_vocabulary`, and
  `serialize_rich_claim_occurrence_vocabulary`.
- Both writer seams are the exact same callable:
  `graph_builder.preflight_candidate_claim_vocabulary` and
  `skg_store.preflight_candidate_claim_vocabulary` alias
  `admit_candidate_claim_vocabulary`. Snapshot copy preflight is
  `preflight_claim_occurrence_vocabulary_copy`; it re-admits a future composite
  and only adapts an exact legacy five-field occurrence.
- Exact inactive persistence layout: discriminator
  `claim_vocabulary_schema_version="2.0"`; ordered sidecar columns are
  `design_family_hint`, `design_family_hint_status`, `evidence_strength`,
  `evidence_strength_status`, `claim_extraction_confidence`,
  `claim_extraction_confidence_status`, `source_basis`, `source_basis_status`,
  `legacy_strength_label`, and `record_extraction_mode`. The pure
  `candidate_claim_vocabulary_store_values` re-admits before returning only
  those values and never returns generic `strength`.
- No-activation proof: `WorkRecord.causal_claims`, legacy parser/LLM append and
  JSONL, `_to_work_record` v1 output, graph DDL/batches/inserts,
  `_infer_edge_strength`, direct span ingest loop, and snapshot assembly/copy
  calls were not changed; the preflight tests call only inactive helpers.

### Pattern pass and exclusions

P01/P02 remain intentionally open until the atomic bridge and consumers land.
P04/P10/P15 are addressed locally by typed absence, independent candidate
axes, and no generic-label laundering. P27 is avoided by consuming Task 1's
sidecar rather than introducing another vocabulary DTO; P29/P33/P38 are covered
with runtime boundary falsifiers rather than source-marker tests.

No authority, receipt, publication, ranking, evaluator, Runtime, Foundry
catalogue, `docs/plans/active/`, or `production_data` path changed. The bound
debt checker was not run.

## Task 2 review fixes — strict admission state and nested metadata

### Pattern pass

This fixes the reviewed P29/P33/P38 gap at the canonical common boundary. The
previous admission path re-used a nested Pydantic instance and a selected-key
outer reconstruction, so `model_copy(update=...)` forged state was not
revalidated; its recursive duplicate-key check also treated an opaque nested
`source_basis` as a second occurrence vocabulary owner. The target pattern is
one complete-state reconstruction for both transport and sidecar, typed
duplicate reservation at the occurrence root, and recursive reservation only
for generic `strength`. P01/P02 remain intentionally
`implemented_but_not_orchestrated` until the Task-3 atomic bridge.

### RED evidence

From `policy-engine/` at Task-2 head `2aa63f5fb` after adding behavioral
review-fix tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py::test_admission_revalidates_complete_nested_sidecar_instance_state tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py::test_admission_revalidates_complete_outer_transport_instance_state tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_all_inactive_writer_aliases_reject_forged_nested_sidecar_state -q
```

Result: `5 failed, 2 passed`; failures were the intended missing strict
nested/outer revalidation and recursive nested `source_basis` rejection.

### GREEN evidence

The focused Task-2 set collected 94 tests and passed after the minimal owner
fix. The transport boundary, all writer/snapshot aliases, producer serializers,
and existing inactive-path sentinels were exercised. Ruff passed on changed
source/tests and `git diff --check` passed. No producer, writer, snapshot
assembly, architecture guardrail, bound debt checker, or `production_data`
path was run.

## Task 3 — consumer/replay strangle

### RED evidence

At the clean Task-2 head `7a985c070`, after adding the store/public-surface
behavior tests, the focused command was:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/knowledge/test_store.py -q
```

Result: collection failed with the expected missing `CausalClaimResultV1`
import from `knowledge.types`; the new v1/v2 projection, typed schema errors,
and audit surface were not yet implemented. This is the intended product RED,
not an environment or syntax failure.

### GREEN evidence

The focused store and graph-writer checks passed after implementation. Ruff
passed over changed production/test paths. The bounded Runtime edge byte guard
reported `runtime_edge_byte_guard=pass protected_segments=4` against Task-3
parent `7a985c070a9edc3f757b3d21c51ee6373c1f18b5`.

### Task 3 recovery — 2026-09-04

The continuation preserved the entire uncommitted Task-3 cluster. Tasks 1 and 2
remain committed and accepted; Task 3 is not claimed accepted by this entry.
The active reader/writer switch is one atomic cluster, including the separately
authorized Runtime causal-claim path. No protected Runtime edge path, publication
gate, evaluator/receipt chain, Foundry catalogue, or production-data path changed.

The snapshot-copy negative test exposed a second entry into the same admission
class: a valid explicit-v2 column layout did not establish valid row vocabulary.
Before the fix, the real copier accepted both `moderate/candidate` and
`rct/not_established` as evidence value/status pairs and replaced a sentinel
destination. This is a vocabulary-admission gap, not a request for authority work.

RED command (shared Python, this worktree's `src` on `PYTHONPATH`):

```text
python -m pytest -o addopts='' -q tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_clone_rejects_invalid_v2_axes_before_replacing_destination
```

Result before the fix: **2 failed in 4.68s**, both `DID NOT RAISE`. The target
property is validation of every source row by the existing envelope before any
destination replacement, not another label mapping or a schema-presence proxy.

### Gate residual attribution, not a blanket inherited-green claim

The exact public-surface snapshot and compatibility selectors were replayed from
the slice base `c7becd3a71bb67307229c7c8f23acb60d58f4289` in an isolated
`git archive` copy under this plan's scratch. Both red conditions reproduced.
The snapshot collector's full base data denominator is 2,618 selected source
Python files plus one baseline JSON; B-1 intersects 17 of those source paths.
The current release check reads 85 content inputs (39 fragments); B-1 contributes
one new fragment. Therefore neither **whole gate** is classified as inherited
under P41. The particular compatibility error names the pre-existing
`2026-08-27-lex-intervention-ownership.toml` change
`lex-intervention-execution-ownership`, not the new vocabulary fragment.

The Runtime module run passed its vocabulary and protected-payload tests but
failed `test_backend_availability_pins_cp_sat_and_defers_dense`. That exact
selector also fails at the slice base: the shared environment lacks the optional
`ortools` module (`ModuleNotFoundError`), so the real availability probe reports
`unavailable`. This is a reproduced environment residual, not a passing full
Runtime suite and not formal whole-test inherited attribution (B-1 touches the
source/test module). No predicate, test inspection set, or baseline was weakened
to turn any of these checks green.

The full architecture check also found five new B-1 deep imports. Their repair
uses the existing supported lazy IR/Data Forge facades; no new exception or
deep-import baseline is authorized. Other reported generated-artifact/toolchain
and acquisition-module findings remain measured closeout residuals until the
final frozen check. The bound debt checker has not been run by this lane.

### Task 3 GREEN — atomic admission, dual-schema projection, and Runtime reroute

The atomic switch now routes all three live extraction variants into
`ClaimOccurrenceVocabularyTransport`; `WorkRecord.causal_claims` accepts only
that strict transport. Deterministic, LLM, and rich extraction serializers name
the four axes independently and emit no generic `strength`. Persisted v1 JSONL
is accepted only by `adapt_jsonl_work_record_claims`, which invokes the
provenance-bound legacy adapter and removes the historical label before common
admission. It does not assign the label to any typed axis.

Both write routes share the exact common admission callable. The graph builder
re-admits every record claim before row construction, writes the `2.0`
discriminator plus the four value/status pairs, and never persists generic
`strength`. The span-grounded writer re-admits every input claim before its first
schema/database write. This prevents a new vocabulary bypass without repairing
or making any claim about the separately owned publication gate. The snapshot
copier discriminates exact legacy/v2 layouts; legacy bytes remain legacy, while
an explicit-v2 table has every row revalidated through the existing envelope
before the destination is dropped or replaced. After that fix, the two-case
snapshot RED above passed and its sentinel destination remained intact on each
rejection.

`ScholarKnowledgeStore` is the one persisted-row projection owner. It accepts an
exact legacy schema or exact `2.0` schema, rejects partial/mixed/future layouts
and invalid value/status pairs as `ClaimTableSchemaError`, and constructs a
descriptive source-row binding from the physical row. Legacy labels (including
`moderate`, enum-looking strings, malformed strings, and future-looking strings)
remain `legacy_strength_label`; every typed value is null and every axis status
is exactly `not_established`. The default result is frozen/strict v2 and has no
`strength`; the explicitly named v1 audit view always returns `strength=None`
with `ambiguous_legacy_vocabulary`. Exact, family, contested, and hybrid readers
use this owner; hybrid bindings enumerate all contributing physical rows.

The projection is forwarded unchanged by SKGQuery/Search, the lazy academic
read facade, Scholar/KnowledgeToolkit, and its registry adapter. Raw lineage uses
bounded `1..500`, `limit+1`, keyset `(id, work_id)` pages. First-page totals and
identity uniqueness are reconciled; cursor filter/rule/schema mismatches fail
typed. The cursor deliberately makes no between-call currentness promise.

Runtime before/after emission on the authorized causal-claim path:

```text
before: SELECT ... strength, design_family_hint, claim_extraction_confidence ...
        value["strength"] = <bare stored label>
after:  academic.iter_causal_claim_results_v2(connection)
        value = four independently named value/status pairs
        provenance.signals.claim_vocabulary = the same pairs + legacy label,
          limitations, and projection binding
```

The claim's pre-existing trust/tier/blocker/membership/status calculation is
unchanged. The exact-edge and family-edge functions and their SQL loops remain
byte-identical to Task-3 parent `7a985c070a9edc3f757b3d21c51ee6373c1f18b5`:
`runtime_edge_byte_guard=pass protected_segments=4`. Two complete, hand-fixed
canonical payload oracles also passed, with exact-edge content hash
`sha256:5b340aa61431fab375278ccf3e0d833b99c2515ae9ec5e565b04080e8c3ee84b`
and family-edge content hash
`sha256:0149a83f050a1f565189c4af228bd731739de1c57fdabeade484f4b6d14213fa`.

Focused Task-3 verification (explicit repo addopts disabled so counts are
visible) ran 14 selectors/modules spanning producers, both writers, snapshot
copy, Store/SKG/public/Scientist consumers, lazy public facades, and the three
bounded Runtime vocabulary/payload tests: **138 passed in 266.24s**. The one
intentional forged-Pydantic warning was then captured as an expected warning;
that selector replayed **1 passed in 1.33s**. Ruff passed all changed Python
paths (including the newly tracked Store test), and `git diff --check` passed.

The architecture check with generated checks explicitly skipped reports only
three deep-import drift rows in the untouched
`runtime.http.services.acquisition_admission_bundle` module. Its output contains
none of the five B-1 import edges from the earlier RED; B-1 now consumes the
existing supported lazy IR and Data Forge facades. This is not a green whole
architecture gate. Likewise, the full read-facade governance module produced
five findings that replay identically at the true slice base: one Ukraine eager
facade and the same pre-existing Runtime direct/dynamic imports. Its B-1-specific
lazy academic export selector passed inside the 138-test wave. No source or
test predicate was narrowed to hide those findings.

Pattern pass: P01/P02 move from `implemented_but_not_orchestrated` to complete
for the narrowly scoped vocabulary chain; P03 has explicit public/audit routes;
P04/P10/P15 use declared absence and independent candidate axes; P27 reuses IR
and Store owners; P28 strangles the ambiguous default with an explicitly named,
strength-free v1 audit route; P29/P33 test runtime behavior and invalid variants;
P31 closes both live write routes plus the single Store projection; P35 retains
the complete-set requirement for Task 4; P37 labels descriptive provenance as
non-authoritative; P38 records the keyset cursor's bounded currentness
limitation. Authority, graph fallback, publication, evaluator, ranking,
currentness/reissue/cache, and the promoted debt rows remain unclaimed.

### Task 3 review fix — operational identity and relation-wide uniqueness

Independent review found that non-exact SKG claim projections dropped the
pre-split operational `work_id`. RED tests for family, contested, and hybrid
support modes each observed an empty value despite nonempty `article_refs`.
`SKGQuery.query_claims` now passes the first supporting reference through the
Store projector, restoring the prior behavior without changing vocabulary or
source-binding semantics.

The review also exposed a real P38 risk in the audit fallback: when a legacy
table lacks a declared identity constraint, uniqueness had been reconciled only
inside the requested status filter. A read-only check of the pinned raw relation
settled the required compatibility: it declares **no constraints**, but has
`137,589` rows, `137,589` distinct `(id, work_id)` pairs, and zero null
identities. Requiring a constraint would therefore make the pinned snapshot
unreadable and contradict the no-data close. The repair instead reconciles the
complete physical relation before applying any status filter, then computes the
filtered total. A RED fixture with duplicate unconstrained legacy identities and
the otherwise-empty `candidate` filter previously returned an empty page; it now
fails with `ClaimLineageCursorError`. Explicit-v2's existing canonical identity
constraint remains mandatory—an attempted intermediate removal was rejected as
a forbidden predicate weakening and was not committed.

Independent root replay after the correction: the complete Store/SKG focused
pair reported **58 passed in 8.39s**; Ruff over both modules and both tests
passed, and `git diff --check` passed. The declared between-call mutation
limitation remains unchanged.

### Task 4 — no-data vocabulary closure receipt

Task 4 adds the one required integration proof at
`tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py`.
It has exactly four behavioral tests and changes no production source, schema,
release fragment, register, or `production_data` bytes. All writable fixtures
use temporary DuckDB paths. The pinned snapshot is opened only read-only and
its required SHA-256 is asserted before and after the complete bounded public
audit traversal.

The proof exercises both activated temporary writers, snapshot copy, Store,
SKGQuery/Search, the lazy academic facade, Scholar/Toolkit/registry, the
Runtime causal-claim path, a temporary physical legacy snapshot/JSONL replay,
and public legacy mechanism forwarding. Four independent axes preserve their
own value/status pairs; a legacy literal remains audit-only, with v2 null plus
`not_established` and explicit v1 `strength=None` plus
`ambiguous_legacy_vocabulary` (a generic registry serializer may omit a null
field).

The complete tracked AST census now discovers bare generic `strength` before
narrowing and constructs disposition from the operation and enclosing symbol.
It rejects every semantic unprojected reader, including `SELECT *` followed by
a key read and indirect Runtime variants; it does not rely on a file allowlist.
The complete `{path,line,symbol,operation,disposition}` inventory is retained
as a pytest property and emitted with the census receipt. The named permitted
cases remain the provenance-bound adapter, Store physical legacy projection,
frozen admitted edge producer, explicit edge evidence, and explicit
administrative/out-of-scope paths.

Against an isolated `7a985c070` archive/source overlay, each individual test
failed behaviorally: missing active graph admission (41.53s), missing public
lineage surface (3.06s), missing JSONL legacy adapter (4.43s), and nine direct
unprojected generic-strength hits including the Runtime query/emission (51.78s).
On the current branch the four-test integration file passed **4 passed in
97.98s**; Ruff and `git diff --check` passed. The broader prerequisite wave has
one known non-Task-4 CP-SAT/OR-Tools availability red, reproduced at the same
slice base; it is recorded in the Task-4 implementer report rather than
suppressed or described as a whole-gate green. The bound debt checker was not
run.
