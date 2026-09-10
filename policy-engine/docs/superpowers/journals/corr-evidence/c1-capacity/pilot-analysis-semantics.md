# C1 pilot analysis semantics — declared before response inspection

Declared 2026-09-09. This document precedes this helper author's inspection or
interpretation of any live model's parsed response. The helper describes measured
candidate behavior and resource cost; it establishes no calibration or correctness
score. Root owns credentials, live calls and final publication.

The denominator is the unchanged six frozen work identities, with every reserved
attempt retained, including failures and unknown outcomes. SQLite and filesystem
identity sets, bindings, hashes, model identity and synthetic provenance must
reconcile before a complete result is credited. Unreadable, missing or contradictory
records are ambiguous or `not_established`, never measured zeros. Provider usage
must be actual nonnegative integer observations; unknown usage remains unknown.
Cost is frozen declared rate times observed tokens, not proof of provider billing.
The local token estimate is compared with observed prompt tokens only where both
are available; it is never substituted for missing provider usage.

For the same document and screening prompt, two actual JSON boolean `relevant`
judgments are mutually exclusive when they differ. Let N be the number of complete
paired boolean judgments and D their disagreements. Then at least D/N of these
paired documents have at least one wrong model judgment, and the pooled two-model
document judgments have at least D/(2N) errors. Neither expression identifies which
model erred, provides an individual model score, estimates an unobserved population,
or establishes correctness on agreements. Missing, non-boolean, mismatched-prompt,
failed or model-mismatched judgments are excluded from N with their identities and
reason recorded; the complete six-document denominator is still reported separately.
If N is zero, both expressions are `not_established`, not zero.

General extraction, free-text or claim-set differences are descriptive. Synonyms,
paraphrases, subsets and different granularity are not automatically contradictory
judgments and do not imply an error bound. No generic textual inequality is counted
as D. Extraction comparison is restricted to documents that both models actually
screened in and successfully extracted. Other documents have extraction comparison
`not_established`; they do not become empty claim sets. There is no gold adjudication
or correctness claim in this analysis.

Per-tercile forecasts reuse the historical-source-cost-target owner's original
input-length terciles and complete target populations, after readback verification.
Each sampled work's cost includes its complete observed phase/attempt chain, including
screening refusals and errors. Unknown phase/attempt usage makes the extrapolation a
conditional lower bound. Small-sample, input-tercile exchangeability is an explicit
assumption; these forecasts have no precision guarantee and do not authorize a full
pass. The direct-extraction concurrency experiment is separate.

Pilot memory/CPU analysis consumes the complete process trace. Warm memory slopes
are descriptive only, using samples after at least one durable work completion;
startup and missing samples are reported separately. This six-input trace cannot
establish a scaling knee or memory-complexity class.

The archive preserves primary parsed phase responses, provider observations, and
run-emitted summaries/StrangleReceipts that cannot be reconstructed from held inputs.
It does not copy held source documents, derived work records or a second sorted-key
view beside their sources. Synthetic artifacts carry their own `synthetic: true`
provenance and remain candidate-only; no analysis grants authority.

Acceptance falsifiers: removing a work/attempt identity prevents complete credit;
removing usage preserves an unknown and prevents an exact-cost claim; replacing a
boolean judgment with a string or arbitrary unequal extraction text cannot create
a mutual-exclusion error bound. All tests use marked synthetic artifacts and make
no provider calls.

Storage is a complete terminal output-root census, independently traversed using
`pathlib` and `os.walk` with `lstat`. Identity, kind, logical length and available
allocated-block values must agree. No WAL, SHM, lock, temporary, symlink or unusual
entry is silently omitted; their categories are separate. Logical bytes count
regular-file lengths; allocated bytes use `st_blocks * 512` once per inode and
do not establish unique physical APFS extents. Final stored bytes per completed
document and per elapsed second are descriptive end-state ratios. Native disk
write counters measure I/O volume and are never called storage consumed.

Checkpoint `usage_known` and provider observation usage are reconciled separately.
A failed reply can have unknown checkpoint usage but known provider tokens; its
observed cost is charged, and the accounting discrepancy remains explicit.
