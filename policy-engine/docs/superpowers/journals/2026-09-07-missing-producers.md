# Missing producers — local execution journal

Base: `main` at `edc104849a9830dd5249390aa5380bd49836490c`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/producers`.
Attached branch: `codex/missing-producers`. No push, stash, rebase or other-lane edits.
The journal is the explicitly requested exception to the source/test write allowlist.
DEBT-REGISTER and LEDGER remain architect-owned and unchanged.

## Plan and pattern pass

1. Re-establish each absence from the complete tracked Python denominator and
   execute the row's mechanism hypothesis before depending on it.
2. Reuse persisted producers and canonical source vocabularies. Wire each new
   artifact to its consumer, preserving empty institutional authority slots.
3. Run focused behavioral tests, adversarial variations and a removal probe
   that must fail while the declarations/markers remain. Review the combined
   source before final verification and append-only local commits.
4. Read committed branch bytes back; disposition both rows; stop before push.

Relevant patterns: P01/P02 (absent producer and bridge), P05/P15 (monitor metadata
and candidates cannot mint authority), P07 (frozen Claim replay profile), P29/P32
(exercise content admission, not field markers), P35/P38 (whole denominator and
vocabulary membership), P40 (classify review escapes before repair).
Target: producer -> CAS artifact -> consumer -> persisted/API observation, plus
a negative/removal witness. No owner appointment is made by this work.
Source predicates are recomputed from exact typed payloads and verified CAS
content. Institutional authority remains `not_established` where unallocated.
Separate work surfaces: root owns case index/provider/API tests and journal;
claim agent owns Claim source and its tests; case agent owns index unit tests.
CAS fixtures are per-test temporary roots; no shared database or fixed port.

## Measurement before construction

Root census and independent Claim-agent census each enumerated all tracked
`policy-engine/src/**/*.py`: **2,619 index paths = 2,619 HEAD-tree paths**, identical
sets; **2,619 AST parses, zero parse errors**. This base differs from the older
2,616-file register census. Sorted relative source path list SHA-256:
`9ee1982a3f38c6fc014df86c3cedb25ce97f83ed9e7f834792e581e7ac45ee7b`.

Reproduction, from `policy-engine` at the base (Python 3.14):

```python
import ast, hashlib, subprocess
from pathlib import Path

def source_paths(command):
    return sorted(p for p in subprocess.check_output(command, text=True).split("\0")
                  if p.startswith("src/") and p.endswith(".py"))

indexed = source_paths(["git", "ls-files", "-z"])
committed = source_paths(["git", "ls-tree", "-rz", "--name-only", "HEAD"])
assert indexed == committed
trees = {p: ast.parse(Path(p).read_text(), filename=p) for p in indexed}
print(len(indexed), len(committed), len(trees))
print(hashlib.sha256("\n".join(indexed).encode()).hexdigest())
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "case":
            print("case literal", path, node.lineno)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if "owner_event" in node.name or "supersession" in node.name:
                print("owner-event definition", path, node.lineno, node.name)
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if "owner_event" in name or "supersession" in name:
                print("owner-event call", path, node.lineno, name)
