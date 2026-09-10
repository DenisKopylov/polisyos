# C1 durable campaign handoff

Date: 2026-09-09. Campaign source and mirrored tests are frozen at this handoff.
No provider request or credential read was performed by this implementation
subtask. The previous six-input declaration and extractor entry point remain
unchanged. This is the extraction/checkpoint stage; graph finalization and the
operator CLI are separate continuing owners, not completed capabilities here.

## Delivered mechanism and source binding

- `src/polisyos/data_forge/domains/academic/batch/reextraction_campaign.py`
  @sha256:4272e4d2f16ef29f8d0cde8d5ef24b3bf6c4a56c9381fdd2488d59e590dedb20
- `tests/unit/data_forge/domains/academic/batch/test_reextraction_campaign.py`
  @sha256:a525bfc1e71806888e977443f849b38a7124670684b5caed48b19a39f7198cbe

`run_campaign` extends the existing `PolicyArticleExtractor` and `_to_work_record`
owners. It streams the declared complete input frame into an exclusive SQLite
checkpoint and immutable source artifacts before dispatch, then uses a bounded
queue and fixed worker count. The emitted owner-source projection is a finite
path/byte binding, including the transport and actual prompt files; it is not a
claim of complete transitive dependencies or loaded-process attestation.

The admitted frame is immutable: identical source replay is idempotent, a rebound
work identity refuses, and a new identity after admission refuses before any
source artifact or database mutation. `begin_attempt` consumes the admitted frame
binding. Corpus expansion requires another declared campaign. Attempt intent is
durable before dispatch, returned response and usage are durable before parsing,
and unknown in-flight outcomes retain spent attempt budget and unknown usage.
Complete work publication has a durable intended hash; restart adopts published
bytes instead of regenerating their processing timestamp. Only bounded per-work
attempt lineage is materialized; corpus membership, work state and outcomes stay
on disk. This is a construction claim, not a measured large-corpus RSS result.

Raw phase admission uses the existing extraction response validator, exact
Boolean screening, and a typed self-verification response shape. A typed critic
response does not establish claim coverage or entailment. Extraction candidates,
raw claim occurrences and independently emitted campaign artifacts retain their
own synthetic/scope provenance. They grant no scientific or institutional
authority. The injected credential-safe writer is the sole JSON publication
path; the SDK transport owns provider-attempt metadata, while phase checkpoints
own parsed responses and usage.

The run-emitted preservation strangle resolves every completed source/result and
attempt lineage, reconciles the complete iteration with SQL count, then replays
the real processing entry point with a provider client that refuses any new call.
Its digest and attempt-count equality are recomputed. The default legacy
processed-key cache is subordinated within this new entry point only.

## Deciding execution

Every referenced JSON capture retains the exact argv, return code and complete
streams. Commands use package `-m`, the lane venv first in PATH and normal pytest
options. The final exact-file gate is `campaign-frame-final-targets.json`, RC0,
12.729 seconds. `campaign-frame-reconciliation.json`, RC0, independently compares
the complete actual collection with executed JUnit identities: 16/16, equal
identity digest, no missing, duplicate, unexpected or ambiguous identities.
`campaign-frame-ruff.json` is RC0. No full test directory or corpus pass ran.

The final gate includes two actual OS SIGKILL/restart tests. One interrupts a
dispatched extraction: the resumed checkpoint retains one `outcome_unknown`
attempt and unknown usage while the complete artifact and database identity sets
agree. Candidate values equal the uninterrupted control under an explicitly
synthetic processing clock; attempt lineage correctly differs by the interrupted
dispatch. The second kills after actual work-file publication but before SQLite
completion, advances that synthetic clock, and proves the original published
bytes survive unchanged with no repeated completed provider phase.

The strangle test removes actual completed-work and phase-response replay while
retaining markers, then observes
`campaign_checkpoint_replay_strangle_failed`. Its enclosing pytest is RC0 because
it asserts that exception; it is not described as a standalone RC1 command.
The same file exercises malformed phase responses, content/source corruption,
actual writer exclusion, wrong complete-frame digest, immutable membership, and
bounded concurrent use through the real extractor.

## Red evidence and corrections

The retained substantive reds include missing checkpoint/bridge capability,
publication-window `campaign_immutable_artifact_conflict`, rebound work identity,
all raw phase shapes being misreported as extracted, absent run strangle,
unadmitted direct dispatch, and post-admission membership expansion. The final
intake reds are `campaign-dispatch-intake-red.json`,
`campaign-frame-membership-red.json` and `campaign-frame-immutable-red.json`.
P40 classification: these are the same complete-frame predicate class; the final
repair freezes membership at intake and consumes that binding at dispatch.

Earlier non-green attempts remain uncredited: the first SIGKILL launcher used the
wrong module name; the next comparison exposed differing processing timestamps
between fresh runs; the initial source projection named a nonexistent prompts
file; and `campaign-dispatch-final-targets.json` exposed this implementation's
SQLite Row-versus-tuple comparison error. None is called inherited or evidence
of current correctness. Corrections append and the final gate covers both happy
paths and refusals.

## Limits and named homes

The graph stage is `not_started_separate_owner_stage` in the actual report and
belongs to the agreed `graph-capacity.md` owner extension. Existing graph
accumulation is not claimed stream-safe by this campaign. Operator preparation,
authorization and execution surface belongs to `reextraction_cli.py`; live model,
error/cost, throughput and RSS measurements belong to the coordinator's declared
capacity experiments. Synthetic timing proves no provider performance result.
The campaign does not yet implement a fatal-error operational stop policy for a
full run; the bounded pilot enumerates its declared outcomes. Same-model critic
coverage and independent entailment remain `not_established` under P14/P15/P37.

The failure register was reread for closeout. Relevant rules are P01/P02 for the
actual checkpoint/extractor bridge, P27 for owner reuse, P28/P29 for replay
strangling, P35 for complete identity reconciliation, and P37/P38/P40 for the
immutable complete-frame predicate. No A/B/C2 mechanism, receipt epoch, governed
authority rule, debt register or ledger was changed by this subtask.
