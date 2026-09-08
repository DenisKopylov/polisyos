# Layer vintage — append-only handback

## Event 1 — contract, construction and bounded scope, 2026-09-07

Row: `historical-confidence-carries-a-withdrawn-contribution`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/vintage`; attached branch:
`codex/layer-vintage`; requested slice base: `938ddc32a`.
The row's execution owner remains **unallocated**. No owner is appointed by this delivery.

The binding input is the user prompt, including its architect correction. The historical
journal's Events 1–23 were read; its measurements were not rerun. Neither DEBT-REGISTER.md nor
LEDGER.md was used to verify this row, and the debt checker was not invoked. The explicit
handback instruction authorizes this journal alongside the listed source/test/register paths.

### Pattern pass and acceptance

P01/P02/P03: a declaration must have a producer, durable definition, consumer bridge and
machine/audit surface. P04/P05/P07: historical stored numbers, current-rule zero, and contested
non-emission stay distinct; no confidence or evidence class is silently rewritten. P29/P32/P38:
byte identity binds an accepted measurement, never a field-name or filename heuristic. P35/P36:
accepted population facts retain their findings and denominators. P31/P40: confidence used to
size bounds belongs in the same intake boundary as confidence returned in a DTO.

Initial missing links were `producer_missing`, `bridge_missing`, `consumer_missing`, and
`semantic_test_missing` for a consumed declaration. Target: the accepted immutable snapshot
emits a machine-readable layer declaration, named readers actually withhold its confidence,
and removal of the declaration changes that behavior while data and lookalike markers remain.
The contended resource is a writer to a given source/test file; agents had disjoint write sets.
Tests use their own temporary databases; production access is read-only.

### What was built

`knowledge/skg_versioning.py` holds frozen `ConfidenceLayerVintage` and
`ConfidenceLayerOutcome` records plus the accepted snapshot SHA-256
`583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
`confidence_layer_vintage` reads the complete file, compares its digest, checks file stability
during that binding, and emits the record. Unreadable/changing input raises `ambiguous`;
it is never counted as an absent declaration. A different readable digest returns no known
restriction, **not** a currentness or authority verdict. The definition is persisted in source
control; it does not modify the pinned database or mint historical generator provenance.

The record identifies claim-axis absence over **137,714 claim subtrees in 310,829 extraction
documents** (HC-F18). Its layer outcomes are **7,607/7,607 exact** and **15,945/15,945 family**
confidences going to zero under the accepted retained-membership computation, and
**723/723 contested** rows **not emitted**, never zero final confidence (HC-F11–HC-F14).
The declaration's named rule and declaration date qualify “current”; this is not a new replay.
The **342/7,868 published evidence rows** contradicting retained adjudication remain a separate
severity field with HC-F06/HC-F07 provenance. Nothing claims the entire layer contradicts its
adjudications, or infers evidence strength from the parameter namespace.

End to end:

1. Complete snapshot bytes → SHA-bound accepted declaration → `to_payload()`.
2. Existing `read_api.academic.SKGQuery` exposes the declaration and the shared
   `require_forwardable_confidence` guard. No new top-level facade export or database schema.
3. Query confidence SQL goes through `_confidence_connection`, including confidence-derived
   transport floors and contested bounds. The guard raises a `ValueError` carrying a JSON
   `confidence_layer_vintage` payload before numerical consumption. Raw stored values stay
   available in the read-only database for explicit audit; independent parameter-estimate
   lowering remains supported and is a positive integration control.
4. `ScholarKnowledgeStore.project_edge_summary` consumes the same guard before projection.
5. `load_scholar_capabilities` and `_iter_l2_edges` call the read-API guard before direct SQL;
   the credal iterator checks before its first yield, preventing partial reference emission.
6. `BuildLiteraturePrior.pure_step` consumes the declaration before querying or constructing
   `LiteratureEdgePrior`: empty prior, `historical_confidence_blocked`, explicit warning, and
   one snapshot-level payload in both prior and graph metadata.
