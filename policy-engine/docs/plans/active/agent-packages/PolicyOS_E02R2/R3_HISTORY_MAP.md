# R3 historical promotion receipt map

Status: read-only serializer and corpus analysis. No source edits, fixture edits, reissues, or tests were performed for this map. R3 implementation remains gated on the baseline freeze and its write lease.

## Finding and serialization path

The property is byte-exact historical replay: a signed or hashed promotion receipt remains structurally verifiable under the serializer that produced it, while historical validity does not confer current authority. The current implementation violates that property when an old owner projection is parsed through the current `CandidateSummary` and then re-dumped.

The path is:

1. `CandidateSummary` is currently declared in `runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:904-944`.
2. `CanonicalPromotionOwnerProjection` embeds that current type at `runtime/quality/promotion_sequence.py@dc8beab981b714e80e54bef22ba83bc66ab3ffd4:1963-1971`; its `_projection_hash_is_content_bound` re-dumps the model and computes the owner hash at `:2003-2008`. The legacy owner projection v1 does the same through the current summary type at `:1903-1910,1943-1949`.
3. V5 and v6 receipt classes subclass the current `CanonicalPromotionReceipt` and do not override its owner-projection type (`promotion_sequence.py:2011-2017,2148-2161`). The supported v4 reader is `_LegacyCanonicalPromotionReceiptV4` (`:2164-2171`), which selects owner projection v2 (`:1953-1960`); its dedicated semantic projection helper uses that owner model (`:2554-2571`). The parser dispatches v4/v5/v6 at `:2228-2253`. All these owner models currently embed the mutable `CandidateSummary` type.
4. The v4/v5/v6 semantic projection helpers parse and then call `receipt.model_dump(mode="json")` before projecting (`promotion_sequence.py:2554-2611`). Thus their historical comparison projections also inherit the current nested summary shape. The v4 class and helper preserve a distinct schema boundary, but no tracked v4 fixture authenticates its complete serialized shape; v4 byte-exact corpus replay is `UNRUN`.
5. `gy_content_hash` canonicalizes with sorted keys (`pdc/_impl/gy_waist.py@def61a737aa88f06cc3a9856df3c9c3b8b6f9bdc:630-639`). The new keys change the hash input; their order does not. `model_dump_json()` preserves model field order, so the same additions also change the compressed-v5 byte round-trip.

The current schema constants are promotion v7 and owner projection v3 (`promotion_sequence.py:161-166`). The v7 schema was introduced by `4f54c80cc` on Sep 8, before the later `CandidateSummary` additions. `grounding_issue_codes` and `grounding_report_ref` arrived in `875231a8` and `source_content_hash` in `0c65c8122`, both Sep 22, without a promotion schema bump. Existing `grounding_source` and `grounding_disposition` are part of the old profile and must not be dropped.

## Frozen nested summary profiles

`p0`, `p1`, and `p2` name nested `CandidateSummary` **field-shape profiles**. They do not name a cycle index.

| Profile | Serialized key count | Cumulative post-p0 fields in serialization order | Evidence/status |
|---|---:|---|---|
| p0 | 22 | None | Historical summary before the three Sep 22 fields; present in v3/v5/v6 receipts. |
| p1 | 24 | `grounding_issue_codes`, then `grounding_report_ref`, inserted after `grounding_disposition` | A v7-era serializer shape; no actual v7 receipt found in the searched corpus. |
| p2 | 25 | `source_content_hash` after `content_hash`; `grounding_issue_codes`, then `grounding_report_ref` after `grounding_disposition` | Later v7-era shape and the current CandidateSummary field shape. |

The p0 ordered keys are `candidate_id`, `content_hash`, `cycle_index`, `generation_channel`, `proxy_score`, `voi_estimate`, `grounding_status`, `grounding_source`, `grounding_disposition`, `grounding_score`, `current_valid`, `value_status`, `value_decision_grade`, `value_ref`, `value_blockers`, `certified_by_n9`, `front`, `high_proxy`, `low_grounding`, `quarantine_action`, `adversarial_validation_status`, `counterexample_ref`.