```

### global-case-index-producer-missing

The 12 exact `case` string literals occur in resource/scope vocabularies,
expert adjudication, PII field patterns, an OpenAPI missing-producer example,
the composer rejection, a slug fallback, and the G0 fixture-source declaration.
None emits a global case index. Additional case/index/provider/persist symbol
inspection found existing individual-case writers and the bounded
`Layer3G5W12DCaseBlockIndex`, not a global discovery producer.

The register's current zero-producer conclusion holds, but literal-site prose
from its older census is not a description of this base. The actual consumer
has two barriers: `CapabilityDiscoveryComposer` rejects a case provider and
`CapabilityProviderSearchResult` has no case receipt vocabulary. A producer
alone would leave `bridge_missing`.

Selected source: existing `execute_s2_design_search_operation` ->
`persist_s2_design_search_run` -> typed binding + DesignRecordV0 + PDC SearchLedger.
Index scope: complete native tenant/cell-visible canonical S2 binding vocabulary
at enumeration time. This is candidate inventory; other case vocabularies and
terminality are declared limitations. No capped HTTP run list is used as a
complete denominator. Arbitrary payload field names do not admit a case.

### claim-ledger-supersession-owner-event-producer-missing

Across the complete 2,619 Python paths there are three
`append_verified_owner_event` definitions (Protocol, unappointed stub, CAS stub)
and **zero calls**; no supersession-owner-event producer/resolver definition.
The named monitor bridge calls the lifecycle transition helper directly.
The row's adjacency-based implication that the append port is production-called
is false: `bridge_missing` is an additional capability absence.

Behavioral hypothesis test added at
`tests/unit/scientist/governance/continuous/test_owner_event_producer.py`:
real initialized Claim CAS head -> same-store production monitor bridge ->
persisted `review_required`, zero append-port calls, original Claim bytes and
durable head unchanged. Initial focused gate passed. A first fixture attempt
used a monitor timestamp before root creation; that fixture error was corrected
before this measurement, without changing product source.

## Verification environment

Offline worktree bootstrap could not find cached pinned jaxlib, nodejs-wheel,
pyarrow or scipy wheels. No lockfile/dependency change was made. Focused tests use
the existing dependency interpreter read-only:
`/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -B`, with
`PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1` and cwd in this worktree's `policy-engine`.
The interpreter reports Python 3.14.0, pytest 9.0.2 and Pydantic 2.12.5. Local test
conftest prepends this worktree's source. No other worktree is written.
Baseline `tests/unit/runtime/http/test_capability_discovery_api.py`: 7 passed,
exit 0. No directory-wide pytest or full-suite gate is used.

## Case implementation and limits

`GlobalCaseIndexProducer.produce` enumerates the native tenant/cell-visible CAS,
resolves the exact PDC binding vocabulary and its linked DesignRecord/SearchLedger,
checks content hashes, producer/schema identity, case/run/candidate consistency,
and actual nonempty instrument-family values, then persists and reads back a
`GlobalCaseIndexSnapshot`. Source artifact refs identify the binding denominator;
`scanned_artifact_count` identifies all artifacts visible at enumeration.

The default runtime provider registry now installs
`GlobalCaseIndexCapabilityDiscoveryProvider`; the existing composer accepts its
exact case receipt type. Each search produces a fresh snapshot, a persisted
receipt and a real SearchLedger, then projects candidates through the existing
HTTP endpoint. No second case writer or capped run-list source was invented.

End-to-end path:
`execute_s2_design_search_operation` -> `persist_s2_design_search_run` -> canonical
binding + record + ledger in CAS -> scoped index producer -> persisted snapshot
and receipt -> default capability composer ->
`POST /api/v1/control/capabilities/search`.
The HTTP witness creates an actual S2 run with the production writer, discovers
it, searches an actual family value, rejects the field name as a vocabulary
query, and reads back the referenced snapshot.

The authority slot is type-constrained to `None`. `s2_bindings_only`,
`terminality_not_established` and `recall_unmeasured` are carried into results.
The mechanism is limited to native FileSystemCAS enumeration and canonical S2
bindings visible to the current tenant/cell. Other case vocabularies, terminality,
whole-world recall and institutional appointment are not established. The runtime
storage guard's supported `for_tenant` delegation yields the native scoped CAS;
a missing scope or unsupported backend yields a typed provider non-receipt.
No engineering owner is appointed by this implementation.

Review found a NEW P38 class: substituting `case_id` when a source had no family
vocabulary would hide a missing basis. The producer now rejects empty/blank
coverage; tests mutate and rebind the actual ledger bytes to exercise that rule.
This is the bounded candidate-inventory property, not proof of external truth.

### Case removal probe

The exact unit selector is
`tests/unit/runtime/quality/test_global_case_index.py::test_real_s2_producer_emits_persisted_content_bound_case_index`.
An isolated interpreter replaces only actual family values while retaining all
classes, fields, persistence and verifier markers:

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -B - <<'PYPROBE'
import polisyos.runtime.quality.global_case_index as case_index
import pytest
original_resolve = case_index._resolve_entry

def field_names_instead_of_vocabulary(*args, **kwargs):
    entry = original_resolve(*args, **kwargs)
    return entry.model_copy(update={"instrument_families": ("instrument_family_coverage",)})

case_index._resolve_entry = field_names_instead_of_vocabulary
raise SystemExit(pytest.main([
    "tests/unit/runtime/quality/test_global_case_index.py::test_real_s2_producer_emits_persisted_content_bound_case_index",
    "-q",
]))
PYPROBE
```