7. `best_snapshot._assemble_duckdb` refuses registered sources before creating the candidate
   database. `_replace_table_contents` independently resolves an attached source's actual file
   and refuses SKG copying **before DELETE**, so that entry cannot strip the declaration while
   forwarding historical numbers. Byte-identical file copies remain recognized under new names.

The machine/audit surface is the typed lookup, JSON refusal, and Foundry prior/graph metadata.
Dashboard and a persisted new production-data release are `surface_out_of_scope` here.

### Review bucket and closure move

The first review found the **same consumer-coverage class one level deeper**, with siblings:
`contested_edge_value_outer_set` forwarded confidence into trust, and
`untransported_value_outer_set` used the retained transport floor to size bounds even with
zero trust. The reviewer walked all **74 methods / 22 public methods in the one Python file
`skg_query.py` at that review revision**. This was source analysis, not another corpus round.

The batched repair widened the intake to **confidence inputs**, including computed/cached
floors, instead of only list-returning entry points. All confidence SQL readers in that
reviewed set now use `_confidence_connection`; the cached floor checks before returning.
Two existing L2 integration tests that expected this historical forwarding are mandatory
behavior companions and were updated. Their names remain stable. No marker-only gate was added.

### Which residual applies

**HC-R01 applies in part; this is not a query-only declaration.** Its named direct Runtime SQL
consumers, Foundry DTO construction, and `best_snapshot` copier are reached as described above.
`tools/ops_runners/cloud/merge_shards.py` is forbidden to this lane and remains outside coverage.
Byte-identical copies are recognized, but a row-wise/mixed rewrite changes the database digest
and is not registered. This extends to other rewritten derivatives, including direct retraction
rewrites; those are examples of the same bounded residual, not new repair rounds.

The residual falsifier copies retained edge rows into a new database and observes the original
confidence still forwarded with no matching declaration. That is an explicit **negative result
for universal derivative coverage**, not evidence that the rewritten data is current.
The smallest missing capability is a content-bound declaration carried and reconciled per source
layer through every row-wise copier/rewriter. It is not implemented here; the forbidden merge
path cannot preserve such a binding through its fixed table-copy path without follow-up work.

Proposed follow-up row: `academic-confidence-vintage-lost-on-rowwise-rewrite`.
Proposed owner: Data Forge snapshot/merge maintenance, **for architect allocation only**;
no appointment is made. Acceptance: mixed-source row copying preserves a validated per-layer
restriction, and downstream readers still withhold the affected numerical confidence.

### Re-extraction requirement

Deliverable (ii) extends the existing `claim-level-evidence-axis` requirement in
`docs/reference/data-capability-requirements.md`, without duplicating a row or appointing an owner.
Its dated registration keeps **310,710 nonblank abstracts / 310,829 works** (HC-F20) distinct
from **67,262 fulltext-derived raw claims / 137,589 raw claims** (accepted architect basis).
Fulltext is not retained; reacquisition is a quality upgrade, not a prerequisite for the
abstract-only route whose explicit downgrade the prompt establishes. Persisted candidate
axis/status, source basis/provenance, and downstream reassembly/validation are required;
old confidence restoration, cost and successful re-extraction are not claimed. The known
normalizer defect remains a separate prerequisite to repair, not work performed in this lane.

## Event 2 — verification evidence

Initial exact-file regression run selected **9/9 tests** in
`tests/unit/data_forge/domains/academic/knowledge/test_skg_confidence_vintage.py` and exited **1**:
all expected restrictions were absent (`DID NOT RAISE`). The same file passed after initial
wiring. Foundry's new exact test likewise first failed because a real fixture confidence
`0.81` reached the prior. The initial two Runtime tests encountered an incomplete shared-method
integration, then passed after that method landed; that first run was not a semantic red claim.

