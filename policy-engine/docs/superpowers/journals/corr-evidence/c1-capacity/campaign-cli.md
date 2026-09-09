# Campaign CLI decision — 2026-09-09

This entry point makes the existing durable extraction campaign operable for a
future, separately authorized full pass. No live call or full pass is authorized
by this implementation task. A/B/C2 and the completed refusal expansion stay closed.

## Owner and contract

`academic/batch/reextraction_cli.py` owns source selection and command admission.
It delegates canonical work hashing, extraction, attempt budgets, checkpoint
persistence, restart, and completed-work proof to `reextraction_campaign`; the
ordinary `SDKExtractionTransport` and `SafeJsonWriter` remain the sole network and
safe-output owners. This is an experimental operator surface. It does not parse
extraction responses, duplicate a checkpoint, or turn candidates into authority.

`prepare` emits one compact strict plan envelope with `full_pass_authorized: false`
and an empty external authorization reference. It includes a recomputed complete
source frame, full canonical work-stream hash, independently reconciled identity
hash/count, source byte and schema pins, current campaign/CLI source pins, exact
provider endpoint/models, global/per-phase attempt limits, worker/queue limits,
per-work input and artifact byte bounds, and required free disk bytes. It never
copies held raw records into a preparation artifact and never reads credentials.
`run` requires a separately supplied envelope with the explicit full-pass flag and
nonempty external authorization reference. That reference records an operator's
external authorization; it is not a cryptographic institutional appointment or an
independent scientific claim. No source read, credential read, SDK construction,
or output creation occurs for an unauthorized plan, apart from reading the plan
itself. All other bindings are recomputed before credential/network/output use.

The measured held source is `ac_works`. The complete DESCRIBE capture
`campaign-cli-source-schema.json` (RC 0) establishes that this held
`ac_causal_claims_raw` uses `work_id`, not `openalex_id`. Secondary preparation
therefore derives the unique available identity column from those two supported
schema forms and joins DISTINCT claims identities to held `ac_works.id`. When both
columns exist the caller must choose explicitly; neither is silently preferred.
No present corpus count appears in code. The two selectors are all nonblank held
abstracts and distinct claim-bearing identities with nonblank held abstracts.

## Streaming and source binding

DuckDB opens read-only with a declared memory limit and one query thread. One
bounded raw work is transferred at a time, after SQL checks its serialized byte
length; raw records above the declared bound refuse before Python parsing. The
stable pinned snapshot's physical row ordinal orders the stream. A second cursor
walks the complete source independently, filters nonblank abstracts in Python,
and independently derives secondary membership with the distinct-identity join.
The exact selected `(row ordinal, work identity)` streams reconcile member by
member, not by totals. Duplicate/null identities refuse. Hash accumulators retain
constant Python memory; no full identity set or raw-source shadow is retained.
A source WAL is refused so the declared full-file byte hash identifies the actual
read-only snapshot. The same open transaction supplies the admitted run iterator.
The existing campaign may persist its required individual input artifacts; the
CLI adds no second raw corpus copy. Free disk is checked before output creation;
this is an admission check, not a claim of kernel-enforced future disk quota.

Credentials come only from process environment and, if explicitly specified, one
dotenv file with interpolation disabled. Exactly one distinct value matching the
explicit prefix is required. No value, variable name, header, provider body, or raw
exception is printed. The CLI uses bounded constant failure codes. Preparation
uses the existing safe writer with an inert sentinel because it has no credential;
run uses the actual transport safe writer. Neither command writes into the held
source tree, its ancestors, or the source database path.

Graph finalization remains a distinct existing-owner stage. The CLI reports the
campaign's actual `not_started_separate_owner_stage` until the separately owned
graph extension supplies an actual artifact; it never fabricates graph completion.

## Falsifiers and ownership