Actual exit **1**. Persisted snapshot readback, CAS verification, scope, binding
and empty-authority assertions succeeded before the vocabulary assertion failed:
`assert set(entry.instrument_families) == set(_FAMILIES)`. Actual left set was
`{instrument_family_coverage}`; expected values were
`{cash_grant, credit_guarantee, interest_rate_buydown}`. No source file mutation.
The unmodified complete new unit file passed all **15** selected cases, exit **0**
(real 158.95 s, user 92.06 s, sys 5.51 s). The final case gate ran the complete
`tests/unit/runtime/http/test_capability_discovery_api.py` and
`tests/unit/runtime/quality/test_global_case_index.py` files together: **23 passed**,
actual exit **0** (real 244.25 s, user 98.14 s, sys 7.07 s). It used the exact
interpreter/environment stated above plus the venv bin directory on PATH and
`--junitxml=tmp/missing-producers-case-tests.xml`.

## Claim implementation and limits

A typed `SupersessionCandidateRequest` on a persisted monitor event reaches the
existing production `EpochClaimLifecycleBridgeService`. The existing Claim owner
resolves its current head and produces an **unsigned** content-bound owner-event
candidate. The bridge enumerates the exact same-store event vocabulary and calls
`append_verified_owner_event`; detector metadata never substitutes for this act.

`owner_events.py` resolves the actual monitor, legal evidence, prior ledger and
successor candidate. The authority dependency has an explicitly empty default
`owner_event_authority: ClaimSupersessionAuthority | None = None`. Admission
requires two distinct Ed25519 signing keys: the independently verified institutional
grant and its grantee's event signature, with exact owner/purpose/time and content
bindings. No default grant, signer, trust root or engineering appointment is made.
Absent authority yields `claim_owner_event_authority_unappointed` and no head move.

A successful append persists a new ledger, a distinct frozen C4 owner-event bridge
profile and a new head through the existing sole compare-and-swap mutation path.
Replay resolves the exact admitted appointment ref/hash, re-verifies the signatures,
recomputes the transition, and compares the actual persisted successor ledger bytes.
Repeated admission is idempotent. Existing Decision Validity pending/bridge consumers
recognize the distinct event bridge without letting it settle unrelated pending work.

End-to-end path:
persisted monitor request -> owner candidate producer -> CAS owner-event artifact ->
external signing dependency -> production monitor bridge -> verifying Claim owner ->
new CAS ledger + frozen bridge + head CAS -> replay -> EXPERT/PUBLIC export.
The positive test supplies synthetic fixture institutions explicitly; it does not
claim a production appointment. The advisory monitor projection remains
`review_required`; the separately typed owner outcome reports the actual head result.

Review classified successor promotion as the SAME P32 trust-by-form class one
level deeper. The structural correction never inserts the successor candidate into
`current_claims`: it appends only the predecessor's verified SUPERSEDED relation,
with the successor as a separate `next_claim_ref`. EXPERT and PUBLIC export tests
assert that the unissued successor is absent. Separate successor issuance remains
required. A NEW P07 replay class was also closed by freezing appointment ref/hash;
a differently signed but matching replacement grant cannot rewrite admission history.

The exact existing integration witness is
`tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit`.
Its old metadata-only expectation is replaced by the real producer/consumer/export
helper. Metadata-only input remains an explicit negative test. Production authority
remains unallocated; this closes mechanism/bridge work subject to that limit.

### Claim removal probes

Both commands ran from `policy-engine`, with source bytes unchanged. The common
prefix is `env PYTHONPATH=src:. PYTHONDONTWRITEBYTECODE=1
/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -B -` followed by the
shown here-document. Each probe is its own process and its actual exit was **1**.

