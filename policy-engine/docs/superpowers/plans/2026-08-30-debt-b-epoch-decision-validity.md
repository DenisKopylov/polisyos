# Epoch and Decision-Validity Debt Closure Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close every engineering-complete row in the eight-row epoch/Decision-Validity denominator, preserve honest `blocked` and `ambiguous` outcomes, and leave all institutional signature slots typed, empty, and visible.

**Architecture:** Reuse the existing Decision Validity owner, epoch-validity cascade, certified-derivation owner, temporal projection, Claim Ledger bridge, and canonical generation roots. New authority-grade facts must be persisted, content-bound, independently re-read, and consumed through one owner seam. No task-local fixture may become production authority. No change may cross into `runtime/quality/promotion_sequence.py`; that seam belongs to task A.

**Tech Stack:** Python 3.14, Pydantic v2 strict DTOs, FileSystemCAS, `uv`, pytest, Ruff, Git AST/token complete-denominator scans.

**Slice base:** `784d020148c56e9bfb3a3631909ba11232210a9f`

**Branch:** `codex/debt-b-epoch-decision-validity`

**Required record:** `docs/superpowers/journals/2026-08-30-debt-b-epoch-decision-validity.md`

## Fixed boundaries and predicted terminal matrix

The working prediction is `8 = 4 closed + 0 open + 3 blocked + 1 ambiguous`:

- `closed`: `GY-GAP8`, `gy-n12-epoch-current-decision-lineage-carrier-unallocated`, `ds18-epoch-inheritance-recompute-projection-missing`, `decision-validity-fixed-temp-concurrency`.
- `blocked`: `GY-DEF23`, `ds18-positive-transition-production-unorchestrated`, `ds18-positive-transition-verification-producer-missing`; each requires the unappointed transition signer and/or verifier/producer-identity authority for a positive result.
- `ambiguous`: `gy-n12-lex-amendment-valid-effect-carrier`; the tracked repository cannot supply the production Lex row set or recover the historical `152,636` count.

This is a hypothesis, not a forced answer. If the lineage carrier or recompute bridge requires editing `promotion_sequence.py`, the affected row remains `open` and the journal names the exact seam. No count is adjusted to preserve the prediction.

## Pattern pass before implementation

- `P01/P02`: the core defect is implemented code without a live producer/bridge. Closure requires producer, persisted artifact, orchestration, consumer, and a negative/e2e semantic test; contracts alone remain `contract_only` or `implemented_but_not_orchestrated`.
- `P04/P05/P15`: `current`, `completed`, and positive verification may arise only from owner evidence. LLM output, shaped receipts, signatures, or caller status never become authority.
- `P07/P08`: epoch identity and Decision Validity lineage are semantic coordinates. Observation/read time never substitutes for valid/effect time or owner time.
- `P29/P32/P33`: tests execute the real persistence/read paths and include authentic-old, substituted, missing, denominator-drift, and sibling-root variants.
- `P31`: use one Decision Validity carrier reader and one recompute reader, not per-root patches.
- `P35`: report the complete Git candidate denominator with `.py`/`.pyi` composition and reconcile AST with token scans.
- `P37/P38`: positive predicates are `recomputed` or `independently_reconciled`; test-count scalar `117` is removed because it is a proxy for the production partition property.
- `P40`: any second same-class escape widens the owner seam or becomes a declared bounded residual; it does not trigger another instance patch.
- `P41`: inherited-red claims use the slice base and exact changed-input intersection. The `118 == 117` red is ours; the `rdflib` collection gap is not used as evidence for any row.

## Task 1: Re-derive and repair the GY-GAP8 denominator invariant

**Files:**

- Modify: `tests/repo_quality/test_claim_ledger_export_callers.py`
- Verify: `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py`
- Verify: the existing crash/pending and stale-caller Claim Ledger tests located by exact node name before execution

### Step 1: Preserve the red receipt

Run:

