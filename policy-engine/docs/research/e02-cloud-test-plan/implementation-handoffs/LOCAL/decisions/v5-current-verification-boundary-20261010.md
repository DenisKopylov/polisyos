# V5 current Search receiver boundary

Implementation candidate: `3afc65ab9444efd28a8a81bcc2cd90b01d90ce9f`, tree
`3a9d90f0dea48cc9f202a3025c777c9b7f55cbb9`, parent/slice base
`00954ff836642ca3c2dca4032fcd1b83019bdfd0`. The complete implementation footprint
is the Search runtime and its MethodJob work-packet test module. Branch readback
is retained in `LOCAL/raw/v5-source-boundary-20261010/`; both committed files
match the bytes exercised below, and their post-commit working diff is empty.

P40 bucket: SAME_CLASS_DEEPER. The original red was a rejected same-shape dispatch
whose finite ATE still reached Search. Independent review also found that an
input-bound evaluator could disable capture and bypass the proposed guard. The
implemented quantity is every MethodJob evaluator with nonempty DataSnapshot
bindings, regardless of capture opt-in. Admission requires a fresh typed CAS
packet, the current request/source/profile identities, and the persisted result
metric/unit. Failed admission removes the primary score before objective,
promotion, and simulation-result projection. Legacy evaluations with no source
bindings retain their existing boundary.

`LOCAL/raw/v5-full-light-admission-verification-20261010/command.json` records the
exact command, selected environment, source hashes, and unchanged after hashes.
Its full `stdout.txt@4ddc00578ff1ebf95690b807b9df255e655cf9e4a492ac53cc0b0dc87fce51a8`
and `stderr.txt@da08d09ca985c2ccb39279a1d56f12b85e0815101be6e017e594a5219106f692`
report **10 PASS / 3 SKIP**, 9.88 pytest seconds / 13.10 wall seconds, peak RSS
907,313,152 bytes. The skipped native GP, native DR 80/40/80, and joined native
GP/DR witness have explicit serialized-slot reasons; they remain pending final
composed execution. The passing controls exercise actual Search intake for a
dispatch swap, missing/unreadable packet, post-persistence metric substitution,
and omitted/false capture, plus a positive fresh read.

Exact tested source hashes:

- `src/polisyos/scientist/methods/autotune/runtime.py@7d5a434b7fa34f1f01446286fdcdf1ca47075bd7958b826530ec8a9c6870d98c`
- `tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py@caa9670e9e9388590a484931e359aee9f54e7f37f21c12da32e3785ea957cd6b`
- `tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py@2138d3634704b4ff94aee12d906f914c5d66f33c0cdc805f007ba6249f501904`

Independent source/delta review is
`LOCAL/reviews/v5-search-admission-independent-20261010.md@586e56f6f4d860522a68f8b048aa24ae0a7f0abfe263713558c41eeeb63e39f7`.
Ruff and format were completed before the deciding run; no later source mutation
occurred in these paths. The real process sidecar `origins-50915.json` records
248 installed distributions / 64,185 file entries / zero inventory issues,
98 resolved external roots and two unresolved roots. Aggregate environment
qualification remains `not_established`; a strict environment manifest has not
yet been admitted. Other known R3/V6 WIP was present at execution and is recorded
as a composition boundary, not omitted from the final freeze denominator.

This is author evidence for a bounded consumer repair, not a formal G closure.
`closure_ids=[]`. B157's default policy-funnel mapping and B108's fiscal owner
inputs remain separate decisions in the engineering packet. The joined native
fixture does not bind the search coordinate to DR inputs and cannot establish
optimization efficacy or policy-effect authority. Next check: reviewed final
source/input/profile freeze, full composed native witness, strict receipt and
environment admission, then independent G adjudication by original occurrence.