Remove the append effect while preserving signed event, head/profile types and
all marker fields:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from polisyos.scientist.evidence.claims import owner_events
from tests.unit.scientist.governance.continuous.test_owner_event_producer import (
    _assert_signed_owner_event_round_trip, owner_event_case,
)
owner_events.apply_claim_supersession_owner_event = (
    lambda *, store, ledger, event, owner_event_ref: ledger
)
with TemporaryDirectory(dir="tmp") as scratch:
    _assert_signed_owner_event_round_trip(owner_event_case.__wrapped__(Path(scratch)))
```

The production producer/service/CAS path ran, but the exported relation was absent:
`assert export.superseded_claim_ids == ["predecessor"]` failed. Thus signature,
artifact and field markers cannot satisfy the end-to-end property by themselves.

Replace cryptographic verification with shape-only success while preserving the
signature-verifier port and its status/key/identity fields:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from polisyos.core.artifacts import FileSystemCAS, SignatureVerificationStatus
from tests.unit.scientist.governance.continuous.test_owner_event_producer import (
    test_owner_event_verification_rejects_present_but_unproven_evidence,
    owner_event_case,
)
def trust_shape_only(self, artifact_id, verifier, *, strict_identity=None):
    key_id = verifier.trusted_key_ids[0]
    return SimpleNamespace(
        status=SignatureVerificationStatus.VALID,
        key_id=key_id,
        signer_identity=verifier.expected_identity(key_id),
    )
FileSystemCAS.verify_signature = trust_shape_only
with TemporaryDirectory(dir="tmp") as scratch:
    test_owner_event_verification_rejects_present_but_unproven_evidence(
        owner_event_case.__wrapped__(Path(scratch)), "unsigned"
    )
```

The unsigned event was incorrectly admitted and the negative witness failed at
`assert isinstance(outcome, ClaimLedgerHeadResolutionNonReceipt)`. This probe
removes the evidence property itself, not just a declaration or marker.

Final-source root-facade import adaptation was also exercised by a fresh
unmodified `_assert_signed_owner_event_round_trip` invocation, actual exit **0**:
`final source import and production supersession round trip: PASS`.

## Verification receipts and handback

Final focused gates and Claim removal receipts are recorded below. No
repository-wide pytest was authorized or run. Each shell gate is its own command,
with the tool's actual exit used as the result.

All changed Python files: final-source Ruff exit **0**; `git diff --check`: exit **0**.

Claim final focused selection: **14 cases, actual exit 0**. Common command prefix:
`env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -B -m pytest`.
Exact selectors followed by `-q -p no:cacheprovider`:

```text
tests/unit/scientist/governance/continuous/test_owner_event_producer.py
tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit
tests/unit/scientist/evidence/claims/test_head_index.py::test_owner_event_append_requires_an_explicit_authority
tests/unit/scientist/evidence/claims/test_head_index.py::test_unappointed_owner_cannot_invent_a_candidate_root
tests/unit/runtime/quality/test_open_world_risk.py::test_promotion_artifacts_use_the_frozen_profiles_and_independent_preimages
```

Separate final lifecycle blast gate, same command prefix/options:
`tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py`: **14 cases,
actual exit 0**. Logs: `tmp/claim-final-focused.log` and
`tmp/claim-final-lifecycle-bridge.log`. The only warning is the configured
`cache_dir` option becoming unknown when cacheprovider is disabled; no assertion
was skipped. Exact durations for these two commands were not measured.

Earlier Claim head blast evidence, **5 selected cases, exit 0**, predating the final
appointment/import delta (the fresh final chain above exercises that delta):

```text
tests/unit/scientist/evidence/claims/test_head_index.py::test_fixture_authority_finalizes_generation_zero_and_exports_current
tests/unit/scientist/evidence/claims/test_head_index.py::test_well_shaped_fake_root_issuance_cannot_be_registered_or_exported
tests/unit/scientist/evidence/claims/test_head_index.py::test_verified_epoch_batch_advances_one_closed_head_with_stale_event
tests/unit/scientist/evidence/claims/test_head_index.py::test_two_sequential_batches_advance_one_claim_ledger_head_without_fork
tests/unit/scientist/evidence/claims/test_head_index.py::test_crash_after_dv_completion_keeps_claim_bridge_pending_public_freeze
```

