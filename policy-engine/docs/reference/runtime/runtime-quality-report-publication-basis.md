# Runtime quality report publication basis

Owner: Runtime quality owners.
Source of truth: `src/polisyos/runtime/quality/report_registry.py`, the runtime quality report publisher and admission consumers under `src/polisyos/runtime/quality/`, and `tests/unit/runtime/quality/test_runtime_quality_report_owner_contract.py`.

Runtime quality reports keep their existing top-level diagnostic fields in
runtime_quality_evidence. The publisher also attaches the internal
runtime_quality_publication_basis object. It retains the complete original
report input and the selected CAS, event, and envelope bindings before the
publisher's compatibility view overlays reference fields.

For owner-backed reports, the publisher verifies the just-written selected
Core CAS object and derives its writer payload from the original input plus the
exact registered owner marker. Scorecard admission replays the same projection,
compares the complete source payload to the verified CAS content, and joins the
basis's typed artifact reference and profile to the selected runtime reference.
The top-level runtime reference map, event profile, manifest link, and inline
envelope must still match that selected publication and pass the existing
manifest and envelope checks.

The basis is diagnostic provenance for the existing runtime job-details
surface. It does not establish report validity, source truth, currentness, or
authority by itself. Admission still requires the selected Core store,
declared manifest profile, verified payload, exact per-report producer
contract, manifest-linked envelope, and the existing authority predicates.
Evidence captured before the basis was introduced remains available as
diagnostic content, but its owner-authored report basis is not_established;
the consumer does not recover it by ignoring fields or rewriting CAS objects.
