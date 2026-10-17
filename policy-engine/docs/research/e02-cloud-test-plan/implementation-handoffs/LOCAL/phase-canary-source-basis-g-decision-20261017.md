# Replay continuity source-basis boundary: engineering/G choice packet

Status: research and implementation choice for independent G review. This is not an acceptance, authority grant, or formal finding closure. No tracked source was changed and no pytest/composed canary run was performed in this packet.

## Question and evidence

The property under review is: a diagnostic projection or continuity artifact produced by one canary pass must not become an independent source basis in a later pass, copy, or reload. The current continuity builder also has a separate boundary question: what evidence qualifies as a source ref, versus a candidate mapping that merely contains a ref-shaped string?

`build_nl_replay_orchestration_continuity` accepts nine `Mapping` surfaces and recursively collects ref-shaped values into one combined set. The resulting record labels itself `diagnostic_only` and explicitly disallows producer truth, scorecard/approval/closeout authority, public-projection authority, and evidence-strength use. It has no resolver, artifact store, verifier, or provenance argument. Thus its `status` is a continuity diagnostic; it is not itself an authority-grade gate.

The canary has existing source-resolution components, but none is a verified continuity source basis:

- `RuntimeQualityAuthorityRefs.from_sources` states that its refs are diagnostic candidates and that the method does not select or verify content, profile, issuer, or currentness. `resolve_quality_refs` also discovers string refs and requires callers to apply role-specific verification.
- `RuntimeQualityAuthorityRefs.from_runtime_payloads` filters to job/run-owned locations and can parse explicit typed `ArtifactRefModel` values, but parsing validates the reference shape, not the referenced bytes, producer identity, signature, or currentness.
- `_quality_reports_from_refs_with_authority` loads generic report JSON from the store. It performs special kind/media/schema manifest validation for the security report; there is no corresponding generic producer/verifier check for every continuity ref family.
- `_artifact_store_from_context` accepts an injected store or creates `FileSystemCAS`; this path does not compose a `SignatureVerifyingArtifactStore` verifier. The optional signed-store protocol exists elsewhere, but is not wired into this canary source path.
- `build_canary_evidence_handoff_ledger` and `_carrier_ref_from_quality_evidence` select/read refs from mappings or caller command metadata and can fall back to `evidence-spine:bundle-carrier-unavailable`; these are diagnostic lineage inputs, not verifier-provenance.
- The continuity builder’s carrier, claim-registry, producer-binding, and spine refs therefore remain caller/producer-asserted diagnostic observations unless an independent owner verifies them.

The R4 candidate does introduce a distinct local `generated_candidate_projection_surfaces` map and keeps the generated public bundle out of `quality_evidence_payload` while still giving audit/export readers access. That is the right owner-plane direction for locally emitted output. However, R4 freezes `continuity_source_quality_evidence` late: after generation of public export/SLO, the first scorecard, scenario graph, and a handoff ledger. Those locally derived artifacts are included in the nominal source snapshot. R4 therefore does not yet prove a pre-output source basis across the complete producer set.

The marker-removal reproduction is the P38 falsifier for classification by visible shape: under an arbitrary nested key, removing `schema_version` and `record_family` still lets the bare map contribute `carrier_ref=evidence-spine:source` and `runtime_claim_registry_ref=quality_evidence/source-registry.json`; no typed malformed-record issue is emitted. The overall record remains `fail` because other ref families are missing. This demonstrates that schema/family detection cannot establish the origin of the same bare ref map. Adding another key marker would repeat the P40 ladder and would not establish content binding or producer provenance.

## P37/P38 boundary

