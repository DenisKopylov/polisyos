# BERL persisted-law admission — G packet

**Disposition:** the existing BERL validation owner now has one shared law-profile admission gate, and both persisted Phase-5 and warrant-reliability consumers use it. This closes the reader-side admission escape only. It does not admit a conditional law, change the bundle schema, or change LA-036's finding disposition.

## Criterion and observed escape

The bound source is LA-036, “BERL: разные method IDs всё ещё обозначают один fallback-вычислитель,” in the immutable `LA_r09_original.md` at source commit `198076863e143dea9f89f02734b13d50dae3eed5`, lines 2103–2145, SHA-256 `ebc61d92552c6dfbf538aed17c8a7ed476ee4322fc9df09f7ed3b89e8c530a2a`. It requires method identity and execution semantics to agree and says a conditional name cannot create a conditional algorithm. The existing producer repair already refuses the conditional KernelSHAP request because no verified observed-feature joint-law resolver exists; see [`s1-law-intakes/decision.md`](../s1-law-intakes/decision.md), especially its LA-036 execution and `producer_missing` statements.

The independent review reproduced the next-level escape at candidate parent `cf949d4a10869d0f992d111cbf1f35fa89a84b30`: the persisted `validate_explanation_bundle` path admitted a bundle carrying `kernel_shap_conditional` and `conditional_observational`, and the actual Phase-5 and reliability consumers accepted it. The public `FeatureDependencePolicy.primary` is a free string; method assumptions are an open JSON object. A parseable field or self-reference therefore was not proof that a conditional law had been resolved.

## Shared invariant and boundary

`validation_rules.py` now checks the raw law profile before parsing and applies the same invariant to typed bundles. `conditional_observational` is refused with `conditional_feature_law_unverified`; unknown and malformed supplied primary, alternatives, and method profiles carry stable typed violations; supplied method-level profiles must match the bundle profile. A CAS-looking string, method ID, profile assertion, or any other self-declaration does not establish a verified law. The method ID is not an authority source and is not maintained as an alias denylist.

The persisted Phase-5 intake and warrant-reliability intake both call this shared validator. They preserve its refusal in their existing result channels: Phase-5 becomes blocked with the validator's violation, while reliability returns a failed threshold decision and BERL issue carrying the same typed reason. `marginal` and `marginal_interventional` still pass their existing bounded contract. No producer files, resolver, verifier, schema version, or historical artifact bytes were changed.

The complete AST walk is retained in [`consumer-census.txt`](validation/consumer-census.txt), with its [reproducible script](validation/consumer_census.py). It walked all **2,707 Python files** under `src/polisyos`; the full target row set has seven call/definition rows, and the complete persisted-helper call-site denominator is **two**: Phase-5 and warrant reliability. The BERL service producer and validator-internal typed/summary calls are listed separately rather than counted as persisted consumers.

## Property and predicate audit

- **Property:** an explanation bundle with conditional feature semantics cannot be admitted as bounded analyst-facing evidence unless its observed-feature law is resolved and verified from an authoritative, content-bound source.
- **Old divergent case:** metrics and schema parsing could pass a forged conditional bundle with a self-attested CAS reference at both persisted consumers.
- **Current implementation:** it tests the declared profile and cross-field consistency, then refuses conditional, unknown, and malformed declarations because no law resolver exists. It does not claim to verify a future conditional law.
- **P37 predicates:** the persisted primary profile and any method profile are `consumer_asserted`; comparing supplied method and bundle profiles is `recomputed`; the existence of a verified conditional law is `not_established`. The gate therefore returns no conditional positive.
- **P38 bounded divergence:** if a correctly source-bound conditional law is introduced later, this implementation still refuses it. The smallest missing capability is a producer-owned law artifact plus a source/content-binding resolver and existing verifier provenance at the consumer. Until then that false-negative boundary is an explicit limitation, not a claim of conditional support.
- **P40:** same LA-036 law-label-versus-execution/evidence class one level deeper, not a new class. After the producer refused unsupported conditional execution, two persisted readers still trusted the same declaration. The fix widens the existing shared validation mechanism across the complete consumer denominator rather than adding a per-consumer alias patch. The remaining law-production gap is a capability residual, not another code patch in the reader.

Relevant register patterns: P05/P10/P15 (candidate metadata cannot carry authority), P29/P31/P32/P33 (exercise the real consumer and test the property, not markers or references), P35/P36 (complete denominator and source-bound finding), P37/P38 (predicate provenance and divergent case), and P40 (same-class widening). The acceptance signal is: actual Phase-5 and reliability consumers block a forged conditional bundle and preserve `conditional_feature_law_unverified`; malformed/unknown/mismatched profile variants fail with typed reasons; an existing marginal/interventional positive remains pass; removing the shared law predicate makes both forged rows pass in the isolated property-removal probe.