Red first: an actual module invocation must exist; an unauthorized full plan must
refuse before a deliberately failing credential/transport/output spy. On marked
synthetic DuckDB input, `prepare` and actual existing campaign execution must work,
then a second execution must make no repeated provider calls. Mutating the source,
frame, owner pin, endpoint/model, phase/global budget, or oversized record must
refuse. Unknown inserted identity invalidates an old frame; a new preparation
admits the complete grown source with zero code change. Complete independent
identity reconciliation must survive SQL/row enumeration disagreement by going
red. Remove the authorization or source-match predicate in memory while keeping
plan markers and run the unchanged negative: it must go red.

P27 reuse is explicit; P28 uses the campaign's actual completed-work default and
run-emitted proof rather than adding a second strangle receipt. P29 proof comes
from the actual CLI/owner tests and removals. P35/P37/P38 require whole frame and
source rederivation, not caller counts/hashes. Per-record/queue bounds are actual
mechanism limits; no corpus-count limit is introduced. Authority and independent
correctness remain outside the candidate extraction mechanism.

Write set: the new CLI, its mirrored targeted test, this decision, and new
`c1-capacity/campaign-cli-*` evidence only. Parent owns package README/release and
commits. Campaign and graph owners remain with the other agent. Initial tests use
small synthetic stores and transports; no provider calls or held-corpus run.

Before runtime verification, source ordering was made explicit through fixed pages of 64 physical row ordinals; only that fixed raw page can participate in sorting. Source-wide identity checks retain the declared DuckDB memory limit and refuse resource exhaustion rather than collecting identities in Python. The CLI also persists its exact authorized invocation as an immutable input artifact through `SafeJsonWriter`, so resume cannot silently change context limits, source pins, or the external authorization reference. Progress remains solely in `CampaignCheckpoint`. The CLI source hash stays in its independent envelope; the campaign source projection is unchanged because pilots do not call this entry point.

## Full-run fatal stop and explicit recovery — accepted before implementation

The root approved this additional full-run requirement. The existing campaign
owner must persist a systemic fatal stop when an admitted attempt returns a
declared authentication/request-configuration failure. Its single admission gate
must then prevent new attempts across all workers and restarts. Already admitted
calls may settle; unstarted inputs stay pending, so a failure cannot consume the
entire declared corpus. Its safe summary must expose the stopped state and exact
stop artifact. The CLI will select that declared policy for future full runs.
Historical bounded pilot semantics and their source epochs remain readable.

Recovery is an explicit append-only campaign-owner transition citing the exact
stop reference and an operator acknowledgment/reason. It does not erase the stop,
attempt or retry history. Resuming without that transition dispatches zero new
calls; an accepted recovery preserves completed work and allows the owner to
continue the pending set. The CLI may expose a thin `recover` command only after
that actual owner API exists. No local CLI boolean, hidden retry loop or alternate
checkpoint may clear the stopped state.

The separate `finalize` command will similarly delegate to the actual
`pipeline.finalize_extraction_campaign_graph` and its resolver after that owner
passes its tests. This command has no provider calls and cannot invent a graph
completion marker. Both owner extensions are coordinated with root; active pilot
source pins prohibit editing the campaign during resource measurements.

## Campaign v2 and historical replay — approved 2026-09-09

Root transferred `reextraction_campaign.py` and dedicated fatal/recovery tests to
this workstream after both bounded pilots completed. Current full-run plans use
`execution_epoch: v2` and `fatal_policy: stop_systemic`; their packets use
`policyos.academic.extraction_campaign.v2`. Legacy defaults remain v1 with
`observe_per_work`. One owner plan projection omits the newly added fields only
for legacy v1, preserving its prior hash/serialization semantics. The live
constructor remains bound to current owner bytes.

`CampaignCheckpoint.read_only_history(root, plan)` is a distinct shared-lock,
read-only view over a quiescent historical checkpoint. It validates the original
projected plan, complete stored frame, attempt references and completed artifacts
without requiring current source identity. It cannot create plans, repair rows,
write artifacts or admit attempts. `validate_complete_frame()` supplies the sole
streaming frame validation for both views; the separate graph owner will consume
this history API and label its input `historical_source_epoch`, while separately
binding its own current graph implementation. Reading old evidence is not current
execution or fresh proof attestation.

