# ORCH03 C09 propagation lease delta review

Read-only review of carrier `8077016f144712b00a05f0b3b6701c51852f1d21` against `9a2cc9dbe0fc2c50ed2371f56cbdde79c05656ff`, current G dispatch/source feedback at `d23ea5e9dd252214fc9e0c5c941a8a3789cead0a`, and the tracked C09 propagation decision at `71ec2e0758cd7cd93423d3a91afe1a07cef61401`. No tests or source changes were made.

## Delta and disposition

The carrier adds exactly two files, both under `implementation-handoffs/ORCH03/`: `parallel-20261008-c09-propagation-lease.json` and its gzip admission receipt `parallel-20261008-c09-propagation-resume.json.gz`. No product source, tests, generated outputs, or G acceptance record changed in this delta.

The lease’s core is consistent with the tracked feedback: E remains the original C09 owner and `/root/c09` the proposed canonical writer; the existing backtesting writers (`evaluator.py`, `orchestrator.py`, `temporal.py`) are retained, and the 71ec propagation grant’s four named consumers (`forecast_bridge.py`, `backtest_matrix.py`, `calibration_validation.py`, `calibration_leaderboard.py`) appear in the exact list. Its interval-specific scope matches the 0932 finding and 1025 feedback: preserve the limited basis through temporal/CAS/report/scoring/promotion/forecast consumers; do not change global trust/scientific law or B172/B173 decisions. The payload correctly leaves historical `ee0b` on HOLD and says the new repair is not submitted/accepted.

The new exact list is disjoint from the current C07 IR paths, C08 graph/method paths, C10 A-owned runtime/S10/served paths, and G’s generated output/lock/global inventory ownership. It therefore does not create a same-file parallel writer. `G` remains sole integration publisher. The release fragment is a slice companion, not a G-generated artifact.

## Path-lease qualification

One path needs explicit G recognition as a lease amendment before authoring: `policy-engine/src/polisyos/calibration/interval_basis.py` (and its `polisyos/calibration/README.md` companion). The current `dispatch.json#/roles/C09` lists Foundry calibration/uncertainty and Scientist DOE/backtesting scopes, not the canonical `polisyos/calibration` package. The 71ec grant names `forecast_bridge.py` there, but does not name this new helper. Execution-organization does assign canonical `polisyos.calibration` to E (LA-053 / PCL-01 ownership); that preserves the original owner, but does not make the absent dispatch path implicit. Treat the new lease as the proposed exact-path expansion and have G affirm/record it against C09 before source writes. Do not infer permission from the C09 title or from worktree admission.

The four named focused tests, backtesting/calibration READMEs, and release fragment are coherent companions for this slice. The existing `test_evaluator_interval_admission.py` is not in this new exact list; if the repair needs to edit it, amend the lease first. The list is otherwise concrete enough to keep the helper/tests with one C09 writer and the generated-family files with G.

## Admission receipt boundary

The compressed payload’s digest matches the lease receipt (`13,887` stored bytes; `171,103` decoded bytes). It requests **resume** of the existing `codex/e02-E-c09-20261008` at `/dev/shm/e02-orch03-20261008/c09`; the recorded command outputs identify that registered worktree at HEAD `6d470eb884c31a8b19ee06058881cf0deaa492f5`. The earlier ORCH03 C09 resume record at `9a2cc9d` has the same branch/path tuple. This is evidence of an existing attachment, not a new branch or worktree reservation.

The receipt labels its selector predicate `consumer_asserted` and explicitly lists `name_reservation` as unresolved by construction: the read-only observation reserves nothing and is non-atomic. Before execution, G must serialize commissioning, rerun the exact branch/path check immediately before resume/attach, then read back the actual attachment and HEAD. Do not read `status: admitted` as source acceptance or as a reservation.

**Recommendation:** accept these two files as a metadata-only continuation packet, with source authoring still conditional on G recording the explicit `interval_basis.py` path expansion. Keep the interval source HOLD until frozen candidate review and the named affected consumer checks; the new metadata does not close the finding.
