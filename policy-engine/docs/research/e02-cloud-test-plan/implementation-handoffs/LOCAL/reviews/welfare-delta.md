# Independent E11 Welfare delta review

Review disposition: the bounded candidate behavior is demonstrated for B192/B194, but this is not a formal finding closure. Source law authority and part of B194's failure classification remain explicit residuals.

## Reviewed candidate

Product worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`  
Candidate HEAD/tree: `077a572ff5880b3f50a85d3e3db6a232d277659a` / `2895b6c7597215b714275cb4ba83a504724dc89c` (shared, dirty worktree; these are not the source-change commit). The source module imported by the local `.venv` resolves to this worktree's `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` with `PYTHONPATH=src:.`.

Frozen reviewed paths (SHA-256):

- `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` — `5ac80606ae9a25d07c14d13b1bc241d15c43ff46a05a559a073a7428e03fb602`
- `tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py` — `7c5d907a2ee842c57f8cef59dda47bbe24029dcfa112e32f7348c477814a3f68`
- `src/polisyos/scientist/nodes/README.md` — `1cb48a58d1b989e456dd5b1ca2ca12d68a880904687ef6df0655581c8aa56fe6`
- `release-fragments/unreleased/2026-10-09-e02-e11-welfare-monte-carlo-truthfulness.toml` — `f573cc604ad076646952b3bac400747e2e7d7e4afc19849d6af6db94065f9383`

## Findings

**B192 consumer behavior is repaired at the candidate boundary.** The node consumes weighted `PosteriorSamplesCarrier` atoms, and multiple empirical inputs are joined only when the declared joint ID is nonempty and equal, axes are nonempty and equal, row counts match, and normalized weights agree (`src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py:3139-3190`). Tests cover weighted atoms and six paired-row controls: aligned rows, reversed rows, absent IDs, different IDs, empty axes, and whitespace-only axes (`tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py:2285-2465`). When the row key is absent or mismatched, the path withholds the sample bundle and interval.

This proves candidate row selection, not an authoritative joint law. The implementation records `joint_identity_status="declared_non_authoritative"`, but matching metadata still enables paired sampling and a complete-draw interval. No independent issuer or content-bound relation authenticates that declaration. P37 predicate status for source-law authority is therefore `not_established`; the paired-row predicate is consumer-asserted metadata plus recomputed equality checks. B188 remains a G/issuer decision, and no formal closure is claimed.

**Selected source lineage now survives the report boundary.** The Delta path carries selected envelope refs into its report manifest (`propagate_welfare.py:2282-2311`); the Monte Carlo report and sample bundle do likewise (`:2105-2162`). The positive test uses the same artifact bytes under two manifest profiles, confirms the selected profile on a fresh CAS read, then corrupts the selected profile ref and confirms resolution fails (`test_propagate_welfare.py:1986-2084`). This is a behavioral source-binding control, not a manifest-shape assertion.

**B194 incomplete draws are represented honestly in the controlled fixture.** The producer emits one terminal outcome per requested draw, including sampled-input digest, success/sample index or failure code/type/bounded message, and denominator counts (`propagate_welfare.py:1901-2023`). A partial run persists a conditional successful-draw summary and does not create a Monte Carlo credible interval (`:2034-2066`). The fixture drives the actual `PropagateWelfareNode`, persists the sample, report, and Welfare bundle, reloads them from a fresh CAS, and calls the actual decision-packet `_build_welfare_section`; it observes nominal point `1.0`, conditional report mean `2.0`, partial status, no interval, and the warning/semantics in the consumer (`test_propagate_welfare.py:2090-2248`; consumer at `scientist/nodes/builtins/decide/decision_packet/enrichment.py:1769-1846`). The producer labels the point as `nominal_input_evaluation` and warns that the report mean is conditional (`propagate_welfare.py:460-482`).

The B194 residual is narrower but material: every `Exception` from sampling or simulation becomes a terminal `sampling_exception` / `simulation_exception`; there is no distinction between transient failure, unsupported input region, or a global contract/program error, and no bounded retry of the exact same sampled input (`propagate_welfare.py:1905-1940`). This is directly warranted by original criterion B194 in `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md:4792-4807` (SHA-256 `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`): it calls for a bounded retry of the same draw for transient failures, conditional diagnostics for unsupported regions, and not absorbing global access/contract errors as ordinary noisy points. This does not require retrying every error. The current failure fixture is a deterministic domain-like exception and proves denominator/conditional-output honesty, not transient retry or global-error behavior. The smallest missing capability is an error distinction that retries the same draw only for the transient class and does not downgrade global errors to draw noise. Until then, B194 is candidate-level partial semantics, not complete recovery/closure. The current behavior still avoids an unconditional-looking interval when a draw fails.

## P40 and capability boundary

P40 bucket: **SAME_CLASS_DEEPER** for B192/B194. The new witnesses were source-ref lineage and the complete paired-row identity/axis/count/weight domain; the author widened the report refs and row admission across their shared paths rather than patching one fixture. The remaining B188 authority and B194 failure taxonomy are bounded residuals; further examples of these declared classes should fold into the residual unless the mechanism is widened.

Capability label: `candidate producer-artifact-consumer-verification path exercised; formal finding closure absent`. The internal node persists typed Welfare/sample artifacts, the decision-packet builder consumes the Welfare bundle, and tests cover fresh-CAS readback plus negative controls. The consumer function is exercised directly; the selector does not run the entire decision-packet node/render/export path. The release fragment explicitly keeps external API/client surfaces out of scope. The tests use a controlled simulation callback and do not prove a native fitted model, live data authority, or institutional admission of the posterior/joint law. `src/polisyos/scientist/nodes/README.md:44-56` and the release fragment both preserve that boundary.

## Verification evidence

Independent focused selectors: Delta selected-profile readback/corruption, weighted empirical atoms, six paired-row controls, partial-draw CAS/consumer projection, covariance-conflict controls, and tied-calibrator propagation; **12 passed**, with two upstream Python 3.14/Torch JIT deprecation warnings. Full stdout: `LOCAL/reviews/raw/welfare-final-independent-tests.log` SHA-256 `18fac177648faef188257c7bec68e13f7ff4fe3090d237fd671cb31bbe151579`.

Explicit Ruff paths passed; log `LOCAL/reviews/raw/welfare-final-independent-ruff.log` SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`. Release TOML parsed (`id=2026-10-09-e02-e11-welfare-monte-carlo-truthfulness`, 17 keys); log `LOCAL/reviews/raw/welfare-final-independent-toml.log` SHA-256 `adda166bf83c4783adc2632e7591c3d723bb0bf53e5bc5f3a3c67b7cc3fb779a`.