The current declaration inserts `source_content_hash` between `content_hash` and `cycle_index`, and inserts the two grounding fields between `grounding_disposition` and `grounding_score` (`generation_cycle.py:907-926`). Defaults are serialized: `source_content_hash=null`, `grounding_issue_codes=[]`, `grounding_report_ref=null`; `value_receipt` is excluded. Thus old p0 payloads gain three keys on a current dump. The empty issue-code list alone is a hash-relevant value. Hash canonicalization sorts keys, so field insertion order explains the byte mismatch, while the additional key/value pairs explain both hash mismatches and byte mismatches.

## Phase 0 corpus and denominator

The Phase 0 denominator is **2,867 tracked `.json` paths**, parsed with zero errors; this whole-repository count includes the unrelated `.github/renovate.json`. The `policy-engine/` product subtree has 2,866 tracked JSON paths. A recursive receipt walk distinguishes actual receipts from enclosing contract nodes: it found 14 v3 and 20 v6 receipts with embedded `CandidateSummary` (all p0), and zero v4/v5/v7 receipt nodes in tracked JSON. A raw schema-marker count is not the receipt denominator: it also sees 7 v1 nodes and 17 v3 nodes, three of the latter being comparison-contract envelopes without an owner projection. The historical CandidateSummary corpus is:

| Outer receipt schema | Embedded summaries | Profile and cycle index |
|---|---:|---|
| v3 | 14 | All p0; all `cycle_index=0`. |
| v4 | 0 tracked receipt nodes | Supported v4/v2-owner reader exists; tracked corpus replay is `UNRUN` because no v4 fixture was found. |
| v5 | 1 compressed unit-test literal | p0; not a tracked JSON path. |
| v6 | 20 | All p0 (22 keys); 19 have `cycle_index=0`, one has `cycle_index=1`. |
| v7 | 0 tracked receipt nodes | Actual profile corpus not established. |

The v6 cycle-index-one exception is `/generation_cycle_run/promotion_port/receipts/1` in `architecture/policy_design_case/layer3_gy_generation_cycle_contract.json@1bb62940465b1c83d707b87df8f9b59484c28762`. A Phase 0 tree read confirmed it still has 22 summary keys and none of the three Sep 22 fields. Therefore it is p0; cycle index is an independent attribute.

The 14 v3 p0 summaries occur in `architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json@efb75eb36d6731d07ce70e49eb9dda83649b52d6` (10) and `architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json@f6fc534efd909a1ca311fd9665a03d4ec41e8a8e` (4). The 20 v6 p0 summaries occur in:

- `architecture/policy_design_case/layer3_gy_generation_cycle_contract.json` (2),
- `architecture/policy_design_case/layer3_gy_promotion_contract.json@3a53eb1a73a07ed3c8910854b98d11cc6e67728c` (3),
- `docs/superpowers/journals/gy-phase5-evidence/pr1/promotion-comparison-complete-observation.json@846fc11711070f178eba5403ca1ad3daa79695d4` (12),
- `tests/repo_quality/tools/fixtures/layer3_gy_promotion_contract_credal_v1.json@0c75c962b68baf72ca49ddeb4b14ace442340c73` (3).

My earlier independent traversal reported 2,869 JSON paths because it ran on the later `codex/e02-r2-ledger` tree at `c34fa756`. `git diff 73c656744 c34fa756 -- '*.json'` shows exactly two added package files, `PolicyOS_E02R2/finding_record_probe.json` and `PolicyOS_E02R2/residual_ledger.json`; no JSON modifications or deletions. Thus 2,869 is the later tree count (`2,867 + 2`), not a contradictory Phase 0 denominator. Use 2,867 for the historical corpus.

The count is reproducible from the Phase 0 worktree by walking Git's complete tracked JSON set and parsing every member (not a `rg` sample):