```bash
uv run --frozen --extra test -m pytest -q \
  tests/repo_quality/test_claim_ledger_export_callers.py::test_all_execution_context_constructors_require_same_claim_owner_port
```

Expected before repair: exit `1`, `118 == 117`.

### Step 2: Pin composition, not a growing total

Delete `_EXPECTED_TEST_EXECUTION_CONTEXT_CALLS`. In the focused test derive:

```python
test_base = {row for row in ast_base if row.path.startswith("tests/")}
assert ast_base == test_base
```

Keep AST/token equality, the exact four production `ClaimCapableExecutionContext` constructor paths, the exact two positive test paths, and the prohibition on claim-capable constructors outside `src/` or `tests/`. This closes both divergent cases: a valid new test constructor stays green, while a base constructor in `tools/` or any other executable partition fails.

### Step 3: Verify the mapping and the three named semantic signals

Record:

- current Git denominator `5,710 paths = 5,705 .py + 5 .pyi`;
- `118` AST test constructions = `118` token test constructions;
- the semantic addition from Task-4.5 boundary `552213d…` is `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py::test_eval_safety_context_fields_are_keyword_only`;
- introduction commit `f715bfdc46c59cfa70e959b99248c9543379192e`.

Run the focused denominator node and the three named GY-GAP8 tests. Do not run either containing directory.

### Step 4: Commit

After branch-attachment readback and `git diff --check`:

```bash
git add tests/repo_quality/test_claim_ledger_export_callers.py \
  docs/superpowers/plans/2026-08-30-debt-b-epoch-decision-validity.md \
  docs/superpowers/journals/2026-08-30-debt-b-epoch-decision-validity.md
git commit -m "test(claims): pin execution-context authority partition"
```

## Task 2: Close the remaining fixed-temp persistence site red-first

**Files:**

- Modify: `src/polisyos/scientist/validation/decision_validity.py`
- Modify: `tests/unit/scientist/validation/test_decision_validity_service.py`

### Step 1: Add the named deterministic concurrency test

Add exactly:

```text
test_concurrent_same_packet_persistence_has_no_fixed_temp_collision
```

Use two concurrent writers and a barrier around the same owner-state target so the current fixed `.json.tmp` sibling deterministically produces a lost-temp/`FileNotFoundError` interleaving. Assert both calls finish, no partial JSON is observable, and readback is one complete admitted value.

Run the exact node and observe red before source modification.

### Step 2: Consolidate the atomic writer

Extract one private atomic-byte writer used by both `_save_model` and `save_dedupe_event_id`. It must:

- allocate a UUID sibling in the target directory;
- create with `O_CREAT | O_EXCL | O_WRONLY` and mode `0o600`;
- write, flush, and `fsync` the file;
- atomically replace the destination;
- `fsync` the parent directory;
- clean up only its own unadvertised temporary on failure.

Do not weaken the existing owner transaction or make a fixed sibling reappear under another suffix.

### Step 3: Verify blast radius and commit

Run the named node, existing Decision Validity persistence/corruption nodes affected by the helper, Ruff for the two Python files, and `git diff --check`. Commit as:

```bash
git commit -m "fix(decision-validity): isolate concurrent atomic writes"
```

## Task 3: Allocate the Decision Validity current-lineage carrier

**Files (subject to the entry read deciding the narrowest owner-safe location):**