The case blast selection was exactly
`tests/unit/runtime/quality/test_capability_discovery.py`,
`tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py`, and
`tests/unit/runtime/http/test_control_service_di.py`.
Its original actual exit was 1 (real 454.57 s), with the replay PATH failure
adjudicated below; it is not reported as a fresh all-green combined gate.
The case HTTP witness exposed two fixture issues during integration (an invalid
empty construct list and snapshot readback after closing the client guard); both
were corrected. It also exposed a real production proxy mismatch in the new
producer; the producer now scopes through the supported `for_tenant` port.

The three-file case blast-radius gate initially exited **1** only because its
replay subprocess invokes bare `python`, absent from the shell PATH. Its earlier
assertions and all other selected tests passed. The exact failed node,
`tests/unit/runtime/quality/test_capability_discovery.py::test_case_provider_missing_is_typed_and_frontier_is_incomplete`,
was rerun with the existing venv directory explicitly on PATH and passed, exit
**0** (real 715.15 s). This is a harness correction, not an assertion that a product
failure was inherited.

A full architecture diagnostic was canceled while source was still changing,
after 1230.15 s inside generated-artifact filesystem snapshot work. It provides
no final architecture receipt. A frozen-source check with the documented
`--skip-generated-checks` flag is the bounded architecture gate for this task.
The canceled CLI additionally raised `UnboundLocalError` while handling the
interrupt; see proposed incidental row below. No tool file was changed.
An obsolete HTTP debug invocation was also canceled. An optional independent
Claim export probe never produced a captured final receipt: `not_established`;
it is not used as evidence. The actual reviewed successor issue and its final
positive export tests are recorded separately.

### Red checks and base replay (no exclusion-green claim)

The first frozen architecture check exposed two introduced Claim edges into
`polisyos.core.artifacts` and `polisyos.core.canon`. They were repaired in source
through `from polisyos.core import ...`, without editing the architecture baseline.
The final bounded command was:

```sh
/usr/bin/time -p env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -B -m tools.cli architecture guardrails check --skip-generated-checks
```

Final actual exit **1** (real 199.81 s): the complete diagnostics contain only
three deep-import edges owned by
`src/polisyos/runtime/http/services/acquisition_admission_bundle.py`, to
`polisyos.core.artifacts.manifest`, `.signing`, and `.write_contract`, plus their
baseline drift. No introduced producer edge remains in that diagnostic set.

The same command was replayed from the slice's original base
`edc104849a9830dd5249390aa5380bd49836490c`, using an isolated ordinary `git archive`
under `tmp/missing-producers-base`, never moving HEAD or another worktree.
The first archive omitted root workflows and produced additional missing-workflow
errors; that was a replay harness defect, not product evidence. All 19 base
`.github` paths were then copied into the isolated snapshot and checked byte-for-byte
against that base. The corrected replay exited **1** (real 155.58 s), with diagnostics
**byte-identical after removing only timing lines** to the final branch diagnostic.
Normalized diagnostic SHA-256:
`83222fcdf3ced06fdbdcf01c6f376ec616139b272b8167cb42617f8aae5e85f4`.
The governed files in the working branch were never edited.

A combined Claim selection had a complete AST-derived denominator of **39 cases**
(9 new producer, 1 integration, 14 lifecycle, 11 monitors, 3 head companions,
1 profile); **zero executed**, actual exit **2**, because `test_monitors.py`
failed collection. The final 14-case producer selection and separate 14-case
lifecycle selection above actually execute and pass; the collection failure is
retained as a red check, not excluded to claim the original gate passed.

The exact failing monitor file was run alone on final source and the same original
base, using the common pytest prefix plus
`tests/unit/scientist/governance/continuous/test_monitors.py -q -p no:cacheprovider`.
Both actual exits were **2** (current real 314.94 s, base real 313.87 s), with the
same circular import path:
`control_plane_store` -> `control.response_shapes` -> `control.py` shim ->
`control.api` -> `control.run_lifecycle` -> partially initialized
`control_plane_store.AcquisitionActionHeadRecord`.