- Property: output-derived diagnostic refs cannot seed a later source basis; source and endpoint observations remain separate across every canary pass and reload.
- Current stand-in: recursive mapping-key/schema/role-marker recognition plus a union of mapping contents.
- Divergent case: a markerless bare map at an arbitrary nested key is structurally indistinguishable from an ordinary mapping carrying diagnostic source refs.
- P37: the ref origin/purpose for an arbitrary bare map is `consumer_asserted` or `not_established`. Do not promote the continuity record or its refs into an authority gate. Authority-grade use must fail closed without actual resolve + content binding + verifier-provenance.
- External malformed input under the known continuity slot or a recognized typed record remains a present malformed input and must yield a typed refusal; do not convert it to absence/default. For markerless arbitrary maps, current source cannot establish that the map is a malformed continuity record. Keep that as an explicit bounded diagnostic residual rather than claiming complete external-source classification.

## Narrow implementation proposal and bounded G choices

Preferred: extend the existing diagnostic bridge with explicit source and observation planes, reusing current producer and persistence owners. At canary entry, freeze the selected caller/loaded input surfaces as `consumer_asserted` diagnostic candidates before any canary-local generated report; keep that snapshot immutable for both continuity passes. This does not admit the inputs as authority. Treat locally generated bundle/inspection/readiness/public-export/handoff/continuity outputs as observations or audit outputs, never as additions to the source basis. Compare their refs against the frozen source refs and report divergence. Keep the existing public export file/API shape. Keep the continuity status diagnostic-only; no positive authority or public-currentness claim follows from consistency. Do not add an origin token or claim the input maps were independently verified. This routine source/output wiring is authorized to continue without waiting for G. A G choice is needed only for an observable public schema/status-meaning change or a new authenticated source-basis capability.

Alternatives:

1. Reuse the existing nine-argument union unchanged and narrow its documented purpose to “observed ref propagation.” This preserves all current callers and status behavior but gives up the distinct source-vs-endpoint reconciliation claim; it cannot assert that an export-only ref was independently source-backed.
2. Extend the shared API with explicit `source_surfaces` and `observation_surfaces` (or an equivalent typed in-memory partition), then migrate the canary producer and the two existing G6/G7 producer callers. This makes the boundary observable and supports removal tests. It changes the meaning of which refs satisfy the source basis and may require a schema/versioned report contract decision if serialized coverage changes.
3. Build a reusable source-basis artifact that binds refs to content, producer identity, verification method, profile, and relevant time, and wire a signature-verifying owner into the canary. This is the only route to an authority-grade provenance claim, but it is a larger new capability and needs its own owner, issuer/verifier inputs, migration, and G decision. Do not simulate it with a self-authored token, manifest field, or hash alone.

## Impact and migration boundary

The shared builder has production call sites in `tools/ops_runners/runtime/canary_evidence.py` (two passes), `runtime/quality/proving_ground/bounded_request_agent.py` (G6), and `runtime/quality/proving_ground/region_widening.py` (G7), plus its direct unit tests. The current G6/G7 producers construct and repeat their own typed record refs across surfaces; they are not evidence that canary mappings have external signatures. Any explicit plane extension must preserve these callers’ current diagnostic behavior or migrate them together with tests.

A routine source/output separation can retain the current JSON artifact path and public bundle schema, but changing the serialized meaning of “required source surfaces” is observable contract semantics and should be versioned if consumers rely on the current union. The runtime-quality owner owns the shared builder; the canary runner owns the source snapshot and output-plane wiring; G decides any public schema/status-semantic change. No institutional issuer or verifier is presently supplied by the inspected path. Time estimate: a narrow diagnostic partition and canary bridge is a bounded engineering change (roughly 1–2 focused days including caller/test migration); actual signature/currentness authority requires a separately scoped design and an identified verifier/issuer owner, so it cannot be honestly time-boxed until those inputs are named.

## Prototype and falsifier

Existing prototype/falsifier output: `phase-barrier-systemic-canary-projection-separation-r1-20261017/r5-continuity-marker-removal-20261017/r4-marker-removal-reproduction.json` (path and SHA are pinned in the manifest). It proves that another marker predicate cannot close the full property. It is not an actual canary replay receipt.