- Modify: `src/polisyos/core/contracts/decision_validity.py`
- Modify: `src/polisyos/scientist/validation/decision_validity.py`
- Modify: `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- Modify: `src/polisyos/runtime/quality/open_world_risk.py` only if needed to inject the same owner reader into all generation roots
- Modify: focused tests under `tests/unit/scientist/validation/` and `tests/unit/runtime/quality/`

### Step 1: Write carrier falsifiers first

Add focused tests proving:

1. a registered current head plus exact prior completed binding resolves a content-bound carrier by `decision_packet_lineage_key_ref`;
2. head advance returns the new head and rejects replay of the authentic old carrier as current;
3. missing key/index/packet/completion returns a typed nonreceipt;
4. substituted subject, lineage key, head packet, completion receipt, purpose, or query fails closed;
5. dependency/adjudication or packet-epoch denominator drift fails closed;
6. direct, recursive, HTTP-composed, and offline projection verification consume the same carrier identity or the same typed nonreceipt.

Observe red before implementation.

### Step 2: Add one owner-held persisted carrier and pointer

The carrier must bind at least:

- derived `decision_packet_lineage_key_ref` and exact subject ref/hash;
- owner raw lineage key and current head packet ref/hash;
- packet-bound semantic epoch refs;
- prior completed batch ref/hash plus dependency/adjudication denominators;
- requested query context, authority purpose, owner generation/content identity, and verifier provenance;
- `predicate_class="independently_reconciled"`.

Persist immutable carrier bytes in CAS and an atomic Decision Validity-owned key-to-carrier pointer. The reader reloads the pointer, carrier, packet, lineage head, evaluation/dependency state, completed receipt, and all hashes before returning positive evidence.

### Step 3: Wire one reader across roots

Inject the same structural reader into `ArtifactEpochValidityPreN9SubjectAuthority`, `ArtifactEpochValidityAuthorityGate`, and `ArtifactEpochValidityN9EvidenceResolver`. A missing carrier retains first-decision `None`/empty packet fields; a present carrier supplies them only after full readback. Offline `resolve_projection_verified` must re-read the same carrier rather than trust projection fields.

If producing the carrier from an actually emitted post-N9 packet requires changing `promotion_sequence.py`, stop at this point, leave the row `open`, and record the exact producer seam. A test-only registration helper is not closure.

### Step 4: Verify and commit only if the production chain is real

Run exact new carrier nodes plus the existing direct/recursive/HTTP/offline epoch-gate nodes. Commit as:

```bash
git commit -m "feat(decision-validity): resolve content-bound current lineage"
```

## Task 4: Produce and expose epoch inheritance/recompute status

**Files:**

- Modify: `src/polisyos/runtime/quality/derived_observations.py`
- Modify: `src/polisyos/runtime/quality/epoch_staleness_projection.py`
- Modify: `src/polisyos/runtime/http/services/temporal.py`
- Modify: `src/polisyos/runtime/http/dependencies.py` only for the minimal shared composition line
- Modify: focused tests in `tests/unit/runtime/quality/` and `tests/unit/runtime/http/`

### Step 1: Write owner receipt and bridge tests first

Test a real certified derivation graph, then persist an epoch-inheritance/recompute receipt that binds source/target refs, old/current epoch refs, transition ref, requested query context, dependency denominator, status, and certified-derivation consumption evidence. Assert:

- exact completed evidence projects `completed` with `independently_reconciled` provenance;
- missing evidence remains `not_established`;
- source/target/transition/epoch/query substitution fails;
- extra, missing, or reordered dependency rows fail denominator readback;
- the temporal service/HTTP route returns the owner result from the same reader.

### Step 2: Implement the derived-observations owner seam

Reuse `consume_certified_derivation`, `_manifest_projection`, `_load_source`, and exact CAS/profile checks. Add one strict persisted receipt plus repository/resolver. Positive status is admitted only after exact certified-derivation replay and manifest/input reconciliation. `pending`, `running`, or `failed` may be represented only if backed by a real owner artifact; no executor is invented.

### Step 3: Replace projection-wide synthetic absence

Pass the resolver into `_dependency_views`; project each edge from its exact owner receipt or typed nonreceipt. Remove `derived_recompute_status_not_established` and the engineering-absence row only when the reader is composed and the complete dependency set was queried. Preserve empty institutional signer rows.

### Step 4: Wire the temporal read bridge

The runtime API context constructs one read-only resolver over the same CAS and injects it into `TemporalService`; do not change request authority. The existing `/runs/{run_id}/epoch-staleness` route remains the surface. If the only way to expose a positive receipt requires task A's promotion-gate mutation, retain the producer and bridge evidence honestly and mark the row `open` rather than using a fixture.

### Step 5: Verify and commit

Run exact new nodes, the existing epoch-staleness projection tests, and temporal route nodes. Commit as:

```bash
git commit -m "feat(epochs): expose owner-backed recompute status"
```

## Task 5: Wire empty institutional transition slots without appointing them

**Files:**

- Modify: `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- Modify: `src/polisyos/scientist/validation/decision_validity.py`
- Shared/minimal: `src/polisyos/runtime/http/dependencies.py`
- Modify: focused producer/verifier/composition tests

