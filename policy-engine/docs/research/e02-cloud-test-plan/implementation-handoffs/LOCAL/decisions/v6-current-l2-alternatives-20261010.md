# V6 current-L2 alternative research — 2026-10-10

## Finding

The exact named L01/L02 custody inputs and the selected local academic source descriptor do not provide an admissible current L2 reference or an already-versioned replacement. The selected N4 source is tied to the registered historical snapshot `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`. The current guard resolves that digest to `confidence_reproducibility=not_reproducible_under_current_rule` and `consumer_action=withhold_confidence_forwarding`; the actual typed `build_credal_reference` probe therefore refuses before N4 creates a candidate or child. This is the correct outcome for the evidence available.

No alternate source was tested by changing bytes, editing metadata, or querying a production database. The conclusion is deliberately bounded to the named locators and configured descriptor below; it does not assert that no other source exists elsewhere.

## Read anchor and evidence

This read used candidate `HEAD c4563fd4da93bf9cc06de3dc77554a8a0d117359`. The examined academic and N4 source files were clean at that anchor and are pinned by their SHA-256 values below. The shared checkout contains other writers’ pending work; I changed no source or test file and ran no tests, producer, server, or database query.

`INPUTS.json` (`b000d61906fc0d732287f1a50cbb1ca902c23f4d08a292e4330734f5147431da`) declares two private custody roots: one for exact ignored locators with production read-only scope, and one for source-qualified authentic inputs with an explicit instruction not to infer currentness. The paired locator convention is documented in `LOCAL/t1-t2-intake/README.md@6498b18d74a62a07dfb7b8398b5cfdc7963b41139a36f8f900ce684e76d4b7f1`.

The selected-run diagnosis, `LOCAL/decisions/v6-actual-derived-lineage-diagnosis.md@3c7325298653f769473637c4c8d5fda428aff77c4c540b3e037c625e0e3d5f43`, records the typed root and context reads. The N4 result is `generation_unavailable`, with zero candidates and zero model calls; its lever-space result carries `credal_reference_unavailable:ValueError`, and the prewarm guard returns `cg1_index_prewarm_reference_unavailable`. The context is `candidate_limited`, has `profile_admission_status=not_established`, and leaves S8 blocked. The vintage record also says `claim_evidence_axis=absent`; its stored outcomes describe retained memberships, not a complete data-pass replay, paper truth, or the generating rule. The diagnostic records that disabling prewarm does not produce a generated result: the same guarded credal-reference construction is attempted again. Thus the observed zero-child outcome precedes child lineage and is not evidence of a fresh-reader defect.

The exact private receipts that bear on this question are:

| Named receipt | SHA-256 | What it establishes |
| --- | --- | --- |
| `L01::parallel-20261008-l01/packets/B.json` | `b2ea97c8e1e9001e33e5c96a15208809d283117d429b0bc97d2a41c256c41ac5` | B13 is a read-only factual draft. Production input admission is `not_established`; the input-byte digest is withheld. Its minimum still includes an exact matching source/profile, manifest or legitimate versioned replacement, and source/context/run/time references. |
| `L01::restart-20261008-bindings/packets/A-l6.json` | `c6ab16fa192483dbfaccca6b634e79129709e6d2ba6f7b05d9e152090a3bf61f` | The packet is specifically L6 intervention-substrate and observation routing, not L2. The `research` profile is described as an owner default, not an admitted served profile. Root-to-bundle binding passes, but two of the three selected L6 members fail size/checksum comparison. |
| `L01::restart-20261008-bindings/evidence/binding-readback.json` | `d3c8e15fa6a76e93703db0e38e837c7c1b5597674e0716943de04a29f7025e43` | Confirms the same three-member L6 comparison; its notes say finding outcomes were not updated by those checks. |
| `L01::restart-20261008-bindings/source.json` | `5092071cf08f36358a3eb00b77e3169ea5dbf47a02e4141fcca5bf75baf38d38` | Source-composition receipt says no accepted composition or runtime execution is inferred. It is not an L2 custody approval. |
| `L02::manifest.json` | `c8b83ebe68bbd3568d9bceb7626863c3acb5616ab2c717bf2a3d13130b0cc769` | L02 delivery/source provenance only; its declared source candidate is the earlier L01 candidate, not a new L2 artifact. |
| `L02::prepared/l02_late_input_independent_review.json` | `8f06c226e12132c91b836507d014cbc161f53f998054817edabdee20d941c347` | Corrects an overclaim: L01 supplies factual navigation and bounded observations, while matching input/profile/owner/API/law/evaluator tuples remain `not_established`. |
| `L02::prepared/l02_input_packets.json` | `a6104430660f645c96d0308a5ab5dbae21695cf78400e5bec4fbd607d859907f` | The V6 row requires a V1 authentic profile, actual served simulation producer, independent sibling failure, and persisted success/history/CAS/error refs. It records the V1 profile as absent. |

