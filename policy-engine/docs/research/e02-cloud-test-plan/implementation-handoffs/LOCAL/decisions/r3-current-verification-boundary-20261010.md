# R3 authority manifest and canon boundary

Implementation candidate `cef50f0e23a50cd62368bdbbca0be878a340676d`, tree
`c90626e65e8a455a8cf4f2c73b797ed957a0fa8d`, parent/slice base
`c4563fd4da93bf9cc06de3dc77554a8a0d117359`. Its complete five-path footprint is
the control artifact owner, Data Forge measurement-root companion, authority
reconciliation tests, NL cost projection tests, and workspace-loop tests.
Post-commit readback is retained at `LOCAL/raw/r3-source-boundary-20261010/`;
these five working files match their committed bytes.

The reader now compares the selected authority-envelope manifest with the
complete existing Core profile projection, including producer, schema, scope,
closure, governance, environment, inputs, and effective canonicalization. The
producer binds effective JSON canon into the immutable identity context;
explicit options retain Core precedence. Measurement-root writer and fresh
reader share the same typed `forbid_floats=False` configuration. Malformed
supplied canon is refused rather than replaced by a default. Foreign tenant
and same-bytes forged-canon controls retain real default/profile view identity.

The captured foreign-manifest red is
`LOCAL/raw/r3-envelope-profile-red-verification-20261010/`: the old shared
verifier accepted the forged selected view. The first full-profile repair then
produced 12 FAIL / 3 PASS; those failures identified missing normalization of
valid JSON canon. The following source-bound composed attempt retained 16 PASS /
3 FAIL at `LOCAL/raw/r3-v3-v6-canon-composed-verification-20261010/`. Its complete
output, not an observer's description, is retained with command and source hashes.

At the current committed authority/cost source bytes, the whole authority test
module and real R3 cost/settlement path pass in
`LOCAL/raw/r3-v3-workspace-fresh-consumer-verification-20261010/`. That full
attempt is **17 PASS / 2 FAIL**, not an overall pass. Its remaining failures are
V3's test receipt-variable mix-up after successful GET integrity reconciliation,
and the workspace negative's counting of an internal ownership lock as an
artifact. The latter now uses the actual complete CAS inventory and refuses
failed/incomplete enumeration. The real measurement producer → CAS → strict
fresh reader and fabricated-source → refusal → empty artifact inventory both
pass at the final workspace bytes:
`LOCAL/raw/workspace-real-negative-inventory-verification-20261010/`, **2 PASS**,
14.13 pytest / 18.53 wall seconds. The earlier positive's ordinary JSON parse
left tagged floats as dictionaries; the strict reconstruction now uses the
canonical decoder. No producer identity or production data was rewritten.

Ruff and format checks pass on all five implementation files. The architecture
iteration command is retained at `LOCAL/raw/r3-architecture-iteration-20261010/`:
exit 2, 159.501 seconds, full stdout 1,819,178 bytes at SHA-256
`080f52cd1eff7c04f1311b421c53a509090cde2a74732fb325eb609337038fcb`.
Four required generated checks were UNRUN because source-copy admission failed;
completed findings include deep-import drift and unresolved export totals.
This is a partial gate receipt, not native green. The source-copy mechanism is
being repaired independently. Gate provenance is `not_established` under P41:
changed paths intersect the complete checker denominator.

Independent review is
`LOCAL/reviews/r3-v3-manifest-scope-independent.md@ae375837dd8f172d1ef4ac60da051c1f908b71f021ef9fe9fdfad362adcc9155`.
P40 bucket is SAME_CLASS_DEEPER, widened to Core's complete manifest projection
and known producer normalization. Historical profileless/same-content manifests
are not automatically migrated or admitted. V6's selected historical L2
confidence is independently withheld; these passing R3 tests do not remove that
external input requirement. Strict environment admission and the final composed
wave remain pending. `closure_ids=[]`; all original-ID conclusions are author
proposals for independent G review.