### Step 1: Preserve exact empty-slot tests

Write or retain tests proving the production composition calls the real producer/verifier seams but returns typed `epoch_transition_signer_not_established` / `verifier_not_configured` without state mutation when appointments are absent. Signer provenance cannot substitute for producer identity; a shaped signed blob cannot appoint its verifier.

### Step 2: Compose mechanisms around the slots

Reuse `EpochValidityTransitionProducer`; do not relabel it missing. Install one concrete exact-byte verifier path whose positive arm requires appointed trust/provenance and whose default appointment registry is empty. Replace the direct `NoEpochTransitionSigningAuthority()` construction at the shared dependency line with the single typed epoch-transition composition root, while leaving its signing and predicate-policy slots empty.

Do not manufacture prior/current epoch refs, target dispositions, producer identity, or signatures. Do not edit `promotion_sequence.py`. The absence of an appointment binds the claim, not whether the producer/verifier mechanisms are constructed and callable.

### Step 3: Apply stop rules and record verdicts

- `GY-DEF23`: `blocked` until the signed transition can be derived before strict intake.
- `ds18-positive-transition-production-unorchestrated`: `blocked` if the real production trigger ends at the task-A promotion seam or cannot persist a positive artifact without signer/producer identity.
- `ds18-positive-transition-verification-producer-missing`: `blocked` if the exact verifier is wired but positive trust remains unappointed.

No fixture may turn these verdicts to `closed`.

## Task 6: Re-evaluate the Lex row without reconstructing data

Run a complete tracked-repository search for the `156,196` denominator, the historical `152,636`, an admitted production Lex database, and a complete owner-adjudication receipt. Record exact path/file denominators and commands. Do not edit Lex data or infer a count.

Expected verdict: `ambiguous`, because the repository cannot answer whether every amendment row now carries a valid/effect coordinate.

## Task 7: Targeted closeout, independent review, and dossier

### Step 1: Freeze changed source and run targeted verification only

Run only exact nodes named by the eight rows plus tests importing changed modules. Run Ruff on changed Python paths, architecture guardrails if imports changed, and `git diff --check`.

Required clean controls:

```bash
PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py --check
PYTHONPATH=. uv run --frozen --extra test python tools/quality/validation/check_docs_lifecycle.py
```

The first must exit `0`; the second must report exactly `6 findings`. The debt register, ledger, master plan, layer-3 slice, and `PUBLISHED_DENOMINATORS` remain byte-identical to the slice base.

### Step 2: Perform independent delta review

Review authority boundaries, content binding, denominator completeness, and concurrency behavior. Bucket every finding per `P40`; fix blocking findings in one batch, then rerun only the affected targeted nodes.

### Step 3: Finish the journal

End the journal with eight Register closure dossier blocks. Each block includes:

- verdict (`closed`, `open`, `blocked`, or `ambiguous`);
- exact deciding command or predicate and exit code;
- exact supersession prose for the architect to append beneath the row.

Also include:

- arithmetic `8 = closed + open + blocked + ambiguous` with measured row counts;
- the complete 118 mapping and composition invariant;
- exactly what task D still lacks for `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`;
- every institutional slot wired and left empty;
- every out-of-scope seam, especially task A's promotion gate.