The named L01 root manifest (`b893eb0590cf151afd89ed0cb0c288fddf09a93f3e36305679e33aaeb55dd6c3`) declares default runtime profile `research`, observed on 2026-10-08, and an academic bundle version `policyos_academic_runtime_slim_20260411T112032Z`. Its nominated academic assembly manifest (`8cd13c17297054d5686222a02b8f1682c452c921518c0d238084cf3f1b64d4f2`) was generated on 2026-04-11. The manifest contains an `academic/graph/scholar_knowledge.duckdb` entry marked `assembled`, but that entry has no content hash or size; the root descriptor’s recorded checksum is for the assembly manifest itself. The selected academic DB therefore cannot be joined by bytes to the selected N4 L2 digest from these receipts, much less established as current under a served profile. The manifest’s dates identify its recorded build/observation times, not a freshness or authority rule.

The L01 alias index (`db427943dfd71c99ad1bf405f24a145b8769eb04f91a0de0f2bc0ddf40bd49b2`) only exposes a configured Lex database/version and the L6 bundle manifest. The Lex aliases are not an academic SKG/L2 source. The local L6 bundle manifest (`e357236d05c1924ff20de5586e37c9b609e0a97dbb5f24653b743b7cc95ac828`) is correspondingly not a current L2 replacement.

## Existing paths and alternatives

The existing academic path offers a useful producer to reuse if its real inputs and source authority are supplied, but it does not itself make a new file hash current:

- `graph_builder.py` builds edge confidence from current `evidence_samples` through `aggregate_edge_confidence`, an evidence-weighted noisy-OR aggregate. This is a real candidate-producing mechanism, not a source-owner currentness artifact. A re-run must bind its actual admitted evidence population, profile, rule/version, and time before its output can be forwarded as current L2.
- `SKGVersionManager.check_retractions` uses a remaining-reference approximation (`base_confidence - 0.05`) before reaggregation. That maintenance operation is not a complete confidence data-pass replay and cannot replace the historical snapshot on its own.
- `best_snapshot._assemble_duckdb` calls `require_forwardable_confidence` on its original and remap inputs before assembling. This prevents republishing the registered historical bytes through that route; a passing check on an unregistered hash is still not proof of currentness.
- The full-file-SHA guard in `skg_versioning.py` refuses the known historical digest. Its function contract explicitly says that unknown hashes have no known restriction, not that they are current. A copy, rewrite, or otherwise different digest cannot be used as a positive currentness witness.

The existing candidate-only proposal route is an honest fallback but a different artifact contract. The diagnosis records a `N4CandidateScenarioSourceRecordV1` with a K-ref limitation, `l2_confidence_forwarded=false`, no credal-reference payload, S8 blocked, and N9 not admitted. Its candidate atom is `candidate_unverified`; it is not `GenerationUnderAResult(status="generated")`, and the existing child derivation function therefore cannot use it to satisfy V6’s two-child witness.

The practical choices are:

