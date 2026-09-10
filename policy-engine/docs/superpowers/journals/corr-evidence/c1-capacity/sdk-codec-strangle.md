# SDK codec default — 2026-09-09

The original adapter's strict JSON parser duplicated the existing extraction
owner. The earlier wrapped-JSON refusal test was red before the adapter was
changed to call `article_extractor._parse_json_object`; the extraction DTO and
structural intake were not relaxed. `codec_strangle.py` now emits the P28
companion from real SDK dispatch over a marked synthetic HTTP transport.

The complete declared codec witness set is ordinary JSON, wrapped JSON and
malformed text. The producer reconciles dispatched content and persisted
provider-attempt identities independently. The unchanged default accepts the
first two and refuses the third, and all artifacts remain candidate-only.
This is a codec vocabulary witness, not an extraction-correctness denominator.

`sdk-codec-strangle-final-green.json` records RC 0 in 4.411 seconds and the
run-emitted `sdk-codec-strangle-final-receipt.json`. The removal changes the
invoked codec back to strict JSON decoding while keeping its module/function
markers. `sdk-codec-strangle-final-removal.json` records RC 1 in 4.662 seconds:
ordinary JSON remains valid and wrapped JSON is wrongly refused. This decisive
behavior, rather than the codec reference string, turns the gate red.

The first proof captures and the intermediate Ruff failure are retained. The
final helper uses explicit exceptions (so optimized Python cannot erase checks),
has complete annotations, and passes scoped Ruff in
`sdk-codec-strangle-final-ruff.json` (RC 0, 0.267 seconds). No production source
changed to produce this companion, and no provider request was made.