### Step 4: Final readback and commit

Verify attached branch, read every changed path from `HEAD`, verify forbidden paths unchanged, then commit the journal/dossier as:

```bash
git commit -m "docs(debt): record epoch validity closure dossier"
```

## Round 2 — terminate every row as closed or concretely blocked

Round 1 is the implementation base and remains append-only.  This round does not
reopen `GY-GAP8`, whose three named tests, exact denominator composition, and Task-4.5
ancestry were accepted by the architect.  It executes the two missing fixed-temp
conjuncts, builds the locally executable transition/recompute mechanisms, and converts
every unresolved row to a concrete `blocked_by` that names an artifact, producer,
appointment, slice seam, or registered repair which must land.

### Round-2 pattern pass and interface rulings

- `P01`/`P02`/`P12`: an adapter, verifier port, or receipt alone is not positive
  orchestration.  Each built half binds exact persisted inputs and its named downstream
  consumer; the register carries the other half explicitly.
- `P05`/`P32`/`P37`: signer provenance cannot substitute for producer identity, a
  verifier cannot trust its own provenance artifact, and caller-provided lists cannot
  establish either owner denominator.
- `P07`/`P08`: recompute receipts bind the exact transition, old/head epochs, query
  coordinate, purpose, dependency edge, certificate, and derived output.  An authentic
  receipt for an old transition cannot answer a later head.
- `P31`/`P38`: do not call the empty-byte signer probe orchestration and do not forward
  the producer graph hash as Decision Validity's differently shaped packet denominator.
- `P35`/`P41`: every zero and every inherited red reports its complete path denominator;
  the Task-4.4 HTTP failures must reproduce at the slice base before they can become a
  named external landing dependency.

## Task 8: Execute and adjudicate the two missing fixed-temp conjuncts

**Files:**

- Append only: `docs/superpowers/journals/2026-08-30-debt-b-epoch-decision-validity.md`
- No product or snapshot write is authorized by this task.

### Step 1: Execute the full Task-4.4 Python suite

Run exactly the nine files listed under predecessor Task 4.4 with the bound `uv`
interpreter.  If any node is red, rerun the exact failing selectors at both
`784d020148c56e9bfb3a3631909ba11232210a9f` and the round-2 source pin, enumerate the
changed-path intersection, and identify the introducing commit for each divergent
expectation.  A runnable-but-red suite is not a passed conjunct.

### Step 2: Execute the exact zero-retry visual no-writer command

Provision the Playwright toolchain with `corepack pnpm install --frozen-lockfile`, then
run the DS9 command exactly as published, without `--update-snapshots`.  A readiness
timeout is a tooling nonreceipt: diagnose which configured server did not bind, remove
only Task-B-owned diagnostic processes, wait for contended sibling workers, and rerun the
unchanged command once under a measured healthy load.

### Step 3: Terminate the row

`decision-validity-fixed-temp-concurrency` is `closed` only if the named concurrency
node, all nine Task-4.4 files, and the exact visual command each exit zero.  Otherwise it
is `blocked` by the exact test-repair or environment artifact that must land; the dossier
must name every failing selector and the owning corridor, not merely say "inherited".

## Task 9: Build the exact semantic-history transition adapter

**Files:**

