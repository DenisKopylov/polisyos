# R13 delta review: capture and custody

**Scope:** the 11 final rows (CAP-01–06, LIF-01–05) in `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/solutions/preferred-solutions.json`, plus `solutions/00-shared-decisions.md` in that plan. I did not reopen the native task set, earlier proposal files, other plan documents, or implementation. This is a bounded consistency check, not product verification, acceptance, or closure. No tests, imports, builds, installs, or protected data were involved.

## Remaining contradictions

### DCC-01 — CAP-02 still persists raw response bytes before CAP-03 can apply query-only rights
**Severity: high. Task: CAP-02, cross-row with CAP-03/LIF-05.**

**References:** CAP-02 `preferred_solution` describes an immutable body-plus-request/response witness; `implementation_steps[1]` says “persist body before exposing a receipt”; `acceptance_discriminators[0]` requires an immutable root. CAP-03 now correctly scopes CAS bytes to retention-permitted profiles and prohibits copying restricted source bytes for query-only profiles. Shared decisions §S02 permits either an immutable permitted artifact or a minimized lawful receipt, and §S06 requires query-only paths to retain only the permitted receipt.

**Counterexample:** A selected query-only source permits a derived output and receipt but prohibits raw response retention. CAP-02's default producer persists the body before CAP-03/LIF-05 can admit downstream use, so the rights decision cannot prevent the forbidden copy.

**Smallest correction:** Make capture conditional on the selected rights/sink profile before the first durable write. For a retention-permitted profile, persist the exact body root. For query-only, stream/compute only through an allowed transient boundary and persist the permitted result/receipt plus binding; if CAP-02 cannot establish its claimed completeness/replay without the prohibited bytes, leave raw replay unavailable and limit/refuse that claim. Do not place a raw CAS root behind a later use-admission check.

**Remaining external input:** Selected profile's raw/result/receipt permissions and the actual controlled transient/provider sinks. This is profile-specific; it does not require a global capture barrier.

### DCC-02 — CAP-01's input list still states a conjunctive grant requirement
**Severity: medium. Task: CAP-01.**

**References:** CAP-01 `preferred_solution` now permits native source/custodian permission **or another verified lawful basis**, and `acceptance_discriminators[2]` says to test public-query contracts and separate custodian grants “without inventing a universal conjunction.” But `inputs_to_resolve[1]` still says the search-provider contract **plus** accountable source/custodian disclosure permission.

**Counterexample:** For a demonstrably owned/public nonsensitive query, the native verifier accepts the applicable provider/source/use contract as the lawful basis and no source custodian signature is needed. The remaining input list still appears to require both inputs, contradicting the preferred path and its acceptance criterion.

**Smallest correction:** Rewrite that input as two separately classified questions: (1) provider terms for egress/logging/retention where applicable, and (2) one competent source/use disclosure basis, which may be the applicable provider/source/use contract or other verified authority. Explicitly say when one contract supplies both properties. Keep unknown sensitivity/recipient fail-closed.

**Remaining external input:** Actual recipient/logging terms and the authority applicable to the chosen query. Which permission evidence is sufficient remains source/use-specific.

## Owner allocation assessment

LIF-05 is now **sufficiently allocated at planning level as one task-owned seam**: its preferred solution assigns the single source-use/AP07 decision and composition to LIF-05; CAP-03/06 consume it; external authority/verifier, material-placement owners, and retention planning remain distinct; AccessScope and RetentionPlanner are explicitly barred from becoming grant authority. If a proved decision owner exists after accepted-source rebind, reuse it; otherwise the missing owner/bridge is assigned internal work under LIF-05, with a canonical API and consumer census, not an external wait or private CAP ledger.

That is not evidence that a current concrete module already owns source-use/AP07. The listed `reuse_anchors` are request scope, retention planning, ArtifactRef/manifest, and store access. Therefore keep the rebind condition explicit and do not report the owner as implemented or currently present. If tightening the row, replace “extend the canonical core/security source-use boundary” with “after rebind, name the proved existing owner or define one LIF-05-owned interface and implement the minimum owner-local producer/consumer seam”; that avoids presuming a path while preserving the single allocation.

## Prior findings resolved in this delta

- CAP-01 now permits an admitted no-hit query, forbids subsequent candidate/source fetch or admission, distinguishes denied disclosure, and calls for a permitted opaque token or tenant-scoped keyed binding. The implementation/acceptance address the earlier no-hit and guessable-digest risks. The composition field still calls this an “exact query digest”; read it as the permitted keyed/reference binding above, or rename it for consistency.
- CAP-02 now scopes continuation to an independently authorized recipient set, requires explicit egress/credential scope for CDN/foreign-origin continuations, accepts byte-identical replay under the same token/cut idempotently, and names the LIF-08 second-source sub-slice. These remove the prior same-origin and blanket-duplicate problems. Provider-specific overlap semantics remain profile evidence, not a universal rule.
- CAP-03 now distinguishes retention-permitted raw roots from query-only result/receipt retention. DCC-01 is the remaining cross-row conflict in the producer path.
- LIF-01 now explicitly admits a lawful query/result receipt when its actual custodian-side operation/content binding verifies, and preserves raw replay limitations.
- LIF-02 says a signed cutoff alone does not establish cross-store currentness and requires scoped source cut plus native validity/expiry semantics. No new cutoff finding in this delta.

No global barrier follows from these rows; scoped rebind, conditional source profiles, and source-specific completion joins remain intact.