Required falsifier for the preferred choice, before any bounded closure proposal: instrument the real canary path and show (1) its source payload/ref snapshot is captured before any canary-local scorecard, scenario graph, handoff ledger, SLO, export, or continuity output is produced; (2) both continuity passes read the same frozen source snapshot; (3) generated candidate export and continuity outputs remain persisted and visible at the existing audit/public output path; (4) no generated candidate-derived object re-enters any ref admission, source-basis builder, scorecard authority input, or next replay basis after deep copy and fresh reload; (5) removing the source-plane separation while keeping labels makes the actual export-only ref appear as a source ref or changes the bridge decision; and (6) malformed present records still yield typed refusals. Separately demonstrate that raw markerless maps remain non-authoritative and cannot satisfy any authority predicate. A passing diagnostic continuity status alone does not establish this.

## Source frame and exact pins

Read-only frame at packet authoring: branch `codex/e02-unified-local-20261009`, HEAD `25595f3fff3265d3002bee87046e3c685b3f800b`, tree `4f7dd39f235906fdabefc935fc96052d2a569a8c`, parent `736104d0144b75272c06f34e6eb185545ece1fed`; worktree had unrelated parent-owned dirty/untracked files. No Git mutation was made.

Relevant source pins:

- `policy-engine/src/polisyos/runtime/quality/refs.py` @ `acaf117c965f09ddf7ce577c90d5a08991f95a928e753843545b7e15fc87ce79`
- `policy-engine/tools/ops_runners/runtime/canary_evidence.py` @ `ca2b03fae39e830ad1d8acbe69e581dde0383cfbfece9c3eaf44d6ee2d466673`
- `policy-engine/src/polisyos/runtime/quality/nl_replay_orchestration.py` @ `2c7732f3b92519e5c0314f33b2a5203ec07e8ecffdb81536c8f8c6118087ece3`
- `policy-engine/src/polisyos/runtime/quality/evidence_spine_handoff.py` @ `10716fd5631c21b8bc6404a717a59c21192f16c6fccd4c13e25e6cb24d04e90a`
- `policy-engine/src/polisyos/runtime/quality/claim_registry.py` @ `a2f45ff090d7c0d954743cc2312f734325a85f64fc43516a20ea367e28daf512`
- `policy-engine/src/polisyos/runtime/quality/public_export.py` @ `1dc9c7e4518a58b307e29fb026e4b214f0ff4ec8465351dbd4c181b88fbf5c0d`
- `policy-engine/src/polisyos/ir/registry/refs.py` @ `bbac14368f7091bf8135f621999e9b702d711c31a95e87e7ceaa1bd963c8fe72`
- `policy-engine/src/polisyos/core/artifacts/protocol.py` @ `f70de7350c66639403fffc7bb28998184f00f0b6fc95a3e6e16a86ee4f6c969e`
- `policy-engine/src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py` @ `0675e4d0398c532e744af931816cbfcb91fb41b06cacd6af2eff8d3605cd82d1`
- `policy-engine/src/polisyos/runtime/quality/proving_ground/region_widening.py` @ `02eff4feb5d4d60fa4a16a3f3ccdc0dc6843e8c5e110497ab61d331da2b75bcd`
- Prior R4 candidate source manifest @ `d4ee3f28cd5c7a862c34dc9ea970d40c07e7503440d240e19d84a9395b7e3dfa`; its candidate source patch and target preimages are listed there. R4 is author research only, not accepted or tested in pytest.

Formal closures/proposals: none from this author packet. Routine source-vs-observation wiring for `build_nl_replay_orchestration_continuity` may proceed under diagnostic-candidate semantics. Bounded residual: external arbitrary markerless ref maps remain diagnostic candidates with purpose `consumer_asserted`/`not_established`, fail-closed for authority. G adjudication remains necessary for an observable public schema/status-meaning change or a new authenticated source-basis capability; independent G code acceptance remains separate.