The review's cached/uncached floor regression selected **2/2 cases**, exited **1**, and observed
`DID NOT RAISE` in both before the shared intake was widened. Further final receipts follow below.

### Final targeted wave and removal probe

All commands below ran from this worktree's `policy-engine`, with the primary checkout's
provisioned Python interpreter and `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src`.
The interpreter resolves product imports to this worktree. Each gate was the sole command in
its shell invocation; its exit status came from the tool, never from a following `echo`.

The final source was frozen after delta review. The reviewer re-executed the original pinned
contested and untransported witnesses and a populated floor cache: all refused with the
declaration after the shared-intake repair. No additional material delta finding remained.

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/knowledge/test_skg_confidence_vintage.py tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py tests/unit/data_forge/domains/academic/knowledge/test_store.py tests/unit/data_forge/domains/academic/batch/test_skg_versioning.py tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py tests/unit/foundry/methods/catalog/causal/test_literature_prior.py tests/unit/runtime/quality/test_capability_index_compiler.py::test_scholar_compiler_consumes_bound_layer_vintage_before_forwarding_confidence tests/unit/runtime/quality/test_credal_reference.py::test_credal_reference_consumes_bound_layer_vintage_before_first_yield tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_grounding_resolves_content_and_fails_closed_for_unrelated_query tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py::test_l2_parameter_estimate_lowers_to_interval_value_outer_set --junitxml=_build/layer-vintage/final-targeted.xml > _build/layer-vintage/final-targeted.log 2>&1
```

**Exit 0; 102/102 selected tests passed, zero errors, failures or skips.** The complete JUnit
testcase denominator is `_build/layer-vintage/final-targeted.xml`; suite wall time 48.552 seconds.
This is a file/node-targeted wave, not a directory-wide or full backend suite.

The independent removal probe replaced only the in-memory declaration producer with `None`:

```python
import pytest
from polisyos.data_forge.domains.academic.knowledge import skg_versioning
skg_versioning.confidence_layer_vintage = lambda db_path: None
raise SystemExit(pytest.main([
    "-q", "-o", "cache_dir=_build/layer-vintage/mutation-cache",
    "tests/unit/data_forge/domains/academic/knowledge/test_skg_confidence_vintage.py",
    "-k", "declared_snapshot_cannot_forward or removing_declaration or snapshot_copy_refuses",
]))
```

It ran as `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src
/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python
_build/layer-vintage/removal_probe.py > _build/layer-vintage/removal.log 2>&1`.
**Exit 1; 9/9 selected tests failed at missing refusal.** DTO definitions, field names, all
guard calls, database bytes and lookalike markers stayed present. The mutation existed only
in that process. The normal final wave above ran unmutated code. This is the requested
remove-the-declaration/keep-the-markers falsifier, not a test of marker presence.

Ruff checked the complete **12 changed Python files** (slice-base diff plus untracked `.py`
delivery files) and exited **0**. Initial lint caught one overlong new declaration line; it
was split before the final wave. No unrelated formatting was performed.

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/devx/architecture/guardrails.py check --skip-generated-checks
```

**Exit 1.** It reports deep-import baseline drift/creep for `acquisition_admission_bundle`
imports from `core.artifacts.manifest`, `core.artifacts.signing`, and
`core.artifacts.write_contract`. This delivery does not edit those files. Its failure
provenance is **`not_established`**: no slice-base replay plus zero complete-input intersection
was established, so it is not called inherited. No architecture baseline was synced or repaired;
those files are outside the allowed list. Generated-artifact gates were explicitly skipped to
keep this bounded check from dispatching unrelated suites. The debt checker was never invoked.

The failure/repair register was reopened at closeout. The source declaration/bridge/consumer/
machine surface/semantic test chain is implemented for the accepted immutable snapshot.
The data-pass artifact remains `artifact_missing`; registration is not execution. Per-layer
binding through row-wise rewriters remains `bridge_missing` / `verification_missing` outside
this delivery. No production data, forbidden active register/ledger, tools, architecture,
dashboard or GitHub file was modified.