```sh
python3 - <<'PY'
import json
import subprocess
from pathlib import Path

root = Path("/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos")
tracked = subprocess.run(
    ["git", "-C", str(root), "ls-files", "-z", "--", "*.json"],
    check=True,
    capture_output=True,
).stdout.split(b"\0")
paths = [root / item.decode() for item in tracked if item]
errors = []
versions, profiles = {}, {}
for path in paths:
    try:
        document = json.loads(path.read_bytes())
    except Exception as exc:
        errors.append((str(path.relative_to(root)), type(exc).__name__))
        continue
    stack = [document]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            version = value.get("schema_version")
            owner = value.get("owner_projection")
            summary = owner.get("candidate_summary") if isinstance(owner, dict) else None
            if isinstance(version, str) and "n9_promotion.v" in version:
                versions[version] = versions.get(version, 0) + 1
            if isinstance(version, str) and isinstance(summary, dict):
                keys = set(summary)
                profile = (
                    "p0" if not keys & {"source_content_hash", "grounding_issue_codes", "grounding_report_ref"}
                    else "p1" if "source_content_hash" not in keys else "p2"
                )
                key = (version, profile, len(summary))
                profiles[key] = profiles.get(key, 0) + 1
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
print(f"tracked_json={len(paths)} parsed={len(paths) - len(errors)} parse_errors={len(errors)}")
print("schema_nodes=", dict(sorted(versions.items())))
print("receipt_summary_profiles=", dict(sorted(profiles.items())))
PY
```

The observed output is `tracked_json=2867 parsed=2867 parse_errors=0`, 14 v3 p0 summaries, and 20 v6 p0 summaries. The v5 compressed test literal is outside this Git JSON walk.

The v5 oracle is embedded in `tests/unit/runtime/quality/test_promotion_sequence.py@fd72907d54b287a2d22031786e6cfd955a40c4d1:531-617`. Decompression yields 48,568 bytes with SHA-256 `dba4a1ab7f374ea04044b171b0e163c6b0b1390089197fc64f96c2f0e86983c9`; the stored p0 summary has the 22 fields above. Existing exact tests are `test_frozen_v6_capture_preserves_history_and_refuses_current_admission` (`:531`), `test_round1_v5_v2_receipt_round_trips_but_cannot_regain_current_authority` (`:584`), and `test_round1_v5_authority_receipt_cannot_enter_historical_comparison` (`:603`). The v6 test currently walks the comparison manifest inside one fixture; it does not enumerate all 20 tracked v6 nodes across all four files.

## v7 excluded-record and source search

No complete or authenticated v7 `CanonicalPromotionReceipt` oracle was found in the inspected text, JSON, CAS blob, SQLite, or gzip corpora. The Phase 0 tracked JSON census found zero v7 receipt nodes. A full exact-marker text search on the E02 integration worktree also found no v7 marker in its tracked combined agent package.

| Search set | Complete searched denominator | Result |
|---|---|---|
| E02 `.superpowers/sdd/bundle_manifest.json` records | 63,443 non-binary files; 173,343,952 bytes searched | Zero exact v7 marker files. |
| CAS-style `.blob` records | 21,393 files; 98,326,785 bytes | Zero raw marker matches. |
| SQLite files | 76 files; 10,162,176 bytes | Zero raw marker matches. |
| Gzip records | 139 files; 1,597,440 decompressed bytes | Zero marker matches; no decompression errors. |
| E02 tracked combined package | 185 tracked paths; raw search traversed 187 files / 10,036,984 bytes | Zero marker matches. Two extra local paths are ignored `.pyc` cache files, not tracked package artifacts. |
| E02 branch tracked JSON | 2,852 paths at `codex/safe-workspace` HEAD `00d946c2`; parsed with zero errors | Zero v7 `schema_version` receipt nodes. |

