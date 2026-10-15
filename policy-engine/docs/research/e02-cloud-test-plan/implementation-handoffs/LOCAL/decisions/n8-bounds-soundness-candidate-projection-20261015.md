# N8 bounds soundness and candidate projection — decision packet

**Status:** proposed for independent G adjudication; no formal closure or source-semantic change is claimed.

## Decision requested

Decide whether the N8 value-owner route may expose a source-preserving, explicitly non-gating candidate bounds projection when the existing producer reports a non-null soundness tier, and what the projection must do with an absent tier and an unverified CERTIFIED declaration. Separately decide whether the exact N8 pair `EstimandSpec.estimand_id = ATE` and `BoundsBundle.estimand_type = ate` has a typed mapping in this route. No arbitrary identifier normalization is proposed.

The recommended bounded direction is an additive candidate-only projection that preserves the exact source tier, assumptions, certificate reference, bounds artifact reference, selected source profile references, and both estimand strings. It must not feed an authority-eligible uncertainty envelope. Until the estimand relationship is explicitly typed and checked, that relationship remains unresolved and the result cannot be represented as bounds for the requested estimand. Keep the current refusal on the authority-facing path.

## Ratified constraint and pattern pass

S0-K06 §4.3 states: “The candidate band may operate under unknown scope as a credal state with a declared unknown,” with unresolved scope carried forward as a typed limitation; silently substituting a concrete scope is the violation. The same application note binds fail-closed to the authority band and says the candidate band may continue only with the unknown declared. See `docs/system-design-decisions/stage0-custody-kernel-ratification.md:164-174` and the application in `docs/system-design-decisions/policyos-identity-and-custody-boundary.md:194-199`.

That ratification establishes a band split; it does not define how this numerical bounds artifact may be transformed or presented. In particular, it does not equate ASSUMPTION_ONLY or HEURISTIC with a valid estimand-specific interval. The candidate claim still needs a typed source basis and an honest limitation. A CERTIFIED label remains a source claim until its proof payload is resolved and verified.

Pattern pass: P05/P04/P10/P12 apply to authority and status; P01/P02/P03 apply to the incomplete candidate producer-to-consumer bridge; P37/P38 apply to the predicates and projection implementation. Current producer and persisted artifact exist, but the candidate bounds bridge is blocked by the broad soundness guard; the consuming candidate representation does not preserve the original method tiers and assumptions. The acceptance signal is a resolved-ref, content-bound candidate projection that preserves every source tier and limitation while every authority gate remains false, plus adversarial controls below.

## Observed source and property

The live E02 request is explicitly scoped as a candidate source projection and fixes its request identifier to ATE in `src/polisyos/runtime/quality/generation_cycle.py:16337-16380`. It runs the existing BoundsEngine and persists a strict BoundsBundle. The reader at `generation_cycle.py:17220-17250` requires a Manski result and then refuses the entire bundle if any method summary has a non-null soundness level. This blocks the actual N8 output rather than distinguishing its tiers.

The typed source vocabulary already distinguishes CERTIFIED, ASSUMPTION_ONLY, and HEURISTIC in `src/polisyos/ir/analytics/partial_identification.py:60-66`. The existing annotator assigns ASSUMPTION_ONLY to Manski and HEURISTIC to sharp-LP and relaxed-polynomial results (`src/polisyos/ir/analytics/certified_tightening.py:31-38`). A certified tightening path separately validates a certificate before attaching its certificate reference and CERTIFIED tier (`certified_tightening.py:189-207`). These distinctions must not be flattened into “has tier” or a single accepted/rejected boolean.

The downstream BoundsBundle converter at `partial_identification.py:348-384` documents a certified outer-bounds projection. It checks exact identifier equality, the native binding, and interval presence; gate eligibility is then derived from sharpness status. It does not inspect method-summary soundness tiers or resolve a certificate payload. A persisted outer_approx Manski bundle with ASSUMPTION_ONLY summaries can therefore be projected with gate_eligible=true if supplied the matching lowercase type. The current N8 reader guard blocks its own route before this converter; it does not make the converter’s property check sound for other callers. This is the P38 divergence: the intended property is “the projected interval is eligible for an authority gate only when its soundness basis is verified”; this converter currently turns on sharpness and identifier/binding matches, and the divergent case is ASSUMPTION_ONLY plus outer_approx.

The estimand strings are different semantic fields. Foundry’s `EstimandSpec.estimand_id` is part of the canonical estimand identity (`src/polisyos/foundry/methods/components/consensus.py:79-98`). Bounds artifacts expose `estimand_type`, whose default is lowercase ate (`partial_identification.py:150-163, 320-333`). The current request validates exact ID ATE; the actual bundle reports type ate. No typed mapping from the request’s arbitrary identity to the bundle’s operator/type is present in the inspected contract. Lowercasing the ID would silently turn identity into an operator-kind alias and could collapse distinct IDs. Preserve both strings and refuse the match until an explicit typed relation exists.

## Evidence and limits

The controlled AIPW source generated and persisted a real BoundsBundle through the existing producer. Its Manski and Imbens-Manski summaries both carry ASSUMPTION_ONLY and `no_assumptions_on_selection`; the bundle is `outer_approx`. The final focused test exercised the real method producer, persistence, reopen/fresh read, candidate output, seed-binding repair, and real_panel refusal under a RAW-only in-process substitution that removed just the current non-null-tier refusal. It passed 1 test in 134.891 seconds. This is a physical-chain prototype, not a product PASS, not production evidence, and not a finding that the current tier semantics permit projection.