**Disposition: `repaired-with-a-limit`.** Both requested deliverables are built. The limit is
HC-R01's forbidden merge path and the explicitly falsified class of rewritten derivatives;
architecture gate provenance is separately unresolved. Stop here for architect transcription
and allocation of any follow-up. The original row's owner remains unallocated. Delivery is
local ordinary git only, without push, rebase, force-push, stash, or a GitHub plugin.

## Event 3 — granted shard-runner residual, closed by refusal

Continuation on `codex/layer-vintage`: `git merge main` fast-forwarded the attached branch
from `89e3e6083` to `f0e2bcbfc`. The architect had merged and verified the earlier delivery.
The new grant covers exactly `tools/ops_runners/cloud/merge_shards.py`; this event supersedes
the forbidden-path limitation above without rewriting that earlier record. No owner is appointed.

Pattern pass: P01/P07 require a consumed, bound declaration; P29/P38 require behavior under
removal, not marker presence; P31 requires guarding the complete input list before emission;
P35/P41 require the complete verification denominator and an honest provenance attribution.
Reuse-first extends the existing `SKGQuery.require_forwardable_confidence` boundary. No new
declaration vocabulary, confidence value, per-row flag, or digest exception was introduced.

The end-to-end path is now:

1. Each normalized input database reaches `merge_duckdb`'s preflight, including later shards.
2. The existing producer hashes its held bytes and resolves the accepted snapshot declaration.
3. The existing read API guard consumes `withhold_confidence_forwarding` and raises the
   machine-readable declaration, preserving the layer outcomes and the sharper adjudication
   subset already recorded above.
4. The merge refuses before destination database creation, replacement, or row insertion.
   The CLI propagates refusal before JSONL/report publication and cleans its staging directory.
   CLI staging/lock activity can precede refusal; the claim is protection of the destination,
   not absence of all temporary filesystem activity.

The input bytes remain the persisted binding artifact. The refusal payload is the audit/error
surface. A new dashboard surface is `surface_out_of_scope`. The runner cannot carry an original
whole-file digest through a row-wise rewrite, so it chooses the explicitly authorized refusal
branch. It does not weaken the binding or silently attach the source digest to changed bytes.
The specific sentence “row-wise merges can lose that binding” is discharged for this runner:
an input bearing the registered declaration cannot enter its destination-producing path.

All **5/5 HC-R01 sites named by the architect** are now reached: capability compiler, credal
reference, best-snapshot copier, literature-prior DTO, and shard merger. HC-R01's query-only
residual no longer applies to this declaration at those sites. Arbitrary external rewrites
made before intake remain outside the immutable-snapshot guarantee; the earlier synthetic SQL
rewrite witness still states that boundary. No claim of universal derivative recognition is made.

### Constructed fixtures and removal receipts

Every new test is a removal probe. The complete new denominator is **6/6 cases**: all three
positions in the constructed input list, crossed with absent/existing destination. Each fixture
keeps lookalike `confidence_layer_vintage`, `evidence_strength`, and conflicting forwarding
metadata present. Each case pins the real producer to the fixture digest, requires the real
merge to refuse, verifies destination preservation and every source digest, then removes only
the producer and observes a destination containing the unchanged base confidence and markers.
That control demonstrates destination production, not correctness of secondary-table merging.
Only constructed fixtures were passed to the runner; no real shard inputs were used.

