# Task R — three unowned producers journal

Date: 2026-09-01
Branch: `codex/debt-r-unowned-producers`
Base: `f6c465648`
Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine`

## Outcome and delivery shape

Two groups close and one group stops on the task's explicit schema/contract rule:

1. `40577c39f` — `feat: bridge epoch recompute receipts into temporal projections`
2. `e0ba8d61b` — `feat: produce connector source-profile discovery snapshots`
3. Group 3 has no source/test commit. The registered closure node is red, and the only honest
   implementation requires a new or discriminated frozen C4 persisted profile and an independently
   appointed owner-event verifier. The task says to stop rather than change that schema or substitute
   an advisory artifact.
4. This append-only journal is its own commit.

The environment binding was confirmed once, before the measurements:

```sh
/usr/bin/env /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -c "import sys; print(sys.prefix)"
```

Exact output, exit 0:

```text
/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv
```

No checkout, switch, stash, history rewrite, other worktree read, or other-lane contact was used.
No file under `docs/plans/active/` was edited. Branch attachment was read immediately before both
commits and returned `refs/heads/codex/debt-r-unowned-producers`; both commits were then read back
from that branch.

## Pattern and capability pass

- `P01` / `P02`: Group 1 wires the already-complete producer and exact reader into both named
  consumers. It does not create a parallel producer. Group 2 supplies contract, producer, paired
  persisted artifacts, orchestration/default-provider bridge, consumer, receipt verification and a
  semantic negative. Group 3 is not called implemented while artifact, verifier and replay family
  are absent.
- `P05` / `P08`: Group 1 projects only recompute status at the exact requested temporal coordinate.
  It does not establish epoch-head currentness, Decision Validity status, lifecycle authority, or
  reissue permission.
- `P15` / `P32` / `P37`: Group 2 remains candidate discovery. Connector/profile DTO availability
  and registry membership cannot establish execution or publication authority. Group 3 does not
  turn monitor metadata or a caller-authored lifecycle projection into Claim-owner authority.
- `P29` / `P33`: each closure has a positive control, a mechanism-specific red, adversarial
  corruption/substitution controls, and a real-path exact node. Group 2 additionally injects a
  secret-bearing connector field and proves it cannot enter the persisted allow-list snapshot.
- `P35`: every absence below comes from one complete AST/text walk over the pinned base's 2,617
  tracked `src/**/*.py` files plus 2,490 tracked `tests/**/*.py` files. The inherited statement that
  `SourceProfileOwnerReceipt` had zero constructor calls everywhere was corrected: production had
  zero; tests had one fixture constructor.
- `P38`: list DTOs are deliberately exercised first and proven to persist no discovery evidence.
  Group 3's existing proxy is also stated exactly: a standalone lifecycle-result append agrees with
  owner supersession only in easy cases and diverges when a head must replay independently verified
  owner authority.
- `P41`: the final architecture guardrail's three deep-import findings name an unchanged file, but
  no exact slice-base replay was performed, so their provenance is `not_established`, not claimed
  inherited. The trust-posture generated artifact consumes all `src/**/*.py`; Task R intersects that
  denominator and therefore honestly caused its current drift.

Capability states after this task:

- `ds18-epoch-inheritance-recompute-projection-missing`: `bridge_missing` -> closed.
- `ds10-connector-acquisition-content`: `absent/unallocated` producer -> closed, candidate-only.
- `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`: remains `blocked` on the named owner-event row.
- `claim-ledger-supersession-owner-event-producer-missing`: remains `open` with
  `artifact_missing + verification_missing + replay-schema-extension-required`; its independent
  authority appointment is also not established.

## Complete base census

The deciding census command was a single in-memory archive/AST walk of the complete pinned set:

```sh
/usr/bin/env /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python - <<'PY'
from __future__ import annotations

import ast
import io
import subprocess
import tarfile

