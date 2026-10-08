# Independent factual and disclosure reviews

Root authored the packets; both reviewers are direct nonauthor helpers. No product tests or production input reads were performed by the reviewers. The first immutable facts candidate was `66f1b9dc3adb336ce39f255c1bffa6e4f65a643b`, tree `8eeebbe480cebaf46d05173b53bc4a131d4e5576`. Corrections were appended as `621e9e7aec1af78da72b0c4b47a8cb8b79daa5fd`, tree `44ce244676e9de74aec215397a1b790c51674cdd`. The deciding review outputs follow; scopes and historical verdicts are retained. One private prior-label mention is redacted; the unredacted local output remains in ignored `policy-engine/_build/e02-L01-restart-20261008/private/independent-review-full-local.md`.

## Disclosure reviewer: initial candidate

**Verdict: no-go for this exact packet until two wording/disclosure corrections.** The factual slice is otherwise carefully bounded and suitable for a limited handoff.

The L6 alias is not opaque: it encodes a country label and appears again in the supplier description and local receipt filename. The local alias index I checked covers the two Legal aliases, not this L6 alias. Replace the L6 label and tracked receipt pointer with neutral aliases, or provide disclosure admission. See `packets/A-l6.json:20`.

The README calls I3 “a real publish snapshot,” while its packet classifies readiness, profile, and time as owner-supplied and leaves live source/run/cursor binding unestablished. Reword it to say the metadata *describes* a snapshot. The branch-admission, disk-space, and Trash statements in README line 17 also lack a linked receipt and are unnecessary in this handoff; remove them or keep them in local operational notes. See `README.md:6`.

The complete delta is nine files—seven JSON and two Markdown, 37,473 bytes total; the largest is 14,097 bytes. It contains no copied source documents or oversized generated views. All 22 Git source refs resolve to the declared blobs at fetched G, and all 11 original-criterion line ranges match their recorded hashes. The candidate is attached to the stated branch, directly follows the pinned base, and has the pinned tree.

The seven cited private receipt files exist and are ignored. Comparing them in memory found no private production path, credential, payload, or production-data digest in the packet; the only digest-valued match is the declared public slice-base commit. The two Legal aliases resolve through the ignored alias index. I did not read production payloads or DB rows, run tests, or publish anything.

The read-only scope is represented honestly: root metadata and three nominated L6 control JSONs; two nominated B194 member stats; no payload census, DB rows, vectors, or model payload. The packets also distinguish owner-supplied, recomputed, and not-established predicates. Their property/proxy falsifiers are concrete: a mismatched dataset/run cursor can coexist with `prod_full` metadata; text search can work without a vector provider; dropping negative-input draws can preserve metadata and file sizes; and separate per-instance caps can pass while aggregate shared work exceeds its cap. The L6 packet records the observed descriptor mismatches while holding the served path and custodian authority unestablished.

## Disclosure reviewer: correction delta

**GO, bounded** for candidate `621e9e7` (`44ce244` tree). The complete delta from `66f1b9d` is four files: three JSON and one Markdown. It is a direct child of the reviewed candidate, and `git diff --check` is clean.

The alias is now neutral, the old country-bearing receipt filename is replaced by a pointer into the ignored alias index, the I3 summary says metadata *describes* a snapshot, and the unsupported machine-state notes are gone. The alias key exists in the ignored index; I did not open the private target.

The F/B56 correction matches current G source: the control dispatch, persisted admission, and separate workspace-loop-to-Scientist callers are present. The packet correctly treats those as source routes only; the actual B56 workload, shared cap, and roster remain `not_established`. Its falsifier distinguishes those generic callers from evidence of an aggregate admitted workload.

`source.json#/source_refs` now has 27 entries; all 27 resolve to exact blobs at the pinned G commit. The prior refs, original criteria, base, and G pin are unchanged. The revised files contain no country label, absolute host paths, credentials, or production payload content.

No tests or production inputs were read. The remaining limit is unchanged: there is still no authentic B56 workload witness, which the packet accurately leaves open.

## Factual reviewer: source-search correction

Correction to my prior note: my earlier `git grep` for `_run_legacy_scientist_workflow` was scoped to `run_lifecycle.py` and missed its mixin callers. At pinned G, `workspace_loop_transition.py` blob `7aa3be95b44f8c5d8c17feaa804be563a30869bf` calls it at lines 131 (`_execute_workflow`) and 901 (`_execute_legacy_shadow_workflow`). The helper is in `run_lifecycle.py` blob `85d24cf...` at 6933 and calls `run_experiment` at 6946. So it is not definition-only; I retract that. Still, full-source denominator 2,700 tracked Python files has zero `DurableControlWorker`/`sync_run_causal_full` symbols, and exact B56 admitted study workload/consumer remains unestablished. The verified source chain can mention ControlWorker dispatch→ControlPlaneService admission→workspace-loop transition→legacy helper→run_experiment where scoped; do not infer a B56 shared-budget witness from that generic route.

## Factual reviewer: correction delta

**GO, bounded to the four-file delta** in `README.md`, `source.json`, `packets/A-l6.json`, and `packets/F-b56.json`.

The five added source refs match their declared blobs in G commit `0321633c0e6d9a87bccfbbe889a4998934c52dd3`. The corrected F packet accurately labels the `ControlWorker` → `ControlPlaneService` admission chain and the workspace-loop → `run_experiment` → `run_selected_workflow` calls as source evidence. They do not establish an actual admitted B56 workload, shared cap, roster, or profile; those remain `not_established`.

The property/proxy divergence is explicit: the property is aggregate resource use across the actual shared admitted workload; the source proxy is generic dispatch and a source-level workflow caller. Both can exist without a named competing B56 workload or shared cap, and per-instance caps can pass while aggregate work exceeds the common cap. This is the same declared source/property boundary, not a new Runtime defect.

The new L6 public alias is present in the cited local alias index and resolves to the existing bundle-manifest receipt, whose embedded record retains the prior [private label withheld] alias. That local binding does not establish served-path or currentness. I found no blocking factual issue in the delta. No product tests or production reads were performed.

## Factual reviewer: combined scope clarification

No remaining **blocking** issue outside the corrected four-file delta. The prior nine-file review verified the 11 retained original criterion spans and 22 existing source pins; the delta review verified the five added source pins and the corrected L6/B56 qualifications. Together, that supports bounded delivery of the current `621e9e7` facts candidate.

One non-blocking traceability caveat remains: C-legal’s aliases resolve in the local ignored alias index, but that index is not explicitly listed in C-legal’s `local_receipts`. This does not establish any positive or closure; the handoff should preserve the local-only limitation.

The evidence supports the facts handoff only. It establishes no actual Runtime workload, admission, authentic positive, or formal G closure.

## Root disposition

The correction delta changes only source qualification, public alias/receipt pointers and wording; the original byte observations and historical outputs remain unchanged. The C handoff explicitly points to the ignored alias index. Private alias resolution is local-only. The initial no-go and reviewer search retraction remain source-qualified history. Both final reviews support the bounded factual packet, with no code acceptance or finding closure assigned to G.
