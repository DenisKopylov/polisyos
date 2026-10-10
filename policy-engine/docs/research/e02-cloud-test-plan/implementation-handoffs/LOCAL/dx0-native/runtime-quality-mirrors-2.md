# Runtime Quality section 6 mirror tests

## Scope and P40 classification

This packet records the 11 tests assigned from section 6 of
`LOCAL/dx0-native/ratchet-repair-routing-current.md`. Production sources were read-only.
Each test is **the same routed property class at a deeper discriminator**, not a new
authority rule or a per-instance production repair. These tests do not constitute a
G-acceptance decision or a formal finding closure.

The suite adds one owner-path counterexample per routed module:

| New test | Property exercised by the real route | Distinguishing case |
| --- | --- | --- |
| `tests/unit/runtime/quality/test_epoch_certificate_issuance.py::test_execution_recipe_reads_the_complete_admitted_source_denominator` | `DecisionPacketEpochIssuanceOwner._complete_recipe_inputs` reads the complete typed execution closure from CAS. | A complete closure succeeds; omission of an invocation input and an unresolved tool source each refuse. |
| `tests/unit/runtime/quality/test_epoch_evidence_exchange.py::test_old_appointment_cannot_authorize_against_a_revoked_current_owner` | `EpochEvidenceExchange` re-resolves an appointment against the current deployment before returning acceptance authority. | The original deployment returns a usable exchange; the same appointment against a newly revoked deployment returns `AcceptanceUnavailableNonReceipt`. |
| `tests/unit/runtime/quality/test_evaluation_modes.py::test_canonical_modes_resolve_to_owner_bands_without_creating_authority` | Canonical evaluation modes map to the owner dispatch bands. | All six accepted tokens map; an absent attempt stays candidate-only and a whitespace-altered token is not established. The result is a dispatch band, not authority. |
| `tests/unit/runtime/quality/test_event_log.py::test_nested_secret_forces_exact_small_payload_through_cas` | `RuntimeDiagnosticEventLog.append` detects sensitive keys recursively and binds stored payload bytes to the persisted digest. | A short, non-authority `dev` payload with a nested `api_key` is read back byte-for-byte from CAS with its independently computed SHA-256. |
| `tests/unit/runtime/quality/test_evidence_independence.py::test_duplicate_source_mass_is_collapsed_independent_of_input_order` | The independence-map producer collapses duplicate lines sharing the full source/method lineage and preserves the effective result when inputs are reordered. | Two distinct specification/evidence/event rows over the same lineage remain raw count 2, effective count 1; effective mass, group membership, source/method dimensions, and collapse reasons remain equal when reversed. The chosen representative remains a group member. |
| `tests/unit/runtime/quality/test_evidence_line.py::test_evidence_line_refuses_a_portfolio_declared_after_execution_started` | Evidence-line validation binds accepted evidence to an existing predeclared portfolio before producer execution. | The same valid line/design is rejected when the execution start precedes declaration and accepted when execution starts after declaration. |
| `tests/unit/runtime/quality/test_evidence_synthesis.py::test_synthesis_builder_requires_each_previous_wave_evidence_class` | The synthesis builder requires every previous-wave source class before emitting a report. | Four populated ref classes do not make the previous wave complete when the disconfirming-ledger class is absent. |
| `tests/unit/runtime/quality/test_explanation_reliability.py::test_passing_explanation_metrics_do_not_fill_missing_claim_argument_surfaces` | Claim-argument validation consumes a matching passing BERL record without treating explanation reliability as claim argument, rebuttal, or counter-evidence. | A passing threshold/bounds record is present, while missing claim surfaces still produce a failed claim-argument result. |
| `tests/unit/runtime/quality/test_graded_outcomes.py::test_one_blocked_claim_keeps_mixed_closeout_blocked_alongside_a_pass` | S1 composition persists a mixed set through the existing status-envelope closeout reader. | One exact pass plus one unsupported production claim yields a blocked envelope and a claim-bound failure issue. |
| `tests/unit/runtime/quality/test_projection_semantics.py::test_contested_source_state_blocks_a_publishable_projection_label` | Projection state derives from the source case and cannot promote a conflicting contested status to publishable. | The source simultaneously says `status=contested` and `publishability=publishable`; the output retains contested and omits publishable while remaining projection-only. |
| `tests/unit/runtime/quality/test_source_truth.py::test_missing_reader_value_is_a_conflict_not_an_equal_or_complete_value` | Source-truth comparison treats an absent lower-authority field as lost authority-bearing information. | The authoritative packet ref is present while the reader projection omits it; the emitted conflict lists the lost field. |

The existing cross-Scientist epoch-certificate test route and the existing cross-runtime
quality selectors remain untouched. No old test module is imported as a fixture; the two
shared helpers used are the neutral appointed-anchor evidence fixture and canonical PDC
case fixture.