The exact marker appears in nine tracked files at that E02 HEAD: the promotion runtime, its unit test, the promotion checker, and six D1 journal JSON documents. Those JSON documents are references/observations, not complete receipts: recursively parsed tracked JSON contains no v7 node. The package manifest and sampled package inputs are `PolicyOS_E02_Combined_Agent_Package/bundle_manifest.json@130ba865f6df9b1e7cd3bec5ce868df85e9b918c`, `finding_to_bundle.json@a6d76fefcca9519962e50684d4377d4eec2aa12c`, `source/B_r19_original.md@d800082eebfc12eaf647b0c0257c4f06e135d25a`, and `source/LA_r09_original.md@4bdf76e99f0c26e40bc2a71e76d4940c23712260`.

The searched git-excluded record controls are all under `safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/`: `I1-CURRENT-RECONCILIATION-DELTA-20260921.md@sha256:b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`, `progress.md@sha256:148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e`, and `i1-test-queue.json@sha256:69b2373fe34aea0243b39f68c4f650237c1e62ef258da7fa5b77d5b8bed1b0b1`. No receipt contents were copied into this report.

**UNRUN:** the excluded tree contains 868 DuckDB files, about 2.466 GiB. The E02 final-integration subdirectory alone contains 56 DuckDB files (155,877,376 bytes). Those databases were not opened or queried under the no-native-job constraint. A v7 payload stored only inside those databases is therefore not ruled out. No v7 producer/deployment identity evidence was found alongside a complete receipt because no complete receipt was found.

## Narrow implementation and verification boundary

Recommended core source/test write set, after baseline freeze and R3 lease: `runtime/quality/promotion_sequence.py` and `tests/unit/runtime/quality/test_promotion_sequence.py`. Preserve separate versioned reader boundaries for v3/v4/v5/v6, including the v4 owner-projection-v2 path; freeze each nested summary projection from authenticated serializer evidence rather than assuming an absent v4 fixture's shape. Keep v4 corpus replay `UNRUN` until a complete fixture is found. Introduce strict p0/p1/p2 historical readers for v7. Select a v7 structural profile only when the raw projection hash and exact byte round-trip uniquely match that profile. Ambiguous profile selection is `not_established`. Bump the current promotion/input schema to v8 and owner projection to v4; v7 remains history-only and cannot migrate into current authority. A current v8 receipt is freshly issued through the authorized owner path, never produced by retagging or restamping old bytes.

**The two-file list is not the complete consumer write set when the schema bump lands.** `tools/quality/validation/check_layer3_gy_promotion_contract.py@16dd37b38fddcc7b5f182d041ed7e520311c3ab8` has a hard-coded `_N9_V7_EPOCH`, guards the current input against v7, and implements the authorized v6-to-current transition in `_translate_n9_v6_receipt_epoch`. Its output schema, rule refs, and current owner schema must target v8/v4 when the owner version advances. Update and replay its test `tests/repo_quality/tools/test_layer3_gy_promotion_contract.py@9941ce2d12db1b9329f515b7e7d867c4e0a3394d::test_n9_writer_reissues_the_governed_v6_source_scope_epoch`. This updates the explicit transition implementation and its test only; do not run its `--write` path or modify the frozen JSON contract/fixture as part of R3. A persisted epoch/receipt reissue remains a separate authorized transition and must not be simulated by restamping.

Removal probe: keep receipt schema markers but run p0 receipts through the mutable current summary type; v6 owner-hash replay and v5 byte-exact replay must fail. Positive control: a fresh p2/v8 receipt verifies with all fields bound, while p0 v3/v5/v6 receipts replay historically and still refuse current authority. V7 controls exercise all three frozen shapes, require unique structural matching, and refuse authority in every case; they are parser controls, not evidence of a stored v7 corpus.

Keep R2 `GenerationCycleRun` and R13 acquisition re-entry out of this R3 patch. Their `CandidateSummary` embeddings need a separate, coordinated schema/history decision under those write leases. Any resulting change to `generation_cycle.py`, `AcquisitionOverlayReentryReceipt.v2`, or acquisition routing is out of this map's implementation scope.