repo = "/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers"
base = "f6c465648"
roots = ("policy-engine/src", "policy-engine/tests")
archive = subprocess.check_output(["/usr/bin/git", "-C", repo, "archive", base, *roots])
source_paths = []
test_paths = []
parse_errors = []
connector_producer_token_paths = []
source_receipt_calls = []
owner_event_token_paths = []
append_defs = []
append_calls = []
consumer_ref_hits = []
consumer_paths = {
    "policy-engine/src/polisyos/runtime/quality/epoch_staleness_projection.py",
    "policy-engine/src/polisyos/runtime/http/services/temporal.py",
}

def call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""

with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tf:
    members = sorted(
        (member for member in tf.getmembers() if member.isfile() and member.name.endswith(".py")),
        key=lambda member: member.name,
    )
    for member in members:
        path = member.name
        source_paths.append(path) if path.startswith("policy-engine/src/") else test_paths.append(path)
        extracted = tf.extractfile(member)
        assert extracted is not None
        text = extracted.read().decode("utf-8")
        if "ConnectorSourceProfileSnapshotProducer" in text:
            connector_producer_token_paths.append(path)
        if "ClaimLedgerOwnerEvent" in text or "claim_ledger_owner_event" in text:
            owner_event_token_paths.append(path)
        if path in consumer_paths:
            for lineno, line in enumerate(text.splitlines(), 1):
                if "EpochInheritanceRecomputeReceipt" in line or "read_epoch_inheritance_recompute_receipt" in line:
                    consumer_ref_hits.append((path, lineno, line.strip()))
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError:
            parse_errors.append(path)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node.func)
                if name.endswith("SourceProfileOwnerReceipt"):
                    source_receipt_calls.append((path, node.lineno))
                if name.endswith("append_verified_owner_event"):
                    append_calls.append((path, node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "append_verified_owner_event":
                append_defs.append((path, node.lineno))

print(f"base={base}")
print(f"tracked_python_denominator=src:{len(source_paths)} tests:{len(test_paths)} total:{len(source_paths) + len(test_paths)}")
print(f"parse_errors={len(parse_errors)} {parse_errors}")
print(f"group1_consumer_denominator={len(consumer_paths)}")
print(f"group1_receipt_or_reader_hits={len(consumer_ref_hits)} {consumer_ref_hits}")
print(f"group2_connector_producer_token_paths={len(connector_producer_token_paths)} {connector_producer_token_paths}")
print(f"group2_source_profile_owner_receipt_constructor_calls={len(source_receipt_calls)} {source_receipt_calls}")
print(f"group3_owner_event_token_paths={len(owner_event_token_paths)} {owner_event_token_paths}")
print(f"group3_append_verified_owner_event_definitions={len(append_defs)} {append_defs}")
print(f"group3_append_verified_owner_event_calls={len(append_calls)} {append_calls}")
PY
```

Exact output, exit 0:

```text
base=f6c465648
tracked_python_denominator=src:2617 tests:2490 total:5107
parse_errors=0 []
group1_consumer_denominator=2
group1_receipt_or_reader_hits=0 []
group2_connector_producer_token_paths=0 []
group2_source_profile_owner_receipt_constructor_calls=1 [('policy-engine/tests/unit/runtime/quality/test_capability_discovery.py', 1176)]
group3_owner_event_token_paths=0 []
group3_append_verified_owner_event_definitions=3 [('policy-engine/src/polisyos/scientist/evidence/claims/head_index.py', 2345), ('policy-engine/src/polisyos/scientist/evidence/claims/head_index.py', 2698), ('policy-engine/src/polisyos/scientist/evidence/claims/head_index.py', 3732)]
group3_append_verified_owner_event_calls=0 []
```

The one receipt construction is test-only. A second partition of the same 5,107-file AST
denominator printed:

```text
base=f6c465648
tracked_python_denominator=src:2617 tests:2490 total:5107
source_profile_owner_receipt_constructor_calls_src=0 []
source_profile_owner_receipt_constructor_calls_tests=1 [('policy-engine/tests/unit/runtime/quality/test_capability_discovery.py', 1176)]
```

This corrects only the dossier's constructor-call wording. The deciding Group 2 absence remains
exact: `ConnectorSourceProfileSnapshotProducer` had zero token occurrences across all 5,107 files,
and production had no owner-receipt constructor.

## Group 1 — `ds18-epoch-inheritance-recompute-projection-missing`

### Red first and positive control

Positive control, run before the red:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g1b /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/quality/test_derived_observations.py::test_epoch_inheritance_recompute_receipt_round_trips_exact_owner_graph -q
```

Exact output, exit 0:

```text
.                                                                        [100%]
```

The registered consumer witness was then observed red before the bridge existed:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g1c /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_temporal_routes.py::test_temporal_service_exact_reads_completed_recompute_at_requested_coordinate -q
```

Decisive exact output, exit 1:

```text
F                                                                        [100%]
E       AssertionError: assert 0 == 1
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
```

The zero was the projected dependency count: the persisted owner receipt existed but neither named
consumer exact-read it.

### Implementation and deciding green

`runtime/quality/epoch_staleness_projection.py` now enumerates persisted recompute receipts,
exact-reads each through `read_epoch_inheritance_recompute_receipt`, content-binds its ref/hash and
transition coordinate, rejects corrupt or ambiguous same-coordinate receipts, and projects only the
receipt matching the requested query/purpose coordinate. `runtime/http/services/temporal.py` supplies
that reader to the existing temporal projection. No second producer was added.

Deciding exact command:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g1e /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_temporal_routes.py::test_temporal_service_exact_reads_completed_recompute_at_requested_coordinate /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_temporal_routes.py::test_temporal_service_rejects_corrupt_same_coordinate_recompute_receipt /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_temporal_routes.py::test_temporal_service_rejects_ambiguous_same_coordinate_recompute_receipts -q
```

Exact output, exit 0:

```text
...                                                                      [100%]
```

The one permitted whole-file wave for the group's changed test files was:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x -o cache_dir=/tmp/polisyos-debt-r-g1-final /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_temporal_routes.py /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/quality/test_derived_observations.py -q
```

Exact output, exit 0:

```text
...............................................................          [100%]
```

### Preserved withholdings

- The non-signer branch remains top-level `status="not_established"` with
  `current_epoch_ref=None`, `decision_validity_status=None`, and
  `revalidation_required=False`.
- The receipt's target disposition is carried only as a replay coordinate. `source_classes`,
  `advisory_event_refs`, and `owner_evidence_refs` are empty on this branch.
- Certificates, lineage, perturbations, head-currentness and lifecycle authority remain behind the
  exact signer/transition path. No disposition authorizes reissue.
- A different temporal coordinate receives no dependency row and retains
  `derived_recompute_status_not_established`.
- Corrupt or multiple matching receipts fail the HTTP/service boundary with 422
  `epoch_staleness_recompute_receipt_invalid`; neither is downgraded to absence.

## Group 2 — `ds10-connector-acquisition-content`

### Red first and positive control

The meaningful positive control established that the canonical profile registry works before the
new discovery producer is considered:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g2-positive-real /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_control_api.py::TestSourceProfiles::test_list_profiles_has_builtin -q
```

Exact output, exit 0:

```text
.                                                                        [100%]
```

The named closure node was then observed red against the missing default producer:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g2-red-real /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed -q
```

Decisive exact output, exit 1:

```text
F                                                                        [100%]
E       assert packet.results
E       assert ()
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
```

### Implementation and deciding green

`ConnectorSourceProfileSnapshotProducer` directly consumes the canonical connector registry's
`query_entries` owner read and the source-profile registry's `list_all` owner read. It persists one
connector snapshot and one matching source-profile snapshot at the same timezone-aware
`observed_at`, computes a joint search snapshot digest, emits the existing strict
`SourceProfileOwnerReceipt`, and persists that receipt with both snapshot refs as manifest inputs.
The default source discovery provider is injected only inside the existing non-overridden registry
factory boundary.

The connector snapshot is a secret-free five-field allow-list (`connector_ref`, `namespace`,
`version`, `declared_capabilities`, `known_datasets`). Source rows expose header names and a digest,
never header values. Discovery remains candidate-only: results are discoverable, execution is
`not_established`, authority is `bridge_missing`, and `authoritative_for` is empty.

Deciding exact command, including the factory-override boundary:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g2-review-fixes /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_control_service_di.py::test_resolve_control_registry_providers_uses_factory_overrides -q
```

Exact output, exit 0:

```text
..                                                                       [100%]
```

The one permitted whole-file wave for the changed test file was:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x -o cache_dir=/tmp/polisyos-debt-r-g2-final /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/runtime/http/test_control_api.py -q
```

Exact output, exit 0:

```text
...............................................................          [100%]
```

### Standing P38 negative and preserved withholdings

- Calling `/api/v1/control/data/connectors` and `/api/v1/control/data/profiles` first produces zero
  connector snapshots, zero source-profile snapshots and zero owner receipts. The generic list DTOs
  are never discovery evidence.
- Only the canonical source capability-discovery request triggers the producer and yields exactly
  one paired snapshot set plus one receipt.
- A fixture connector carries `resilience_config={"api_token": "must-not-enter-source-discovery-cas"}`;
  the sentinel bytes are absent from the connector snapshot.
- Registry membership establishes neither live availability nor execution capability. The search
  ledger explicitly forbids list DTOs and registry membership as execution evidence.

## Group 3 — `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` and its named blocker

### Positive control and registered red

Positive control, run first, proves the existing monitor-to-candidate lifecycle mapping executes and
does not skip for an owner catalog or proof solver:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g3-positive /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_bridge_maps_detector_families_to_claim_lifecycle_and_public_revision -q
```

Exact output, exit 0:

```text
.                                                                        [100%]
```

Registered closure command:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python -m pytest -x --lf -o cache_dir=/tmp/polisyos-debt-r-g3-red /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit -q
```

Decisive exact output, exit 1:

```text
F
=================================== FAILURES ===================================
_____ test_monitor_event_persists_claim_supersession_without_in_place_edit _____
E           AssertionError: assert [<ClaimLifecy...ew_required'>] == [<ClaimLifecy...'superseded'>]
E             At index 0 diff: <ClaimLifecycleAction.REVIEW_REQUIRED: 'review_required'> != <ClaimLifecycleAction.SUPERSEDED: 'superseded'>
tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py:227: AssertionError
=========================== short test summary info ============================
FAILED tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
```

The failure occurs at the pre-existing semantic assertion, before any temporary instrumentation:
production persists `review_required`, not an owner-authorized supersession. The temporary witness was
removed immediately; `git status -sb` returned only the attached clean branch.

### Deciding stop rule

The complete 5,107-file base census finds zero `ClaimLedgerOwnerEvent` or
`claim_ledger_owner_event` paths. It finds exactly three `append_verified_owner_event` definitions in
`scientist/evidence/claims/head_index.py` — the port plus two implementations — and zero call sites.
The repository implementation at line 3732 deletes both arguments and returns
`ClaimLedgerHeadResolutionNonReceipt(code="claim_head_absent")`.

The obstruction is structural, not an estimate:

1. `core/contracts/c4_persisted_profiles.py` declares itself the frozen persistence-profile registry.
   It has only `claim_bridge_pending` and `claim_bridge_result` for this path.
2. `ClaimLifecycleBridgeResultStatement` is epoch-shaped: it requires batch receipt, requested query
   context, pending freeze and dependency denominator refs/hashes.
3. `ClaimLedgerHeadStatement.bridge_result_refs` are all exact-read and replayed as that one
   `claim_bridge_result` profile. Head generation is required to equal the length of that exact
   replay chain.
4. A legal/policy-context supersession owner event therefore cannot enter or replay from the Claim
   head unless a new profile/result family is added or the frozen result becomes a discriminated
   union. It also needs a separate verifier receipt/provenance and an appointed verifier; the
   producer cannot self-attest.

Changing that frozen profile/schema is forbidden by this task. Reusing the lifecycle result,
`ReissuePacket`, monitor metadata, a generic JSON artifact, or the epoch batch profile would satisfy
only form and would launder projection authority into Claim-owner authority (`P32`/`P38`). An
independent read-only reviewer reached the same stop verdict. No whole-file Group 3 run or source/test
commit was made after the deciding red, because there is no permitted implementation to verify.

`DS11-SCOPE-ADJUDICATION-RECORD` remains a different object. The complete Task R diff through the two
source/test commits is exactly seven Python files under runtime temporal projection, runtime
capability discovery and their tests; it contains no scope-adjudication path or artifact.

## Exact append-only register prose for architect transcription

### `ds18-epoch-inheritance-recompute-projection-missing`

> **TASK R 2026-09-01 — `blocked` -> `closed`; `bridge_missing` -> closed.** Commit `40577c39f` extends the two named consumers rather than building a second producer. The temporal service enumerates persisted completed-only recompute receipts, exact-reads each through the existing owner reader, rejects corrupt or ambiguous same-coordinate evidence, and projects the receipt only at its exact query/purpose/temporal coordinate. The registered semantic node is red-before/green-after and both changed test files finish 63/63 green. The two Task-B withholdings remain load-bearing: receipt-only projection never establishes epoch-head currentness or lifecycle/reissue authority; top-level status, Decision Validity status, certificates, lineage, perturbations and revalidation stay `not_established`/empty until the independently signed transition path exists.

### `ds10-connector-acquisition-content`

> **TASK R 2026-09-01 — `blocked` -> `closed`; the unowned producer is now complete at candidate authority.** Commit `e0ba8d61b` adds `ConnectorSourceProfileSnapshotProducer` at the canonical capability-discovery owner, persists matching connector and source-profile snapshots, content-binds both in the existing `SourceProfileOwnerReceipt`, persists the receipt with both manifest inputs, and supplies the default source discovery provider without crossing factory overrides. The named closure node is red-before/green-after and its whole file finishes 63/63 green. Connector/profile list DTOs remain a tested P38 negative: calling both generic routes creates no discovery artifact. Registry membership establishes neither execution nor publication authority, and a secret-bearing connector resilience field is excluded by a five-field persisted allow-list. Census correction: across the pinned 2,617 source plus 2,490 test Python files the producer had zero occurrences and production had zero receipt constructors, while one pre-existing test fixture did construct the receipt; the earlier phrase “zero constructor calls everywhere” is therefore narrowed to production without changing the row's deciding absence.

### `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`

> **TASK R 2026-09-01 — stays `blocked` on `claim-ledger-supersession-owner-event-producer-missing`; no scope-adjudication coupling was introduced.** The positive bridge control passes, while the registered production closure node exits 1 because the persisted action is `review_required`, not `superseded`. This is the correct authority refusal. The existing Claim-owner port and runtime bridge are present, but the bridge never invokes the owner-event port and production `append_verified_owner_event` remains a nonreceipt stub. Task R stops rather than route monitor metadata or a standalone lifecycle projection around the missing independently verified owner event.

### `claim-ledger-supersession-owner-event-producer-missing`

> **TASK R 2026-09-01 — stays `open`; deciding rule recorded, no substitute artifact built.** A complete pinned-base walk of 2,617 source plus 2,490 test Python files finds zero typed owner-event artifact/profile paths, three `append_verified_owner_event` definitions and zero calls. Every current Claim-head bridge ref is frozen and replayed as the epoch-specific `claim_bridge_result`, whose mandatory batch receipt, query-context, pending-freeze and dependency-denominator fields cannot represent legal/policy-context supersession. Honest closure therefore requires an authorized new/discriminated C4 persisted owner-event profile, a producer, an independently appointed verifier with persisted receipt/provenance, bridge invocation, CAS head advance and replay negatives. The Task R stop rule forbids the required governed schema change; monitor metadata, `ReissuePacket`, generic JSON and the existing epoch profile are explicitly rejected as evidence substitutes. Reassign only after that schema/profile change and verifier appointment are authorized.

## Verification and set movement

The tracked source-Python census at head is:

```sh
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers ls-tree -r --name-only HEAD -- policy-engine/src | /usr/bin/awk '/\.py$/ {count += 1} END {print "tracked_src_python=" count}'
```

Exact output, exit 0:

```text
tracked_src_python=2617
```

The base was also 2,617, so the delta is **0**. Group 1 and Group 2 extended canonical existing
modules under the reuse-first rule; Group 3 added no module because its schema stop fired. The count
therefore honestly did not move despite the original expectation that it might.

Final Ruff command over every changed Python file returned exit 0 with exact output:

```text
All checks passed!
```

After the required `corepack pnpm install --frozen-lockfile`, generated client freshness was clean for
all five runtime-api-client outputs and the runtime-dashboard API types. The architecture guardrail
then exited 1 on exactly:

- three deep imports from unchanged `runtime/http/services/acquisition_admission_bundle.py` into
  `core.artifacts.{manifest,signing,write_contract}`; provenance is `not_established` because no exact
  base replay was run;
- the trust-claim-posture generated artifact, whose all-`src/**/*.py` input denominator intersects
  Task R and is therefore Task-R-triggered generated drift, not labelled inherited.

No OpenAPI source, generated client, frozen profile, schema, deep-import baseline or trust-posture
artifact was edited to make that broad guardrail green.

The bound debt checker was run exactly once on the clean, attached, quiescent source/test tree:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine PATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tools/quality/validation/check_debt_ledger.py --check
```

Exact decisive output, exit 0:

```text
register_ids=178
closure_signal_pytest_selections=43
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=9
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=9
Informational findings (do not block):
```

There are zero blocking findings. The carried Task-O bound set was 10; current is 9. The strict set
delta is exactly the removal of `ds10-connector-acquisition-content`. The remaining nine are:

1. `DS11-EXTERNAL-A11Y-COUNTERSIGN`
2. `DS11-FULL-TRUST-CENTER-AND-DOCS-IA`
3. `DS11-GROUNDED-PERFORMANCE`
4. `DS11-PUBLIC-SIGNATURE-POPULATION`
5. `DS11-SCOPE-ADJUDICATION-RECORD`
6. `ds10-global-case-index-producer-allocation`
7. `ds10-public-decision-rendering`
8. `epoch-dependency-denominator-defined-twice-incompatibly`
9. `global-case-index-producer-missing`

Group 1 did not occupy the carried unresolved-identity set because its register row contains no
literal pytest closure command. Group 3's literal node already existed and collects; its problem is
the observed semantic red, not unresolved identity. The one-member reduction is therefore the exact
expected checker movement for the only Task R row that was in the carried missing set.

The docs lifecycle command was run after the journal contained all mechanism and register prose:

```sh
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine PATH=/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers/policy-engine/tools/quality/validation/check_docs_lifecycle.py
```

Exit 1 carries the following exact six finding identities and messages. The removed stub literal is
written as `frontend` + `/runtime-dashboard` rather than concatenated: quoting that trigger verbatim
inside this journal creates a self-referential seventh finding.

```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend` + `/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend` + `/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend` + `/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend` + `/runtime-dashboard`; use `apps/runtime-dashboard`.
```
