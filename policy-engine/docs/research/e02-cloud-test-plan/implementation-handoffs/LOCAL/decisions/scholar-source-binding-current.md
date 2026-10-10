# Scholar source-binding current engineering receipt

## Status and boundary

This receipt describes the shared working tree based on branch `codex/e02-unified-local-20261009`, HEAD `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`. It is not the final source/input/backend freeze; these path hashes describe the observed file bytes at receipt time. The change is engineering evidence about content binding only. `formal_closure_ids=[]`; no G decision is accepted or proposed as formal closure. It does not establish web truth, source authority, currentness, freshness at a later time, or recommendation/publication admissibility.

## Property and implementation

The property is that each persisted citation’s half-open character interval resolves to exactly the snippet text from a source payload that the system can resolve and verify. The earlier producer-only correction kept trimmed snippet text and offsets aligned, but the consumer had accepted a plausible fabricated quote: the independent pre-fix probe in `LOCAL/raw/scholar-benchmark-independent/malformed-span-consumer-falsifier.*` printed `bundle_verifier_passed: true`; even the source-map helper printed `passed: true` with only a mismatch warning. Its historical command record does not bind all executed source-file hashes, so it is a property falsifier, not a source-attribution or P41 inheritance receipt. Raw output hashes are recorded in the independent review note.

The current helper in `src/polisyos/scholar/search/source_binding.py` resolves the raw CAS object, checks digest, size, manifest identity and Scholar kind/media/schema/producer, checks the selected manifest profile when the typed `ArtifactRef` carries one, reruns the existing page extractor and sanitizer, and requires `source_text[start_char:end_char] == snippet.text` for each snippet. Missing CAS, absent/unresolvable bytes, invalid references, profile or manifest mismatch, extraction failure, missing source text, out-of-range intervals, and text mismatch produce violations. An artifact ID alone selects only the default CAS manifest view and adds `source_artifact_profileless_default:<source_id>`; a content digest is not treated as proof that the bytes exist.

The real local chain is: `UrlFetchCache.put` stores the fetched raw bytes and returns an `ArtifactRef`; cache-to-`FetchResult` and `build_source_metadata` preserve that ref in `SourceMetadata`; `enrich_topic` calls `validate_web_evidence_source_binding(..., require_all_sources=True)` before `persist_bundle` and before constructing seed sources; `_source_spec_from_snapshot` re-resolves the selected full ref and places it on `SourceSpec`; `_acquire_bytes` reads the same typed ref and checks the acquired bytes against the declared digest/size. The verifier delegates through Scholar’s package facade, so Scientist does not own or import a second source resolver. The ordinary `ScholarService.enrich` path calls `enrich_topic`.

Bounded compatibility change: `verify_web_evidence_bundle` keeps the optional `cas` argument and remains callable without it, but a citation-bearing web bundle without a resolver now fails with `source_cas_unavailable` and reports `source_binding_status=not_established`. The API bootstrap test checks that an invented quotation is rejected before either bundle persistence or downstream enrichment. A direct call to `ScholarDeepSearchService.persist_bundle` remains a storage operation and does not itself perform source verification; this receipt claims the gated ordinary `enrich_topic` route, not that every possible direct storage call is an admission gate.

The checked profile proves byte-to-citation binding under the current extractor. It cannot show whether the fetched page was truthful, controlled by an authoritative issuer, later changed, or still current. No online fetch or external source was used for these tests.

## P40 classification

This is the same citation-span/source-binding class one level deeper: correcting producer offsets alone was insufficient because the bundle consumer could not join a snippet back to verified source text. The structural change adds the raw CAS reference path and makes source-aware verification run in the ordinary web-bootstrap consumer. Further source-binding escapes must widen this quantity-level mechanism or be recorded with a bounded residual and falsifier; they should not be repaired as individual snippets.

## Deciding evidence

Historical pre-fix consumer falsifier, run by the independent review against its then-current shared source tree:

