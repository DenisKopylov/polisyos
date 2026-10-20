# Q2 source-bound consumer runner

This package contains the tracked R6/R7 packaging helpers and the R9/R10
host/Linux orchestration bridge. The executable helpers are loaded from this
package and checked against `source-manifest-r10.json`; the older ignored RAW
R6/R7 manifests are checked only as upstream provenance.

Run the complete bridge from the `policy-engine` directory with
`python -m tools.quality.validation.q2_composite.q2_composite_cli`. Supply the
selected repository, exact host-build receipt and SHA-256, source commit/tree,
fresh output directory under the ignored Q2 RAW run area, and an existing
external neutral-state directory. The coordinator verifies the host receipt,
recomputes the profile plan, runs the three-profile primary barrier, and only
then admits supplemental profiles. It retains command and consumer receipts.

The helper tests live under `tests/repo_quality/tools/q2_composite/` and can be
run with `python -m pytest tests/repo_quality/tools/q2_composite`. These tests
include controlled command adapters; they do not establish a physical Docker
run, the installed-consumer matrix, or G acceptance. Those remain explicit
follow-up evidence.
