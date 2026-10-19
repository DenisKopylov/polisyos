# Independent delta QA: native typing G packet v3

**Verdict: PASS for the requested correction delta.** The former 367-as-consumer wording is corrected consistently. This QA does not adjudicate the G API choice or establish current type-gate status.

## Frozen inputs

- Correction overlay `native-typing-consumer-census-20261019-r5/consumer-inventory-correction-v1.json` — SHA-256 `772f9a349863a795bd353aad79c6ea12df57d33165fbe1cf5ce44d8a579434dd`.
- Decision `native-typing-consumer-census-20261019-r5/api-conflict-g-decision-v3.json` — SHA-256 `e620efefc5117ba7a99db269e4c4f6cb4e6fcf5a0607c7e0406c27d227c5ea6b`.
- Both SHA-256 values were read back and match the supplied pins. The source frame remains b770/tree `aade34278065576f738ddf352b6560ab4fa70bb8`, expressly historical rather than current HEAD.

## Delta checks

- The correction replaces `exact_family_consumer_files` with `exact_family_name_hit_files`, retaining 367 and the complete type split: 338 `.py`, 26 `.json`, 3 `.ts`. It expressly says these are exact tracked name-hit rows, not runtime/typed consumers, callers, or Mapping coverage.
- The v3 decision propagates that distinction through its consumer inventory status, IR consumer boundary, migration impact, required proof, and rationale. It says the 367 rows are not a Mapping caller denominator and leaves complete typed Mapping, reflection/dynamic, and external/private flow closure `not_established`.
- The broad Mapping search remains candidate-only: the 1,098 files, 16,921 literal matches, and 203 intersections are not labeled ArtifactRefModel consumers.
- The historical diagnostics remain attributed to the earlier ae14 run. The b770 full no-ignore MyPy replay is explicitly `UNRUN`; the selected 47/47 semantic test result is not represented as a MyPy pass or a current native-green result.
- No waiver, exception, expiry, issuer, automatic closure, or formal adjudication is introduced. The proposal remains `PROPOSED_NOT_ADJUDICATED` and awaits G.
- The correction overlay explicitly names the superseded r3 and r4 claims and points to the prior independent review; it preserves the original packets rather than rewriting them.

No source, tests, generators, or runtime/type gates were changed or run. No additional census or repository scan was performed.