- Command and original output: `LOCAL/raw/scholar-benchmark-independent/malformed-span-consumer-falsifier.command.json` and `.stdout.bin` (exit `0`, stderr empty).
- Output: `{'bundle_verifier_passed': True, 'bundle_violations': [], 'bundle_warnings': [], 'with_source_text_passed': True, 'with_source_text_violations': [], 'with_source_text_warnings': ['span_text_mismatch:snip.bad']}`.
- It proves the prior behavior divergence but is not a P41 source-attribution claim because the captured command did not bind the executed module hashes.

Current property and remove-the-property-keep-the-markers probe (cwd `policy-engine`):

```sh
PYTHONPATH=tests/unit/scholar/search .venv/bin/python - <<'PY'
from tempfile import TemporaryDirectory
from unittest.mock import patch

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scholar.search.source_binding import SourceBindingResult
from polisyos.scientist.evidence.verifier import verify_web_evidence_bundle
from test_source_binding import _bundle_for_source

with TemporaryDirectory(prefix='scholar-source-binding-probe-') as tmp:
    cas = FileSystemCAS(tmp + '/cas')
    original = _bundle_for_source(cas)
    snippet = original.snippets[0]
    invented = original.model_copy(update={'snippets': [snippet.model_copy(update={'text': 'invented quote'})]})
    intact = verify_web_evidence_bundle(invented, cas=cas)
    with patch('polisyos.scientist.evidence.verifier.validate_web_evidence_source_binding', return_value=SourceBindingResult(passed=True)):
        property_removed = verify_web_evidence_bundle(invented, cas=cas)
    print({
        'current_binding_rejects_fabricated_text': intact.passed is False,
        'current_binding_violation': [item for item in intact.violations if 'span_text_mismatch' in item],
        'remove_property_keep_markers_allows_same_fabricated_text': property_removed.passed is True,
        'property_removed_other_violations': property_removed.violations,
    })
PY
```

Output (exit `0`):

```text
{'current_binding_rejects_fabricated_text': True, 'current_binding_violation': ['span_text_mismatch:snip.src.b6f95337074e7ebe5e8a15ab.1'], 'remove_property_keep_markers_allows_same_fabricated_text': True, 'property_removed_other_violations': []}
```

Focused command (cwd `policy-engine`):

```sh
.venv/bin/python -m pytest -q \
  tests/unit/scholar/search/test_fetcher_security_cache.py \
  tests/unit/scholar/search/test_scoring.py \
  tests/unit/scholar/search/test_service_jobs_tools.py \
  tests/unit/scholar/search/test_source_binding.py \
  tests/unit/scholar/test_api_web_bootstrap.py \
  tests/unit/scientist/evidence/test_snippet_ledger.py \
  tests/unit/scientist/evidence/test_verifier.py
```

Output: 47 test cases (47 dots), exit `0`; two upstream Python 3.14 Torch JIT deprecation warnings, no test failures. The command covers exact producer slices, Unicode offset cases, CAS profile/manifest/hash failures, no-CAS and missing-artifact refusals, legacy default-profile warning, every-snippet verification, verifier behavior, and the ordinary API path rejecting a fabricated quote before persistence/enrichment.

Python Ruff command (cwd `policy-engine`):

```sh
.venv/bin/python -m ruff check \
  src/polisyos/core/contracts/scholar.py \
  src/polisyos/scholar/api.py \
  src/polisyos/scholar/orchestrator/enrich.py \
  src/polisyos/scholar/search/__init__.py \
  src/polisyos/scholar/search/cache.py \
  src/polisyos/scholar/search/models.py \
  src/polisyos/scholar/search/scoring.py \
  src/polisyos/scholar/search/source_binding.py \
  src/polisyos/scientist/evidence/snippet_ledger.py \
  src/polisyos/scientist/evidence/verifier.py \
  tests/unit/scholar/search/test_fetcher_security_cache.py \
  tests/unit/scholar/search/test_scoring.py \
  tests/unit/scholar/search/test_source_binding.py \
  tests/unit/scholar/test_api_web_bootstrap.py \
  tests/unit/scientist/evidence/test_snippet_ledger.py \
  tests/unit/scientist/evidence/test_verifier.py
```

