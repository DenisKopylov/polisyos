# Independent custody/version reviews

Root authored the receipts; both direct reviewers were nonauthors. Base: `5bcc319d1c2c08d7abba82fe87b818e502caea78`. First facts candidate: `c3f3b71ebf2e2f9b3f8a4cc38f6f4239ce880002`, tree `d2fc802451785accf662b99e7fcb7babb46bd1b5`. Three further task packets: `1e23d9ef80eab758391c11579caa8820004ed57b`. Final facts/pointer correction: `9f6841f877566a70aa559fc490c382a437f5619c`, tree `ebe6d6f2dd6ae27b2e3085616658060c3c4c1b78`. These are bounded facts reviews, not Runtime or admission verification.

## Factual reviewer: first five documents

**GO, bounded to the five new custody-version documents.** I found no blocking correction.

All 27 previously nominated source refs resolve unchanged in current G; all seven added refs match their declared blobs. The L6 comparison uses the exact pinned G `gy_content_hash` implementation loaded from AST and only the prior cached JSON metadata. I independently checked the three alias-bound objects against both the frame and refusal-suite source refs; the cached private receipt and public deciding output agree. I did not rerun old byte-SHA checks, execute the comparison script, or read production payloads.

The packet correctly separates content equality from release authority, currentness, and served-root identity. The frame remains `label_status=not_collected` with no correctness bound; the refusal suite is declared synthetic. The existing source-owned release/replacement reference remains a pending custodian question, not an admission condition. Actual L6 currentness and served root remain unestablished.

The I3 receipt supports the packet’s scoped root finding: the readiness ref is a child of the declared snapshot root, the direct ref does not resolve as a file, and that snapshot root does not match the nominated bundle root. The packet preserves the separate metadata profile declarations and leaves the live source/cursor/event/replay/verifier binding unestablished; it does not claim global data absence.

The property/proxy divergence is explicit: L6 content hashes can agree while release descriptors, currentness, or the actual root differ; I3 lexical containment and `prod_full` metadata can hold while the readiness ref is unresolved and the root mismatches. These are the same declared L6 and I3 boundaries, not new Runtime findings or formal closure.

One non-blocking wording note: `packets/L6.json#held_transition` begins “Authentic positive for an admitted current source.” The surrounding fields clearly leave admission and currentness unestablished, but preserve that condition if quoting it in the handoff.

## Disclosure reviewer: first candidate locator blocker

5-doc review complete at c3f3b71e (exact diff: 5 files, 4 JSON/1 Markdown, 11,789 bytes; clean diff). Disclosure/claim boundaries are bounded: no private indexed values, raw data, absolute host paths, credential-like text, or long non-Git digests in the new files. L6 is explicitly GY recursive time-stripped canonical-JSON equivalence (not file-byte SHA); currentness/custody/release/served-root and authentic positive stay not established. Frame `synthetic=false` remains a declaration; `label_status=not_collected`, `correctness_bound=null`, suite synthetic=true. I verified base/tree and G ancestry, all 7 new source blobs, all 27 prior nominated blobs unchanged. NO-GO on the two `prior_packet` locators as presently written: relative to packet files they do not resolve; their commit suffixes contain intended old packets only when resolved from the slice root. Source-scope refs are packet-relative and resolve, so the base convention is inconsistent/undocumented. A one-level prefix correction or explicit per-field base is needed.

## Factual reviewer: final eight documents

**GO, bounded to the current eight fact documents.** The three new packets stay metadata/source scoped; the two `prior_packet` corrections now resolve to the intended earlier packets. I found no blocker requiring an expanded gate or production prerequisite.

Legal’s helper records the C5/prior-L01 size and mtime agreement, preserves the prior alias/version binding, and confirms no content read or hash. The packet keeps that as metadata reconciliation, not database identity or current legal authority. The inspected G source supports the stated defaults/parameter-to-transport-constraints path and the separate lexical text-search route. Vector membership, model/query-encoder identity, effective request profile, and lawful current source remain unestablished.

B194’s helper records two index-named JSON references that did not resolve from the index directory, with their reference base unestablished; it records no payload or execution. The packet correctly limits the missing tuple to the selected evaluator, law, source-model domain, and ordered draw/outcome receipt. Its conditional fields are not universal prerequisites, and it makes no global-absence or all-S2-gate claim.

The named C08 G packet says the actual shared workload input is unavailable and disqualifies its synthetic test pool as the Runtime denominator. The B56 packet preserves that boundary while allowing a portable synthetic witness for mechanical admission once C01 binds the permit and roster. It does not claim an actual workload or require production population.

The property/proxy divergences are explicit: Legal metadata and a text hit cannot establish vector identity; a ready calibration index and member size cannot establish evaluator coverage; per-test pool caps cannot establish a shared Runtime permit. These remain the declared Legal/B194/B56 boundaries, with no new Runtime finding.

Carry `authentic_execution: UNRUN; L02` with the held-transition wording in the handoff. No tests, hashes, old probes, production reads, or edits were made.

## Disclosure reviewer: final eight documents

**GO bounded** for candidate `9f6841f877566a70aa559fc490c382a437f5619c`. The earlier `c3f3b71` candidate remains a no-go on its own: its two `prior_packet` paths did not resolve from the packet files. The final candidate fixes those prefixes; the cited commits are unchanged, and all five packet references now resolve file-relative.

The complete base-to-final delta is eight files: seven JSON and one Markdown, totaling 19,649 bytes. The three added packets are unchanged from `1e23d9e`; the two edits to L6 and I3 change only `prior_packet`. The diff check is clean. I verified the five prior-packet criterion sets, the seven new G source blobs and 27 unchanged prior refs, and B56’s supplier record at its pinned path and blob.

The packets keep the evidence bounded: L6 reports equality only in the GY hash domain, not byte identity, custody, currentness, release authority, or served-root identity. The frame’s `synthetic=false` remains a declaration alongside `label_status=not_collected` and `correctness_bound=null`; the suite is synthetic, and no authentic positive is claimed. I3 does not promote unresolved readiness/root metadata. B194 leaves the actual evaluator, law, and draw unestablished. B56 distinguishes a portable synthetic witness from the actual shared Runtime workload. Legal limits its result to metadata/stat reconciliation and leaves DB content, legal currency, and vector readiness unestablished.

The five `private_binding(s)` references resolve to ignored, untracked local receipts. Legal’s path overlap with the ignored alias index is that local receipt reference; I found no production asset locator or raw private value in the added docs. No absolute host paths or credential-like strings appear.

One nonblocking wording note: the pinned GY hash function removes its declared volatile-field set, which includes `runtime_metrics` as well as time fields. “GY volatile/operational-field-stripped canonical JSON” would describe the domain more precisely than “time-stripped.”

This was a read-only review; I ran no tests and read no production data.

## Root disposition

The pointer-only blocker was corrected append-only; prior observations remain immutable. Handoffs explicitly retain authentic UNRUN and the broader GY operational-field exclusion description. Local receipt-relative references are intentionally public operational references and expose no production asset locator. C5 owner evidence is qualified separately by exact fetched commit/path/blob, outside pinned G. No product code acceptance or formal finding closure is assigned.
