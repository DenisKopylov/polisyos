# Optional native test admission

Test implementation `66270f22b3cdab68196f97d78cc6c9e4715ce97c` adds optional
backend admission only to the three leased native test surfaces. All 57 original
assertions and all original statements/decorators survive removal of the new
fixture/admission calls. No product code changed.

The actual three-whole-file run used merged ROOT
`b9fc7d005d39ded686f276fae8eae617b683bac6`, tree
`689ce50660504bb7d718d124ec2c41f4dd5d7ddd`, its canonical config/conftest and the
real frozen minimal148 environment. It collected and finished 38 unique cases:
17 PASS, 21 SKIP, zero failures/errors/deselections. Six fallback cases and eleven
history/DTO cases executed. Fifteen vector cases, five transfer-history/native
cases and the first native Sobol case skipped because their backend was absent.
These 21 native properties remain **UNRUN**, not native passes. No GP26 or full
backend replay occurred.

The lossless gzip JSON carrier retains ten complete output/input-identity
members. Decode gzip, then parse JSON. UTF-8 members reconstruct from `content`;
the `after.json` member refers to byte-identical `before.json`, avoiding a second
copy while retaining its original name/path/hash/size. Verify each reconstructed
member against its raw SHA256/size. All original files remain at the actual
output directory. No tracked source/test/config/document bodies are embedded.

Before/after 5,567 input identities and root Git state are unchanged. The capture
includes all 2,701 product Python and 2,860 test Python inputs. Actual observed
249 product-module and 249 transient module-exec origins match frozen Git; this
does not claim that every product module executed. Complete stdout, stderr,
JUnit, collection IDs and phase reports remain in the carrier.

The old c17 broad run is a source-qualified SIGKILL partial ERROR. Its eighteen
relevant native call failures are independently reported; they are not a
completed baseline suite, an inherited waiver or retroactive green result.
Actual b9 results are a distinct supported-profile admission verification.

Pytest cache and basetemp were fresh, unique paths. No cleanup/deletion was
performed by the harness; framework/internal cleanup scope remains unknown.
The original minimal environment and linked dependencies remain retained.