Output: `All checks passed!` (exit `0`). `git diff --check` on the source/test/release-fragment footprint returned exit `0` with no output.

## Changed path hashes

SHA-256 values below bind the observed bytes at this receipt time; they are not a final source freeze.

| Path | SHA-256 |
|---|---|
| `src/polisyos/core/contracts/scholar.py` | `0b07188715674b88ed21d393dc02b41b8a0d500c3f6398b8ab1a280a9ee3fae5` |
| `src/polisyos/scholar/README.md` | `5841cae5a5b6b0b070d3b40f47c9b2d3961172ef1615c4aa37fa66f1b6bc0286` |
| `src/polisyos/scholar/api.py` | `22415287942e2eb286fbeede96d60073387408e79957b7db3b8e50cb315bce9f` |
| `src/polisyos/scholar/orchestrator/enrich.py` | `a8c8090ad6b382ac17004e98022ad55a685247c27b81a8987f59408564ccadd1` |
| `src/polisyos/scholar/search/__init__.py` | `362b3970fed8fb1b42fe2684e58401b6db00b01ae6e5462d28707003c91b5b7e` |
| `src/polisyos/scholar/search/cache.py` | `fdb1c7af47a42b109f06013c041807be1dc68065521ed55778f4b2e32dc56600` |
| `src/polisyos/scholar/search/models.py` | `a33422b4b6301972bd09bf6b6db13f8af10bbf4a1e9f2e072bed98ec963d2b34` |
| `src/polisyos/scholar/search/scoring.py` | `8b0782abf35a33e71041b1186865abc037d76f85c818852cf884e60876894d22` |
| `src/polisyos/scholar/search/source_binding.py` | `4c2b54180448ab9981896f12b9a5da0cd810a6140514e5a6bb051e7a546045ba` |
| `src/polisyos/scientist/evidence/snippet_ledger.py` | `e0370425cbec5bbd3b6b44f937f32c893c89341e3d4084882402215856f908de` |
| `src/polisyos/scientist/evidence/verifier.py` | `3060df3f87e1dba0cf61e83c671e61b7dab6e5bd655c299ad4d7885a641fde78` |
| `tests/unit/scholar/search/test_fetcher_security_cache.py` | `556505127e2ef6f7e171529224baef6daea99bd7a66e1737cfe1c9058c8b2b08` |
| `tests/unit/scholar/search/test_scoring.py` | `8c89be104e52799e7abbd8633ba634716d1cef4ecb08445fa74c9076ee43f5ad` |
| `tests/unit/scholar/search/test_source_binding.py` | `a7713008a2a78b7370a5469f70615daa5dffc9ba9ebe0529904beeddf452b9e4` |
| `tests/unit/scholar/test_api_web_bootstrap.py` | `703d1a89b9e049813f3df9626f12234421c00f0bce000d4ecfcb3b476509e835` |
| `tests/unit/scientist/evidence/test_snippet_ledger.py` | `8153c5e98cafa17ce10c2020439266fafcd2bf53bde451786e043809b4849bc2` |
| `tests/unit/scientist/evidence/test_verifier.py` | `4b584132892cbb93ae76724ba1962c6bb18ce743c5c494955c10779a6140c3fe` |

The changed footprint has no new config file. `SourceSpec`, `SourceMetadata`, and `FetchResult` now carry optional typed `ArtifactRef` fields; their generated model schemas render a nullable strict `ArtifactRef` object with artifact ID, kind, media type, and optional `manifest_profile_sha256`. Runtime/API schema, generated client, and public-surface review remain pending; the release fragment deliberately keeps `public_surface_inventory_reviewed = false` and `generated_client_compatibility = "requires_regeneration"`.

## Pattern pass

P29/P32/P37/P38 apply to source-content binding and consumer verification; P40 records the same citation-binding class one level deeper. The producer chain and ordinary `enrich_topic` verifier/consumer path are demonstrated. Source truth/currentness, issuer authority, live-web retrieval, G acceptance, and formal closure are outside this receipt.