Source and test at the prototype base are `generation_cycle.py@4d3181679789503bf8dd993f20cb9ac4e54139c0e778e4334adc0b15038907c1` and `test_value_gate.py@627dc34b631c49070f4d73fa5218f2b47310c6317a92de10179c4e4167f17d95`. The final run and static check manifest is `LOCAL/raw/resume-n8-soundness-candidate-prototype-20261015/post-seed-n8-candidate-prototype-verification.json@1d8cf25e239d153b28bfc6d54a11e97dd2cfd7b620145b939792df60d09a2def`. Deciding stdout is `LOCAL/raw/resume-n8-soundness-candidate-prototype-20261015/prototype-aipw-reader-r3-pytest.txt@423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d`; JUnit is `.../prototype-aipw-reader-r3-junit.xml@9f58097ff903b6b1050106db860a0b17ab784baba52ed7300527f1374f5a7c57`. Ruff, format, and scoped diff checks passed in the manifest. The earlier raw CAS diagnostic is `LOCAL/raw/resume-n8-soundness-candidate-prototype-20261015/cas-soundness-diagnostic.json@9f14209189a9aafd8211b4e01e22a5b3c6e5e1c2af12fdcd20b92a374e387a4f`; its manual lowercase substitution is diagnostic only, not a valid estimand mapping.

The fixture is controlled synthetic data. It establishes no production authority, assignment mechanism, calibration, unit conversion, source-time status, or currentness. Existing output retains `assignment_provenance=consumer_asserted` and `source_time_status=not_established`; those limitations must survive any candidate projection.

## Reuse-first options

1. **Reuse:** Keep the current refusal and the existing certified converter. This preserves the authority boundary but leaves the candidate value chain blocked for this actual non-null-tier output. It also leaves the converter’s tier/certificate predicate divergence unresolved if that method is called directly.

2. **Extend — recommended bounded candidate route:** Add a versioned candidate bounds projection to the existing N8 path. Resolve the persisted bundle and selected profiles by exact reference, verify bytes/profile identity, and preserve every method summary’s tier (including explicit absence), assumptions, certificate reference, numeric result, exact `estimand_id`, exact `estimand_type`, and request/profile/bounds refs. Mark the projection candidate-only and structurally non-gating; never call a converter that can set gate_eligible=true. Preserve the current protected refusal whenever a caller requests a gate-eligible or estimand-bound value without the necessary verifier/mapping. This follows the ratified candidate band only if G confirms that this evidence can be represented without adding a new scientific interpretation.

3. **Consolidate:** Unify the partial-identification, causal-report, and ValueOwner projection protocols behind a shared typed candidate-evidence contract. This may reduce duplicate conversion logic, but broadens migration and all consumer surfaces beyond the demonstrated N8 defect. Defer until the narrow extension is accepted and its whole consumer set is inventoried.

4. **Build new:** Create a new bounds/evidence subsystem or redefine soundness semantics. This duplicates the existing producer and artifact family and is not justified by current evidence. Do not proceed without a separate G decision.

## Required G choices and falsifiers

The narrow candidate DTO behavior needs explicit disposition for these inputs:

- **ASSUMPTION_ONLY:** Preserve the exact tier and every assumption (including `no_assumptions_on_selection`); demonstrate useful candidate output with the gate still false.
- **HEURISTIC:** Preserve the heuristic tier and provenance; do not relabel it as assumption-only or certified, and keep all gates false.
- **Missing tier:** Do not invent a default. Either carry an explicit unknown tier as a typed limitation in candidate output or refuse that projection; the choice must be explicit and tested.
- **CERTIFIED without a resolvable verified payload:** Do not emit a verified/certified claim. Either keep the source declaration only as explicitly unverified candidate evidence with gates false, or refuse it. A marker/reference alone is not proof.
- **Wrong estimand:** Same numeric interval with a different arbitrary estimand identity/type must refuse binding. If G approves an ATE operator mapping, encode the exact typed mapping and preserve both identifiers; do not lowercase or uppercase arbitrary IDs.

For P37, a candidate projection may record producer-emitted tiers and assumptions only after exact persisted bytes are reread and bound to their refs; it may not use those labels as an authority predicate. Certificate verification and estimand binding must be recomputed or independently reconciled before any authority use. For P38, delete the tier/certificate check while retaining DTO fields and prove that no gate becomes green. Also mutate each source tier, remove an assumption, remove/replace the certificate payload, alter the profile ref, and substitute a different estimand while keeping shape/markers intact; the candidate projection must either preserve the changed fact as a limitation or refuse, and an authority consumer must remain blocked.

## Proposed implementation boundary if accepted

Minimum additive mechanism: `src/polisyos/runtime/quality/generation_cycle.py` plus `tests/unit/runtime/quality/test_value_gate.py`. Add the narrowest versioned source-basis DTO/field that preserves the already available tier, assumption, certificate and reference data; do not rename historical artifact kinds or change existing authority-gate semantics. If the decision also changes the generic BoundsBundle converter, include `src/polisyos/ir/analytics/partial_identification.py` and its mirrored IR analytics tests as a separate, explicitly reviewed companion rather than silently widening the N8 patch.

Migration is additive. Existing persisted BoundsBundle and ValueOuterSet bytes remain immutable. Legacy/history reads remain explicitly profileless or limited where they lack this basis; no tier is inferred from method names or recreated during read. Until the typed estimand mapping and any required certificate verification exist, a request/result mismatch remains a typed limitation/refusal and the current authority path stays protected.

No source change is requested by this packet. The candidate-only extension, if accepted, needs a source lease, source freeze, independent review, actual producer→CAS→fresh-reader replay, the five falsifiers above, and a removal probe before any closeout proposal.