P41 boundary: base reproduction is established for these exact red commands;
**whole-gate disjointness is not established**. The architecture command reads
the entire source tree, which includes this lane's eight changed Python source
files, and the monitor command's full transitive import denominator has not been
proved disjoint. Therefore neither gate is called inherited-green, unrelated,
or fully passing. They remain explicit validation limits for architect adjudication.
No acquisition/shim/architecture repair is bundled into producer work.

### Parallel-lane test path reconciliation

New path under `tests/unit/scientist/`:
`tests/unit/scientist/governance/continuous/test_owner_event_producer.py`.
Changed existing path:
`tests/unit/scientist/evidence/claims/test_head_index.py`.
The existing integration path is
`tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py`.
Other added test path: `tests/unit/runtime/quality/test_global_case_index.py`.
Changed runtime tests: `tests/unit/runtime/http/test_capability_discovery_api.py`
and the frozen-profile companion in `tests/unit/runtime/quality/test_open_world_risk.py`.
These are actual local files to reconcile with the parallel workflow-path lane;
no workflow or tools file was modified here.

### Proposed incidental rows (architect transcription only)

Proposed ID: `cli-interrupt-obscures-gate-exit`.
Proposed owner: `team-devx` / CLI runner engineering (proposal, not appointment).
Evidence: interrupting the architecture generated-artifact diagnostic raised
`KeyboardInterrupt` in `_snapshot_filesystem_tree`, then
`tools/cli.py::_run_registered_tool` referenced unassigned `exit_code` at line 413
and raised `UnboundLocalError`. The gate returned exit 1; neither exception is a
product validation receipt. Proposed closure: initialize/finalize CLI timing state
without replacing the original interruption and test that behavioral path.
Repair needs a forbidden `tools/**` file and is handed back, not attempted.

Proposed ID: `acquisition-admission-deep-import-baseline-drift`.
Proposed owner: `team-runtime` / DS15 acquisition engineering, with architecture
owner adjudication (proposals, not appointments). The final/base bounded guardrail
receipts above identify the three exact deep imports. Proposed closure: use the
approved facade or obtain the architecture owner's explicit baseline ruling;
retain a fresh complete guardrail receipt. This lane does not edit the acquisition
mechanism or the forbidden architecture files.

Proposed ID: `monitor-test-control-store-import-cycle`.
Proposed owner: `team-runtime` / control-plane composition engineering (proposal,
not appointment). Both base and final standalone monitor-file gates fail collection
through the exact circular import above. Proposed closure: close the import cycle
structurally and run the standalone test file in a fresh interpreter, without
relying on an earlier HTTP test to preload modules. Gate exclusion remains
`not_established` for this lane.

### Final dispositions

- `global-case-index-producer-missing`: **repaired-with-a-limit**. Producer,
  persistence, default consumer/API bridge and negative semantic witness are
  verified. S2/native scoped inventory and unallocated authority limits remain.
- `claim-ledger-supersession-owner-event-producer-missing`:
  **repaired-with-a-limit**. Candidate production, consumer handshake, verified
  append, exact replay and export are exercised. Institutional appointment remains
  an empty typed slot, initial-root authority remains an external prerequisite,
  and successor issuance is separate. The broader red gates above remain explicit
  validation limits; no full-suite or all-gates-green claim is made.

Pattern closeout reopened P01/P02/P05/P07/P29/P32/P35/P37/P38/P40/P41 in the failure
register. No new recurring pattern is written there because that path is outside
this lane's allowlist; the findings use its existing repair classes.

Case commit `d207b82f5f231fc0ea8653027b2576b33d6a71b2` was read back from
`codex/missing-producers`: all seven committed paths matched the worktree bytes.
A complete changed-path census before final commit found **17 paths**: source,
own tests and this explicitly requested journal; **zero outside the user allowlist**.
Final Claim/journal commit and committed-branch readback follow this entry.
The shared pre-commit hook reported no Lefthook config at this worktree root;
ordinary `git commit` returned 0. No hook validation is claimed in place of the
explicit gate receipts above.

DEBT-REGISTER and LEDGER remain unchanged for architect transcription. Engineering
and institutional owners remain unallocated. Work stops locally at the push boundary.