1. **Reuse an existing source only if its custodian can bind it.** Supply one already-existing L2 database reference plus its versioned manifest, actual DB content hash, selected profile/purpose, producer and rule versions, effective time/currentness policy, and source-owner or issuer provenance. No such positive reference is present in the named inputs.
2. **Extend the existing academic producer/reader if no accepted positive artifact exists.** Run the current graph-building path only on an admitted, source-owned evidence population; emit a content-bound L2 result with the exact rule/data-pass lineage and typed source/profile/time bindings; make the reader recompute or independently reconcile those fields. Do not merely add a new SHA to the historical registry or infer authority from `confidence_layer_vintage(...) is None`.
3. **Build a new producer only if the owner proves the existing path cannot emit that artifact.** The present inputs do not justify a parallel L2 engine or a new confidence law.

## Smallest discriminator and next G input

The smallest next input is an owner-supplied exact reference to an already-versioned current L2 source, or an explicit choice to make a current, source-owned build through the existing academic producer. For the former, the reference must bind the actual DB bytes, source population, producer/rule version, intended profile/purpose, effective time and currentness basis, and custodian/issuer provenance. For the latter, the same facts must be produced by the real data pass and retained with its output. A manifest lacking the database’s content digest, or a declaration that merely repeats a status, is insufficient.

Once that input exists, the minimal falsifier is to resolve and content-bind it through the existing SKG source API under the selected profile, then replay the existing forwardability guard and root N4 producer. The historical digest must remain refused; a deliberately changed/hash-only copy with no source or rule lineage must remain `not_established`; only a source-bound current output may proceed. The positive V6 check then has to observe two semantically distinct root-derived child problems, persist their typed source/history/CAS refs, and read them through the fresh served consumer, including the sibling-failure control. No such positive replay was run here because its required source input is absent.

G’s decision is whether a named custodian can nominate a current L2 source/profile or whether the selected N4 path remains limited until the existing producer can create and prove one. Authority/currentness, source identity, and the profile match are `not_established`; the recorded bundle metadata is `owner_supplied`; historical byte binding is `recomputed`. No authority-grade gate should treat the missing positive as zero confidence or accept an unregistered hash as current.

## Classification

P40: **SAME_CLASS_DEEPER** within the original root N4 → actual children → persisted source → fresh reader property. The deeper blocker is the source/currentness prerequisite for a root result that can create children, not a new child-lineage class. Stop patching prewarm settings or adding per-instance lineage exceptions. The property needs a full selected current L2 input and its admitted authority/time/profile basis.

Relevant patterns are P05 (authority and currentness), P01/P02 (real producer and bridge), P37/P38 (the guard’s predicate is a known-hash refusal, not a currentness proof), and P40 (widen to the source/basis quantity). Within the named locators, the positive current L2 artifact is `artifact_missing`; the authentic generated two-child bridge and semantic test are `bridge_missing` / `semantic_test_missing`. This is a bounded finding about the inspected inputs, not a global absence claim.

### Source fingerprints

- `src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py` — `ce4133e49d93ac785083d853ca3c1c7b09cf18ed7d95d1c6caa16d29446cfd59`
- `src/polisyos/data_forge/domains/academic/knowledge/skg_store.py` — `d10fe6a8388036f898cd44205c11b9a8961428c8559ba7ac0e64a1b0efccc5c5`
- `src/polisyos/data_forge/domains/academic/batch/graph_builder.py` — `0d1b79b2dc45d3d97dbb7f2414be69ecae534a1212dfdaa917b21b9a272b996d`
- `src/polisyos/data_forge/domains/academic/batch/best_snapshot.py` — `2d45e808711c42254cf8da0e3d67df1a9b53c9f6c931f2aa6a7c2b68b3e05140`
- `src/polisyos/runtime/quality/design_generation.py` — `3cea32f0016aaccf22cb2aba2216b6ee0aefe777abc6e50548eb063a3bc84411`
- `src/polisyos/runtime/quality/credal_reference.py` — `dd18ed8daace58aac9d7e242ecb0699ae3f956a4c1c89fdc057909751afb8459`
- `src/polisyos/runtime/quality/generation_source.py` — `8b399470e10afe538b87f8616b64bbf2bc512327f83c7c4483478f23c233c6bd`
- `src/polisyos/data_forge/domains/academic/knowledge/README.md` — `846e7526c2cb87e003a3deeb53a0cdefd7172e7e3ac46278f140b23140850dcd`