Fatal stop reconstruction derives from the actual durable failed-attempt packet,
including after an interruption before stop publication. Stop and recovery records
are immutable owner artifacts; SQLite is the existing checkpoint's index. Recovery
binds the exact current stop and operator acknowledgment/reason, covers preceding
settled failures, and preserves all previous records. Recovery does not reset or
silently increase global or per-phase budgets: operators must predeclare retry
capacity if they want to retry a failed phase. Current full-run preparation defaults
to two attempts per phase; exhaustion remains an honest refusal.

## Bounded review corrections — before repair

The recovery finding is the same fatal-stop temporal class one level deeper.
Dispatch order is not settlement order: an earlier outstanding attempt could fail
after a later stop was acknowledged. The sole recovery intake therefore must
require zero `dispatched` attempts before acknowledging the latest stop. The
actual pure-SQLite red (`campaign-recovery-quiescence-red.json`, RC 1) settled the
later admission first and proved the unguarded recovery was accepted. After all
prior admissions settle, exact-stop recovery remains valid and budgets unchanged.

The historical-read finding is the same epoch-readability class. A finished source
may have a valid nonempty SQLite WAL. Rejecting it confuses storage layout with
incompleteness. Root approved a disposable metadata view in separate owner-local
`.tmp/history-views` scratch: hold the existing source shared lock, bound/count
DB+WAL disk requirements, stream-copy those metadata files only, verify original
DB/WAL/SHM byte identities before/after, and let read-only SQLite interpret the
copied WAL. Its scratch-only provenance sidecar is `synthetic: true`, candidate-only,
and separately records the original source synthetic flag. The sidecar does not
relabel or rewrite original work/attempt artifacts and is never a delivered proof.
The view is removed on close. No source WAL checkpoint, deletion, ignored WAL,
current-source restamp, or raw input corpus copy is permitted.

The exact quiescence and valid-WAL controls now pass together in
`campaign-recovery-wal-green.json` (RC 0, 1.748 seconds), against their retained
semantic reds above. Independent bounded review is recorded in
`campaign-v2-independent-review.md`. The later added scratch-sidecar provenance
and deletion assertions still await the final scoped wave; this receipt does not
credit them. The CLI recovery test now exercises the real stopped campaign, its
command parser and the same append-only recovery owner while a provider spy would
fail on any recovery-time call. It is prepared but not yet executed during the
throughput quiet window.

The added sidecar/cleanup control was subsequently executed alone under the
approved short pure-SQLite allowance: `campaign-history-marker-green.json` is
RC 0 in 1.880 seconds. It verifies the disposable view's own synthetic marker,
candidate limitation, original source flag, cleanup and exact original file
bytes/set preservation.

## Remaining source-fidelity discriminator and preparation measurement

The actual held schema contains `trust_score FLOAT`. The transfer must preserve
the native source values used by the existing complete-work hash owner; SQL JSON
decimal rendering must not silently choose a different Python value. A focused
native-value comparison test is prepared before any transfer repair. This is an
unmeasured discriminator until its native-runtime capture, not a claimed finding.

After the quiet window and source freeze, both complete held selectors will be
prepared with wall time and maximum RSS measured by `/usr/bin/time -l`. The compact
templates remain unauthorized and candidate-only. Root selected concurrency 1 for
this measurement, an explicit 2,000,000 total-attempt operational cap and two
attempts per phase. These are preparation inputs, not a throughput recommendation
or permission to spend. Provider/model/concurrency for any later authorizable full
pass must be chosen from its separately reviewed measurements. No present-corpus
count becomes a code limit, and no provider calls occur during preparation.

The native FLOAT discriminator actually passed unchanged in
`campaign-cli-native-value-red.json` (RC 0, 1.831 seconds). Its filename describes
the intended pre-repair probe, not the outcome: the anticipated divergence was
refuted. No value-transfer repair was made. The exact old campaign test file plus
the new recovery/history file pass in `campaign-v2-final-tests.json` (RC 0,
9.137 seconds); independent complete collection/JUnit reconciliation records
21/21 equal identities with no missing, ambiguous, duplicated or nonpassing case
in `campaign-v2-final-identities.json`.