Before the runner change, the exact new regression file exited **1**, with **6/6 cases** failing
at `DID NOT RAISE`. Independent review of the final mechanism and probes found no blocker.
The final exact-file wave used the same interpreter and worktree import roots as Event 2:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest -q tests/unit/tools/ops_runners/cloud/test_merge_shards.py tests/unit/data_forge/domains/academic/knowledge/test_skg_confidence_vintage.py --junitxml=_build/layer-vintage/merge-final.xml > _build/layer-vintage/merge-final.log 2>&1
```

**Exit 0; 21/21 selected tests passed; zero failures, errors, or skips; 3.155 seconds.** This
includes the architect-verified earlier file plus the complete new six-case denominator.
The only subsequent Python edit removed a blank line demanded by Ruff's import formatting.
Ruff then checked **2/2 continuation Python files** and exited **0**:

```sh
/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check tools/ops_runners/cloud/merge_shards.py tests/unit/tools/ops_runners/cloud/test_merge_shards.py
```

The independent mutation removed the consumer's enforcement in memory, leaving the declaration
producer, DTO definitions, guard call, fixture bytes and lookalike metadata intact:

```python
import pytest
from polisyos.data_forge.read_api.academic import SKGQuery
SKGQuery.require_forwardable_confidence = staticmethod(lambda db_path: None)
raise SystemExit(pytest.main([
    "-q", "-o", "cache_dir=_build/layer-vintage/merge-mutation-cache",
    "tests/unit/tools/ops_runners/cloud/test_merge_shards.py",
    "--junitxml=_build/layer-vintage/merge-removal.xml",
]))
```

This ran as one Python heredoc gate with the same environment and interpreter, redirecting to
`_build/layer-vintage/merge-removal.log`. **Exit 1; 6/6 selected cases failed at `DID NOT RAISE`,
zero errors or skips.** The complete JUnit denominator was read back from both receipt files.
No mutation was written to production code. Every gate was its invocation's sole command;
exit statuses were read from the execution tool, with no trailing `echo`.

### Incidental proposed row — attached catalog mistaken for schema

**Proposed row:** `shard-merge-secondary-catalog-lookups-skip-retained-tables`.
**Proposed owner:** cloud shard-runner maintainers; proposal only, not an appointment.
**Bucket:** new class, unrelated to declaration enforcement. `_table_exists` compares an
attached database alias to `information_schema.tables.table_schema`; the alias belongs to
`table_catalog`. A constructed witness with **2/2 source files**, each containing one
`main.ac_skg_edges` table and one distinct row, exposed both schema rows, returned false for
the secondary lookup, and produced **1/2 source rows** in the destination. Complete witness:
`_build/layer-vintage/merge-catalog-witness.json`. This is a fixture result, not a corpus count.
Proposed repair: resolve catalog and schema distinctly and verify secondary-row contribution
and deduplication behavior. It was not repaired in this residual patch, and the refusal probes
do not depend on secondary rows being merged successfully.

## Event 4 — architecture failure provenance established

**The three `acquisition_admission_bundle` findings are inherited.** This supersedes Event 2's
`not_established` attribution for those findings. It does not claim that the complete architecture
gate is disjoint from our original source changes or that the gate passes.

The exact Event 2 gate was replayed, alone in each invocation, at the true slice base
`938ddc32a5e243267a8fcd578364ff7c8505df9e` and merged continuation base
`f0e2bcbfc7012e8e5dafec3fa4b25772ca26fcd5`:

```sh
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python tools/devx/architecture/guardrails.py check --skip-generated-checks
```

The old tree was materialized with ordinary `git archive` in this worktree's ignored scratch,
at `_build/layer-vintage/provenance/base-938ddc32a/policy-engine`. Referenced workflow existence
inputs were included. Neither another lane's checkout nor any tracked architecture file was
changed. **Both gates exited 1**, with byte-identical output, SHA-256
`83222fcdf3ced06fdbdcf01c6f376ec616139b272b8167cb42617f8aae5e85f4`.
The reports name imports from `core.artifacts.manifest`, `core.artifacts.signing`, and
`core.artifacts.write_contract`, and the resulting baseline drift.

The complete traced input denominator in **each of the 2/2 replays** is **3,210 paths**:
**2,821 existing files + 340 directories + 49 proven-absent probes; 0/3,210 ambiguous**.
Filesystem enumeration is included, including the root Python file enumerated but not parsed.
File-type denominator: 2,665 `.py`, 68 `.json`, 34 `.md`, 19 `.toml`, 11 `.blob`, 7 `.yml`,
5 `.sql`, 4 `.ts`, 3 `.yaml`, 2 `.js`, 2 `.mjs`, and 1 `.jsonl` = **2,821/2,821 files**.
Every **2,821/2,821 archived base file inputs** was checked against its exact Git blob and matched.

The original delivery intersects **7/2,821 file inputs**: `best_snapshot.py`, `skg_query.py`,
`skg_versioning.py`, `store.py`, `literature_prior.py`, `capability_index_compiler.py`, and
`credal_reference.py` at their full paths in the report. Thus **whole-gate zero intersection
is false**. The continuation's runner, test and journal intersect **0/2,821 file inputs**.
We did not substitute the nearer merge base to hide the original overlap.

Finding attribution was established with the real collector, not inferred from a matching
exit code. It enumerates **2,621/2,621 source `.py` candidates**, parses **2,620/2,621**, and
collects **3,285/3,285 deep-import edges**. Its complete new-edge set has **3/3 edges** from
`acquisition_admission_bundle.py`. Restricting the same collector to that source reproduces
**3/3 new edges and all reported findings**, after the unchanged baseline and exception rules.
The complete finding-support denominator is **15 files** (11 `.py`, 3 `.toml`, 1 `.json`),
**15/15 byte-identical between base and current, 0/15 intersecting our changed paths**:

- `src/polisyos/runtime/http/services/acquisition_admission_bundle.py`
- `architecture/public_surface/contract.toml`
- `architecture/baselines/imports/deep_import.json`
- `architecture/exceptions/guardrails.toml`
- `pyproject.toml` (root existence sentinel)
- `tools/devx/architecture/guardrails.py`
- `tools/__init__.py`
- `tools/lib/__init__.py`, `fs.py`, `imports.py`, `output.py`, `preflight.py`, `runner.py`,
  `sql.py`, and `timing.py` (all eight executed helper modules)

The two additional finding-support directory predicates are existence of `src` and `tools`.
All three import statements, at lines 16, 22 and 28, originate in
`b346925ae9465ffc588763e326bf56a0dcc44868`, before the slice base. The source package's recorded
owner in the public-surface contract is `team-polisyos`; this is attribution from the existing
contract, not an appointment by this lane. No repair or baseline sync is needed from this patch.

Complete path lists, file hashes, intersections, replay receipts and isolation results are in
`_build/layer-vintage/provenance/provenance-summary.json` and its `.log` companion. Reproduction
scripts in the same scratch directory are:

- `trace_gate_inputs.py`, SHA-256
  `14aee3f6cda3b8d5ab685bf3c9561c6e2457e6a408b0ac51a41c31fe32766b3d`;
- `derive_finding.py`, SHA-256
  `452a4ef1ec5e3e8d7cb39a78d5af7b3a98b1e530c8417d288199e198202e20aa`;
- `summarize_provenance.py`, SHA-256
  `947292dafabab737af4612904591a824d025e677b4839035c4e5023891ecc03f`.

The failure/repair register was reopened at closeout. No debt register/ledger was consulted,
and no debt checker, generated subprocess gate, or TypeScript scanner was run.

**Continuation disposition: `repaired`.** The granted merge-shards residual is closed by
refusal and the architecture finding attribution is established. This extends the already
registered re-extraction requirement; it does not execute re-extraction, appoint an owner, or
extend the declaration beyond the accepted immutable snapshot. The existing abstract-only /
fulltext partition and the distinct adjudication-contradicting subset remain as recorded.
Delivery is local ordinary git, without push, rebase, force-push, stash, or a GitHub plugin.