The first combined run's full-map equality assertion failed only at
`collapse_clusters[0].representative_line_id`: the forward result selected `line-a` and
the reversed result selected `line-b`. A standalone replay of the real builder with the
same test inputs found raw count `2/2`, effective count `1/1`, equal complete
`effective_mass_report`, equal cluster line IDs, equal collapse dimensions, and equal
collapse reasons. The source currently chooses the first input line as representative;
the current runtime-quality paths do not consume this field, and I found no canonical
serialized-map or artifact-ID contract requiring a stable representative. The repaired
test compares the effective result and exact source/method/group/reason bindings, then
checks that each representative names a cluster member. It does not claim byte-for-byte
map determinism.
This is the same independence property at a deeper discriminator: the original
source-closure case is preserved, with no second test or authority rule added.

The next affected-five-path replay exposed one test expectation error at the source
binding assertion. It had expected `source_id|source_ref|lineage_ref` in input order, but
the producer's source key is the pipe-delimited, unique set of `source_id`, `source_ref`,
and all `lineage_refs`; this fixture's two hashes are canonically ordered opposite to
their input order. The corrected test checks that the decoded key has no duplicate
tokens and that its complete token set equals the input source ID and references. It
does not constrain diagnostic string order. This is the same independence class at a
deeper discriminator: source binding remains intact and effective mass is unchanged.

The exact replay was an iteration, not a frozen run: root's command record lists one
unrelated source-input change (`src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py`)
during execution. The command, stdout, JUnit, and pre-run input inventory are retained at
`LOCAL/raw/dx0-owner-mirrors-combined-fixes/command.json` (`e35ffb8d6e417dbd09e5ac109932018f252a2da37f779110b6e4f503c20834b4`),
`stdout.txt` (`7dd37155f29ff56020cd07620a30740ac70dae11637b065ba1a87140eca99298`),
`junit.xml` (`37a29906818f814a8ee60364c1a059bd86b12d7e085166e78e223faac1bc1c57`), and
`inputs-pre.json` (`c32ffff07e521331a650c3e7eeed87e1c1d41cb36117332c41debb8815852dd2`).
That run had four passes and only this assertion failure. The standalone key readback is
`LOCAL/raw/dx0-owner-mirrors-combined-fixes/order-lineage-diagnostic.txt` at
`a6b317127238c2948c3b80326f5226281998b8ac626c20f72e3918aed6c0c401`.

## Exact bytes and verification

The production-source and new-test SHA-256 inventory is
`LOCAL/dx0-native/raw/runtime-quality-mirrors-2-sha256.txt` at
`84007930fa1c7ab81c45557a79e1e07b52b7f5755cb34db39639c1262fcc8404`; it records the
repaired test hash `a7cf0cb3507889b1ffefce26859c70385072f83f5a7b46addaa45b96b9a6d6e6`. The
independence-map source remains
`161b6cd2b193050495615b75306d3b239e3e9420e512d19bb49f1bcab625646b`; no production
source changed. The standalone diff and its output are retained at
`LOCAL/raw/dx0-owner-mirrors-combined-first/order-diagnostic.txt`.

Scoped checks used the candidate product root and its `.venv`:

| Command | Result | Full output |
| --- | --- | --- |
| `.venv/bin/python -m ruff check <the 11 listed test paths>` | Exit 0, “All checks passed!” | `LOCAL/dx0-native/raw/runtime-quality-mirrors-2-ruff.txt` at `b55a15a18a1ea234f7b205b754b1ce8f698d25d732bb90da1cdb1a19c52c634a` |
| `.venv/bin/python -m ruff format --check <the 11 listed test paths>` | Exit 0, “11 files already formatted” | `LOCAL/dx0-native/raw/runtime-quality-mirrors-2-format.txt` at `aa48b1c0bb7586dcd487b794e4ee169c5a7b036e8fdb82050cc32fbb2021ff69` |
| `.venv/bin/python -m py_compile <the 11 listed test paths>` | Exit 0, no diagnostics | `LOCAL/dx0-native/raw/runtime-quality-mirrors-2-pycompile.txt` at `19eaf43821a7660ec323a87c8457bf74823beb296c39f5e01aa8a683aa50f061` |

After the source-binding assertion adjustment, checks on the changed test alone passed:
Ruff check (`LOCAL/raw/dx0-owner-mirrors-combined-fixes/order-ruff.txt`,
`241282764e775e958f2fca2b03911c1a136a9962479dc41524c6f58a1a2bc16e`), Ruff format
check (`LOCAL/raw/dx0-owner-mirrors-combined-fixes/order-format.txt`,
`a20c7723980eefbc950c33c5fc1f6f5349a6caac7d3234d450427e726ba4e465`), and
`py_compile` (`LOCAL/raw/dx0-owner-mirrors-combined-fixes/order-pycompile.txt`,
`b1e36e8a1744179fcd6b175efefa10d4380b018a733682c7de6feda22efe7f62`). These static
checks do not replace the root's next combined execution.

I did not run pytest under the root's execution hold. Root's affected-five-path iteration
is recorded above as four passes and one failure in the earlier order-sensitive source
binding assertion; this test-only correction has not yet been included in a combined
rerun. The corrected assertion therefore has no pytest pass claim here.