Three in-memory removals keep artifacts and declarations intact. Removing fatal
stop permits all eight constructed inputs to be dispatched after the fatal
failure (`campaign-fatal-stop-removal.json`, RC 1). Removing only the recovery
quiescence predicate allows premature acknowledgment
(`campaign-recovery_quiescence-removal.json`, RC 1). Omitting the actual WAL bytes
from the disposable view loses the committed works table and makes the unchanged
history replay fail (`campaign-wal-removal.json`, RC 1). These are actual semantic
failures; none edits original source files or historical checkpoint bytes.

`campaign-real-pilot-history.json` (RC 0, 1.033 seconds) additionally invokes the
same history reader on the actual finished DeepSeek and MiniMax pilot roots.
Each complete 43-file source set is independently derived by `rglob` and
`os.walk`, then every file is streamed and rehashed before and after replay.
No identity or byte changes occur. DeepSeek's original 440,872-byte WAL is
consumed; MiniMax has no WAL. Both original v1 owner pins and all actual work and
attempt dispositions remain visible, including MiniMax's provider failure.
No source artifacts are copied into tracked evidence. The probe is explicitly a
marked diagnostic, not fresh provider execution or a new authority receipt.

The actual CLI recovery bridge passes in `campaign-cli-recovery-green.json`
(RC 0, 2.573 seconds): the command delegates the exact stop and operator reason,
makes no provider call, retains the failed attempt, and resumes pending work.
The separate finalize bridge's missing-entry red is
`campaign-cli-finalize-entry-red.json` (RC 1, 1.667 seconds). It awaits the graph
owner’s green before implementation, as agreed.

After the separately owned graph API passed its actual seven-case wave, the
approved thin `finalize` bridge was implemented. It consumes the exact immutable
CLI invocation, delegates construction and resolution to the existing pipeline
owner, and emits only the resolved candidate artifact reference. It neither
requires a current extraction owner pin for historical inputs nor grants dispatch
authority to the old pin. It needs no credential or provider call. Optional
capacity configuration uses the existing `GraphCapacityLimits` intake, with a
bounded JSON input, and no duplicate graph algorithm. The first actual incomplete
refusal plus completed-history graph control passes in
`campaign-cli-finalize-green.json` (RC 0, 2.966 seconds). The final wave additionally
routes its happy control through the actual `finalize` command parser.

## Final prepared-source measurements and operator steps

Both measured selections use the complete held DuckDB snapshot. Primary
preparation independently reconciles 310,710 selected work identities, takes
22.776 seconds, and reaches 341,311,488 bytes maximum RSS. Secondary independently
reconciles 65,327 distinct claim-bearing work identities, takes 55.002 seconds,
and reaches 387,579,904 bytes maximum RSS. The complete owner outputs and
`/usr/bin/time -l` streams are retained in `campaign-cli-primary-prepare.json` and
`campaign-cli-secondary-prepare.json`; both are RC 0 with no swaps. The secondary
scan is measurably slower despite a smaller selected set. Its complete independent
claim-membership scans remain part of the work; per-query cost attribution was
not separately measured. These are observed
local preparation costs, not a hard process-RSS bound or a corpus throughput
forecast. No raw source records or identity lists are copied into the compact
plan artifacts.

The exact operational `prepare` command for the primary template was:

```sh
.venv/bin/python -m polisyos.data_forge.domains.academic.batch.reextraction_cli prepare \
  --source production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb \
  --output-root .tmp/corr-c1-capacity/future-primary-run \
  --plan-output .tmp/corr-c1-capacity/prepared-primary.json \
  --selector primary --campaign-id corr-c1-primary-unauthorized-template \
  --screening-model deepseek-ai/DeepSeek-V4-Flash-0731 \
  --extraction-model deepseek-ai/DeepSeek-V4-Flash-0731 \
  --credential-prefix sk-3dd7c527 --concurrency 1 \
  --max-attempts 2000000 --max-attempts-per-phase 2 --min-free-disk-bytes 1073741824
```

