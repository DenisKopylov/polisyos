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
