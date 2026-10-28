# C90 R4 public Cloud inputs

This carrier contains the **unapplied, SOURCE HOLD R3 proposal**, complete
independent review and original small source-removal controls. It is input to a
compatible R4 repair, not accepted numerical code, runtime evidence, an R4
implementation or a G decision. Runtime/imports/tests/removals remain UNRUN.

All payloads are public repository source/test/doc/release differences and their
source review. There is no production data, credential, environment, CAS/DB,
private runtime output, or dependency archive. Historical local locators in the
verbatim review are provenance only; no private RAW path is a required Cloud input.

## Contents and reconstruction

- `source-r3.patch.gz` is lossless gzip of the complete held five-target patch.
  `input-manifest.json` binds compressed/uncompressed bytes and hashes, all five
  actual target preimages/expected absence and candidate postimage hashes.
- `C90-law-admission-r3-independent.md` and `.json` are the complete byte-exact
  review, including F01/F02 and declared limitations. The Markdown's JSON links
  resolve locally because the original review basenames are preserved.
- `property-removals-r3.json`, `verification-plan-r3.json` and `removals/` preserve
  the original nine small semantic property controls. Their source hashes and
  expected nodes describe R3, not a qualified R4 mutant. Rebind the property at
  the corrected common finalizer/actual source, collect real nodes and retain
  actual original/red/restored outputs. An old patch applying is not the test.

The prior R3 manifest is identified by hash in input-manifest.json; its authoring
scripts/static receipts/duplicate postimages are not necessary rebuild inputs.
Recover R3 source from the ordinary Git preimages and this patch. For example,
using this directory as `carrier`, read and verify the gzip before applying:

```python
from pathlib import Path
import gzip
import hashlib
import json

carrier = Path("path/to/this/carrier")
inputs = json.loads((carrier / "input-manifest.json").read_text())
compressed = (carrier / "source-r3.patch.gz").read_bytes()
assert hashlib.sha256(compressed).hexdigest() == inputs["held_patch"]["compressed_sha256"]
patch = gzip.decompress(compressed)
assert hashlib.sha256(patch).hexdigest() == inputs["held_patch"]["uncompressed_sha256"]
```

Use only the final Root-published launch source and its actual five preimages.
The manifest's `source_frame_before_carrier_publication` is the observed
preparation frame, not a guessed future commit/tree. Final launch/publication
fields intentionally remain null until Root supplies exact published identities.
Do not apply R3 as an approved repair, reset/rebase/overwrite drift, or execute
historical local authoring scripts. R3 can be reconstructed in the authorized
Cloud working source to reproduce the held regressions, then repaired to R4.

## Required compatible repair

F01 is the **same common preparation/finalization class**, not another per-route
ladder. Borrowed fixed values and unavailable original identity must have truthful
typed limitation/non-gating results across actual MC, Delta, Analytical and
fallback returns. Use one shared invariant and real gate-eligible moment-route
regressions; do not only fix the two example branches. Exercise the conditional
unvalidated numeric-buffer alias through its real consumer and report what the
actual supported revalidation accepts; do not claim an unrun conditional defect.

F02 is a **new producer/strict-reader handshake class**. Preserve the current
strict schema-1.0 draw ledger, whose actual 13 declared fields are recorded in the
manifest. Prefer existing `input_identity_status`/typed limitations. R3's extra
`fixed_input_identity_status` must not silently enter that grammar; never use
`extra="allow"` to make it pass. Current C78 producer/reader/fresh selected-CAS
tests are mandatory companions. Shared schema/facade/version changes belong to
Root; a demonstrably required wire change needs explicit coordinated versioning,
not an implicit field addition or a new G architecture cycle.

The existing sampling recipe hashes uncertain envelopes/configuration, not fixed
scalar invocation data. Fixed scale=2 versus scale=3 can have equal recipes while
changing outputs. Do not promote `content_hashed`/a new ownership marker into a
complete-invocation/source-authority claim. Keep the actual existing IR limitations.
Preserve compatible callback values/types and public provenance behavior; any
bounded in-memory wire-only difference needs an explicit real-consumer falsifier,
not an invented generic Python codec or sandbox claim.

## Execution and evidence boundary

The standalone R4 launch prompt supplies final source pins, lease, regression and
nine-control execution. It must include the real current C78 check at
`tests/unit/scientist/nodes/builtins/simulate/test_uncertainty_source_projection.py`
and genuine MC results → actual Science `_persist_report`/node path → selected
report → fresh strict reader. An existing hand-authored report fixture alone is
not that producer witness. Preserve historical reports and unknown-field refusal.

Cloud has no mid-run transport channel. Its final managed source diff is separate
from a task-owned evidence package capped at **512 KiB (524,288 bytes)** after
lossless compression. Measure complete file/type/path/hash and compressed and
uncompressed totals. The budget is our evidence design, not a provider capacity
promise. Keep full required A/D outputs; never truncate/omit them and claim PASS.
If over budget, preserve useful source and available evidence, state the exact
unavailable gap and minimal repeat. No runtime or code acceptance is supplied by
this public carrier; closure_ids=[] and code_acceptance=false remain correct.