The secondary command is identical with `--selector secondary`, campaign ID
`corr-c1-secondary-unauthorized-template`, output root
`.tmp/corr-c1-capacity/future-secondary-run` and plan path
`.tmp/corr-c1-capacity/prepared-secondary.json`. Both exact argument vectors are
in their deciding captures. No current count is encoded into the implementation;
more articles or another same-schema source require a newly prepared complete
frame and a new separately authorized campaign, not an expanded old frame.

**Neither prepared template authorizes a full pass.** Both throughput sweeps
stopped at concurrency 1, so the operating knee is `not_established`. Neither a
production model nor a production concurrency has been selected here. The
template's model names and concurrency 1 are explicit structural preparation
inputs; the full-pass acceptance criteria remain unmet. The following commands
are ready operator surfaces for a future separately architect-authorized plan,
not actions performed or approved by this lane:

```sh
.venv/bin/python -m polisyos.data_forge.domains.academic.batch.reextraction_cli run \
  --plan .tmp/corr-c1-capacity/architect-authorized-primary.json \
  --dotenv /explicit/operator/provided.env

.venv/bin/python -m polisyos.data_forge.domains.academic.batch.reextraction_cli recover \
  --plan .tmp/corr-c1-capacity/architect-authorized-primary.json \
  --stop-path "exact path from fatal_stop_ref" \
  --stop-sha256 "exact sha256 from fatal_stop_ref" \
  --acknowledgment-ref "external operator acknowledgment reference" \
  --reason "operator's concrete repair and reason to resume" \
  --dotenv /explicit/operator/provided.env

.venv/bin/python -m polisyos.data_forge.domains.academic.batch.reextraction_cli finalize \
  --plan .tmp/corr-c1-capacity/architect-authorized-primary.json
```

Omit `--dotenv` to use only the existing process environment. No implicit dotenv
search occurs in the production CLI. It requires one distinct credential with
the declared nonsecret prefix and prints neither that credential nor raw provider
errors. A CLI-level refusal prints a constant safe error. Inspect the exact plan
bindings and, when a campaign exists, its immutable `attempts` packets'
`error_kind`, `retryable` and `status_code`, plus `fatal_stop_ref`; do not infer the
provider cause from the generic CLI message. The campaign owner exposes systemic
`authentication_error`, `request_rejected`, `reported_model_mismatch` and
`unsafe_response_refused` stops. Other declared attempt outcomes remain visible
without being recast as successful extraction.

An unchanged authorized `run` resumes the same checkpoint and never repeats
completed work. The same plan after an active fatal stop dispatches zero new
attempts. `recover` requires all admitted attempts to settle and appends the
exact-stop acknowledgment; it preserves every spent attempt and budget. A source,
budget, delay or owner-pin change cannot silently replace the original invocation.
The template deliberately uses two attempts per phase and a retry delay of zero;
neither setting alters old pilots. For a future plan, root recommends considering
an explicitly declared 30-second retry delay after the new acceptance criteria
are met. That would be chosen before execution and is not a hidden retry or a
present throughput recommendation. `finalize` is separate, makes no provider call,
requires every campaign input to have a completed disposition, and preserves
candidate-only authority even when a graph is produced.

The final exact CLI file passes in `campaign-cli-final-tests.json` (RC 0,
3.442 seconds). Complete collection/JUnit reconciliation in
`campaign-cli-final-identities.json` records 24/24 identical test identities with
no missing, unexpected, ambiguous, duplicated or nonpassing case. This includes
the command-parser finalization positive and its actual incomplete-input refusal.

The final authorization/source-frame removals are retained in
`campaign-cli-authorization-final-removal.json` and
`campaign-cli-source_frame-final-removal.json`; each is RC 1 at the intended
boundary and retains the legitimate prepared-frame positive. The earlier removal
captures remain history. A test spy was changed to discard its arguments before
raising, avoiding pytest's truncated environment representation in a diagnostic
trace; no production predicate changed. Actual module execution of `run` with
the complete unauthorized real-source template refuses in
`campaign-cli-unauthorized-module.json` (RC 1, 1.112 seconds). No full pass, provider
call, recovery on a real pilot, or graph finalization of a real pilot was performed
by this workstream.