## G options — no selection made

1. **Keep conditional semantics unsupported.** Retain the current typed refusal and publish no conditional attribution. This is today's behavior and has the smallest operational surface. It remains the safe path if no upstream law producer is admitted.
2. **Admit a source-bound Gaussian joint law.** Define and persist the fitted mean/covariance (or conditional parameters), ordered observed-feature axes, population/source identity, fit procedure/version, observation time, support policy, and a verifier result. The consumer must resolve the exact source and content-bind the fit before making the conditional expectation. Singular or poorly calibrated fits need an explicit refusal/degradation rule.
3. **Admit an exact finite empirical conditional law.** Bind ordered source rows, conditioning strata, weights, support, population/time, feature schema and source digest; compute expectations only over the resolved support. Empty or inadequate support must remain unknown/refused. This is transparent and may be narrow, but can be sparse and does not imply a general conditional sampler.
4. **Admit a richer fitted conditional sampler.** Use a source-bound model and held-out conditional-distribution conformance evidence with explicit error/support guarantees. This covers more distributions but requires a larger verifier and error contract; a model name or training report alone is not evidence.

These are different scientific choices about the observed-feature conditional law. No choice, estimator, threshold, status transition, or G closure is made here. Any selected path must specify the conditional estimand and a distinguishing correlated-feature case; it must preserve explicit `marginal` and `marginal_interventional` behavior.

## Migration and falsifier

Historical conditional bundles are not rewritten or relabeled. When Phase-5 or warrant reliability revalidates one, it becomes diagnostic/refused with the typed law reason. A historical bundle may be regenerated under a supported marginal profile only when that matches the computation that actually produced its attribution. Unknown/malformed profiles are not defaulted, and no profileless-history compatibility law is introduced.

The focused consumer tests and complete output are in [`validation/focused-final.txt`](validation/focused-final.txt): **47 passed**, with two upstream PyTorch/Python 3.14 `torch.jit.script` deprecation warnings. Ruff lint, release-fragment TOML parsing, and the changed-path `git diff --check` pass. The isolated [`property_removal_probe.py`](validation/property_removal_probe.py) monkeypatches the central predicate only in a separate process and confirms both actual consumer intakes pass the forged `kernel_shap_conditional` bundle when that property is removed; complete output: [`property-removal.txt`](validation/property-removal.txt). This verifies that the negatives depend on the semantic law gate, not merely profile markers or test setup.

The scoped [mypy output](validation/mypy-final.txt) has no BERL validator/reliability errors after typing the existing threshold conversion, but reports three unchanged Phase-5 diagnostics at lines 307, 309 and 878: the current Core `ArtifactStore`/`InputRef` types do not satisfy the IR artifact-store protocol, and one existing `type: ignore` is unused. The full-tree [`git diff --check` output](validation/worktree-diff-check.txt) also reports four whitespace findings outside this exact footprint in `runtime/http/services/control/generation_cycle.py`, `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py`, and `tests/unit/scientist/methods/backtesting/test_backtesting.py`; the scoped changed-path check is clean. Ruff's format-diff still lists four style deltas whose same hunks are present at HEAD, as demonstrated by the [baseline probe](validation/format-baseline.txt); I left those existing hunks untouched rather than reformatting unrelated lines.

## Scope and capability status

Changed product paths:

- `src/polisyos/berl/contracts/validation_rules.py`
- `src/polisyos/scientist/validation/phase5_preflight.py`
- `src/polisyos/runtime/quality/explanation_reliability.py`
- `tests/unit/berl/test_contracts.py`
- `tests/integration/scientist_berl/test_explanation_reliability_bridge.py`
- `tests/unit/scientist/validation/test_phase5_preflight.py`
- `tests/unit/runtime/quality/test_berl_warrant_reliability.py`
- `src/polisyos/berl/README.md`
- `release-fragments/unreleased/2026-10-09-e02-berl-persisted-law-admission.toml`

The remaining `LOCAL/berl-persisted-law/` files are the G packet and retained probes/logs, not product mechanism paths. Full conditional-law capability remains `producer_missing` and `bridge_missing`; persisted reader protection is implemented and behaviorally verified, while a verified conditional law source/resolver remains for G to choose and fund. No test or document claims LA-036 is closed now, and the existing planning `closure_now` field remains untouched.