- Modify: `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- Modify: `tests/unit/runtime/quality/test_epoch_validity_cascade.py`

### Step 1: Write the adapter falsifiers first

Create an exact semantic-epoch production receipt and history in a real CAS.  The first
test must fail because no concrete `EpochTransitionHistoryRepository` adapter exists.
Cover receipt substitution, wrong current manifest, wrong purpose/scope, missing or
ambiguous previous epoch, non-head current epoch, and corrupt receipt/manifest bytes.

### Step 2: Reuse the existing history owner

Implement only the adapter from `current_epoch_receipt_ref` to
`FileSemanticEpochHistoryRepository`.  Exact-reload the one framed production receipt,
follow and validate its semantic manifest, resolve the matching complete scope history,
and return previous/current manifests only when the requested current epoch is the sole
verified head and the previous epoch is its declared predecessor in the same purpose and
scope.  Do not create a second history repository.

### Step 3: Verify and commit

Run the exact new adapter nodes plus the existing producer nonreceipt node, Ruff the two
changed Python paths, and commit the coherent adapter/test group.  Positive production
remains `blocked` by the task-A trigger, complete dependency inventory producer, complete
owner-adjudication producer, and signer/owner-held producer-identity appointment.

## Task 10: Build the derived-observations recompute producer half

**Files:**

- Modify: `src/polisyos/runtime/quality/derived_observations.py`
- Modify: `tests/unit/runtime/quality/test_derived_observations.py`

### Step 1: Write red owner-receipt tests

Materialize a real certified derivation, persist an exact positive epoch transition, and
request one exact dependency edge.  Require one completed-only owner receipt whose
manifest inputs and content hash bind transition ref/hash, previous/current epoch,
query/purpose, producer denominator, source/target/relation, certificate binding, and
the independently recomputed derived output.  Add substitution, authentic-old, corrupt
bytes/manifest, wrong disposition, missing edge, and certificate/output drift
falsifiers.

### Step 2: Implement one completed-only producer and exact reader

Reuse `consume_certified_derivation`, `_put_or_verify`, fixed schemas/producers, and CAS
verification.  The producer may emit `completed` only after exact transition readback,
edge/target-disposition membership, certificate-binding reconciliation, and full
certified-derivation replay.  Do not invent pending/running/failed executor states.  The
persisted handle carries only ref/hash; the reader revalidates bytes, profile, inputs,
and referenced owner evidence.

### Step 3: Verify and commit

Run only the new owner-producer nodes and directly imported existing derivation nodes,
then Ruff and `git diff --check`.  Do not edit the staleness projector, temporal service,
or shared dependency composition: those are the named external read bridge for the
blocked row.

## Task 11: Re-census blockers and produce the round-2 dossier

**Files:**

- Append only: `docs/superpowers/journals/2026-08-30-debt-b-epoch-decision-validity.md`
- Append only: this plan and the SDD progress ledger as execution receipts require.

### Step 1: Re-run complete source censuses

Use `git ls-files` to state repository/source/test/Python denominators.  Re-run the
transition constructor/caller, provider, verifier-injection, positive-verifier,
Decision-Validity service, and four-field Scientist carrier searches.  For every
`producer_missing` block, report the exact signature intersection and zero over the full
2,611-source-Python denominator (or the recomputed current denominator).

### Step 2: Re-state the two denominator definitions

Record that the transition producer hashes certificate bindings, dependency graph, and
graph target refs, while Decision Validity hashes registered dependency keys with owner
artifact, packet, and lineage membership.  Name the required persisted cross-owner
mapping/reconciliation receipt and its trust appointment.  Do not forward one hash as
the other.

### Step 3: Run targeted controls and independent review

Run only exact changed-module nodes and named row signals.  The debt checker is expected
to exit `1`; compare its blocker identities to the round-2 preflight set and require no
new blocker outside rows B owns.  The docs-lifecycle checker is expected to exit `1`
with exactly six inherited findings.  Run Ruff, architecture guardrails if imports
changed, and `git diff --check`.  Dispatch a whole-branch review after source freeze and
fix only blocking findings in a bounded delta round.

### Step 4: Append the eight-block dossier last

The final journal section contains exactly eight blocks, each with verdict `closed` or
`blocked`, `blocked_by` when applicable, exact deciding command/predicate and exit code,
and append-only register prose.  Include `8 = closed + blocked`, the two fixed-temp
conjunct receipts, every transition mechanism built or full-census blocker, the Lex
production-row-set block, the task-A four-field lineage seam, empty institutional slots,
task D's remaining `GY-GAP8` overlap, and every out-of-scope finding.
