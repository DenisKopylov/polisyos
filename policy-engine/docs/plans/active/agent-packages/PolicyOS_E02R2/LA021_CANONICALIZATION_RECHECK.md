# LA-021 canonicalization re-check

## Result

**PASS (exit 0).** The pinned historical Core and IR implementations and the current Core and IR facades agreed on the exhaustive tracked-JSON selector and the fixed codec vectors, except for four recorded historical malformed-tag encoder differences. The measurement took 115.944 seconds on Python 3.14.0 / Pydantic 2.12.5 / macOS.

The deciding output is `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/la021-canonicalization-20260924.log@12796e7177e20ee23c49619c34c866305e060fcdfbe2941ec4ae7061b6f63974`. Its SHA-256 was read back and matched. The instrument is [check_la021_canonicalization.py](tools/check_la021_canonicalization.py) at commit `0b71f037cd83785c0b62244dad861dcaaf8c21ed` (blob SHA-256 `f2b49f190c8cdb687aed57c2285dd20b5cdbfefc475714f0abbf39bfd8ba36f8`).

## Selector reconciliation

The instrument selects every regular Git blob ending in case-sensitive `.json` from the pinned integration tree `73c656744f051d9f40667da7f8bc91c61d8b4ebf`. This gives **2,867 tracked paths, 2,833 unique blobs, 34 duplicate path occurrences, and 213,526,105 path bytes**; the unique blob bytes read total 213,420,537. The path-and-blob manifest digest is `12dbd3659110a6fa67404f95c07af05d438dbd9e6163d3e7cf250a8f4113beed`.

The earlier **2,852 / 2,818** estimate used the same selector at E02 head `00d946c2b7d052522be092f9c70eb9902f6521c2`. A read-only Git-tree comparison reproduces both counts: the merge adds 15 JSON paths from main and removes none. Those added unique blobs account for 446,146 path bytes. Six retained paths also changed blob size, adding 81,832 bytes; together these explain the 527,978-byte increase from 212,998,127 to 213,526,105:

The paths below are relative to `policy-engine/`.

| Retained path changed at merge | Byte delta |
| --- | ---: |
| `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json` | +41,086 |
| `apps/runtime-dashboard/src/shared/i18n/locales/en.json` | +1,912 |
| `apps/runtime-dashboard/src/shared/i18n/locales/uk.json` | +3,016 |
| `architecture/baselines/imports/deep_import.json` | +8,573 |
| `architecture/public_surface/inventory.json` | +1,944 |
| `schemas/runtime_api_v1.openapi.json` | +25,301 |

All 2,867 selected documents parsed as strict UTF-8 JSON with unique object keys. The complete corpus has 1,778 files containing floats and no `_type` tags.

## Per-profile corpus outcomes

Every row below has denominator 2,867. The accepted/rejected counts are per operation; the same counts held for the legacy implementation and its current facade.

| Profile | Default encode accepted / rejected | Floats-enabled encode accepted / rejected | Decode bytes accepted / rejected | Decode object accepted / rejected |
| --- | ---: | ---: | ---: | ---: |
| Historical Core | 1,089 / 1,778 | 2,867 / 0 | 2,867 / 0 | 2,867 / 0 |
| Current Core | 1,089 / 1,778 | 2,867 / 0 | 2,867 / 0 | 2,867 / 0 |
| Historical IR | 1,089 / 1,778 | 2,867 / 0 | 2,867 / 0 | 2,867 / 0 |
| Current IR | 1,089 / 1,778 | 2,867 / 0 | 2,867 / 0 | 2,867 / 0 |

The default profile's 1,778 rejections match the 1,778 JSON documents containing floats; enabling floats admits all documents. For each historical/current pair, default and floats-enabled encoded bytes matched on all 2,867 inputs. Historical/current byte decoding and direct object decoding matched on all 2,867. Cross-decoding matched in both directions for the 1,089 default-encoded documents (2,178 comparisons) and all 2,867 floats-enabled documents (5,734 comparisons). No unexpected corpus discrepancy was recorded.

## Fixed vectors and hashes

The vector set contains 27 cases copied from four source files pinned by blob in the receipt. Per profile, it attempted 27 encodes, 74 byte decodes, and 21 direct object decodes. Core accepted/rejected counts were 18/9 encodes, 69/5 byte decodes, and 17/4 object decodes. IR counts were 15/12, 60/14, and 14/7 respectively. Historical and current counts were identical within each profile.

The four expected historical differences are the two malformed `_type` values (list and object) encoded by each profile: the historical encoder leaked `TypeError`; the current facade raises its typed `CanonViolation`. There were no other fixed-vector differences. The cases also verified Core-only tags, Core/IR exception-class separation, typed scalars, dataclass and Pydantic inputs, null policy, datetime normalization, float policy, depth limits, malformed/unknown tags, and stable byte/hash goldens.

Each of the four profiles passed all 16 raw hash vectors (four input forms by SHA-256, default and 16-byte BLAKE2b, and explicit SHA-1). The Core-only historical and current implementations also matched their independent hashlib goldens for fingerprint, truncated hash, and streaming hash. There were no hash discrepancies.

## Scope limits

The claimed historical 418-input selector could not be replayed: no immutable manifest for those exact inputs was found in the tracked CAN-01 package or its pinned codec tests. This measurement supplies a new exhaustive denominator over tracked JSON plus the named pinned vectors; it does not claim those are the same 418 cases. A pinned caller census found 136 test files referencing codec APIs, but those dynamic callers were not executed.

Unresolved by construction: non-JSON tracked inputs; ignored or persisted CAS artifacts and `production_data`; dynamically constructed inputs in the 136 caller files; arbitrary typed-tag payload/shape space beyond the fixed cases; and other Python/Pydantic versions. The measurement did not read or copy `production_data`.
