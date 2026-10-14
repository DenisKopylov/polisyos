# R1392-r2 binding addendum — final R1386 packet metadata

Date: 2026-10-14

This append-only addendum reconciles the packet-identity issue recorded in [the original R1392 review](r1392-r1386-fresh-cas-reader-independent-20261014.md). It does not modify or retract that historical record: the earlier assignment carried a temporary manifest digest, while the parent has now identified the final author announcement.

The final adjacent metadata now binds as follows:

- Candidate patch: `candidate.patch`, SHA-256 `dcf3d7e7a3fa16b168a80be9b65842d4d428f9b8dd89af315d705d02539a63be`.
- Final adjacent manifest: `manifest.json`, SHA-256 `7537b0c4ebba33afaf0854e8ed922a1ac9efcc2072fd9b3beef46f1702585819`.
- Final decision: `decision.md`, SHA-256 `ae3190f8203eb693448852c72cabeea5f604eb854ed069ab0c8af12c480a8aeb`.
- Patch materialization receipt: SHA-256 `69eb07ad18658f8708b68653d85dfaa1eca04f3e0bd85e0e5d7da354a77ba348`.

The earlier announced manifest digest was `dbfcc65f704c68c133a24ded192f592d80f2efa9271f46ca71e22d470113e405`; it is not the final identity. The final author announcement names `7537b0c4ebba33afaf0854e8ed922a1ac9efcc2072fd9b3beef46f1702585819` and `ae3190f8203eb693448852c72cabeea5f604eb854ed069ab0c8af12c480a8aeb`, matching the exact bytes currently adjacent to the patch. The observed manifest binds the same candidate patch and the previously reviewed base HEAD/tree/source frame, test-file preimage SHA `5092c6a52fa96ba5e89e610cef5936b08c2cd92fbec8e86b94fcacd2e887699f`, and virtual postimage SHA `7e3d206a7c244866daa3250580e1c89b7aa99ccffdfb41d3d307a7320fc1cac3`. The retained materialization receipt independently names those same patch/pre/post hashes and reports in-memory reconstruction PASS.

Therefore the earlier packet-binding limitation is resolved for the final metadata identity. The source-property disposition remains the original **GO for focused composed replay only**: one test-only path; fresh unscoped CAS reader at the same `cas_root`; selected payload, envelope, and diagnostic-event refs; preserved profileless and wrong-profile refusals; no synthetic owner claim. Runtime imports and pytest are still **UNRUN**. This addendum does not assert runtime verification, production ownership, issuer/custody, billing, currentness, or formal closure; `closure_ids: []`.