Author's remove-the-property control removes the nonempty-axis guard and makes the empty-axis paired-row case incorrectly sample; expected-red output is `LOCAL/raw/welfare-review-current/06-axis-removal-control.log` SHA-256 `edc88600086f30afc7f0bc07ba39e576c1ff7259b4682a52996815b724513493`. Current author receipt `LOCAL/reviews/E11-current-witness-repair.json` SHA-256 `e27b1fa967344c93ce5b89bc42d6241922b0d0bb7d2674db39d999cdcce7cdcc` records B192/B194 as candidate paths and no formal closures.

No product source, tests, or Git state were changed by this reviewer; this note is the review artifact.

## Immutable component confirmation

Root-authored commit `24f3b72dd6eaa77cb7493d0880fe181e79181d75` has tree `421ee2bc4f24083777516c414975a7f899f91648` and parent `077a572ff5880b3f50a85d3e3db6a232d277659a`. Hashes computed from the commit's Git blobs confirm the implementation source, README, and release fragment exactly match the reviewed candidate. The committed test blob hash is `7350625f34df793b246f9b89ca2eb7993f76e0ef33546385dc99936ca9a1e818`, differing from the pre-commit reviewed test hash above; I reran the same focused 12 selectors against the committed bytes, with **12 passed** and the same two upstream warnings. The receipt `LOCAL/reviews/raw/welfare-immutable-commit-check.log` SHA-256 is `18fac177648faef188257c7bec68e13f7ff4fe3090d237fd671cb31bbe151579`. Ruff on the committed test path passed. `git diff --exit-code 24f3b72dd6eaa77cb7493d0880fe181e79181d75 -- <four reviewed paths>` is clean in the candidate worktree. This confirms this component only; the full-candidate freeze and backend wave remain pending.
