"""Render an independent, conservative proposal from fixed criterion/evidence pins.

Statuses are recommendations for root/G. This script has no closure authority.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
ROOT = "99af508a5282854f3e609c5a94bc19ac55893dde"
REVIEW_SOURCE = "16b1b982471508feef149eefc70203562c6a2a6f"
DECISIONS = {
    "B13": (
        "limited",
        ("Real simulation survives later failure and is correctly consumed through served route."),
        (
            "Real simulation artifact and later-failure prefix "
            "persist; actual served-route attempt stops at "
            "catalog_fetch_source_unreadable before TestClient "
            "consumption."
        ),
        (
            "Readonly native production catalog/acquisition input "
            "and all15 served HTTP negatives unavailable; producer "
            "success is insufficient."
        ),
        "A lifecycle/generation owner + local G",
        {"identity": [5], "cmp": [2]},
    ),
    "B14": (
        "limited",
        (
            "Timeout/cancellation stops owned work or revokes late "
            "current-state publication; delivery success is "
            "distinguished from compute failure."
        ),
        (
            "Real Linux owned descendants are reaped; queued jobs "
            "cancel synchronously; late thread output/owned-write "
            "refusal distinguished from continued raw physical work."
        ),
        (
            "Arbitrary already-running thread/coroutine/external "
            "effects cannot be hard-stopped; native macOS profile "
            "unrun."
        ),
        "RUN + external effect owner + G native platform",
        {"run": [0, 1, 2, 5], "run-process": [0, 1]},
    ),
    "B24": (
        "limited",
        (
            "Small/1MiB process results drain while producer lives; "
            "compute and delivery failures never publish false "
            "success."
        ),
        (
            "Actual framed1MiB, partial Pipe transport, first-handle"
            " setup faults and descendant cleanup controls "
            "distinguish join-before-drain and delivery loss."
        ),
        (
            "Linux supervisor/procfs/pidfd profile established; "
            "native macOS process/adopted-child boundary unrun."
        ),
        "G native platform + RUN",
        {"run-process": [0, 1], "run": [5]},
    ),
    "B37": (
        "closed",
        (
            "Concurrent ledger reads and interrupted publication "
            "yield complete old/new or typed recovery, never "
            "implicit unlimited; sparse wire is refused before "
            "defaults."
        ),
        (
            "Actual child cold public spend refuses missing "
            "bootstrap; explicit unlimited remains valid; fixed23 "
            "wire-field consumer negatives, process concurrent "
            "read/write, fsync/replace/SIGKILL cuts and reopened "
            "middleware cap refusal pass."
        ),
        None,
        "root/G final integrated criterion acceptance",
        {"dur-settlement": [0, 1, 2, 3], "dur-independent": [0, 1, 2], "dur": [0]},
    ),
    "B38": (
        "limited",
        (
            "Actual bound stale worker cannot publish "
            "terminal/progress/event/history/outbox after "
            "owner/attempt/expiry takeover; current owner completes "
            "coherently."
        ),
        (
            "Fresh SQLite processes exercise13 public mutators with "
            "unchanged full rows, currentB completion, "
            "expiry/renew/self-generation rollback and verified "
            "terminal publication; fence removal fails actual "
            "consumer."
        ),
        (
            "Broad10-file378 availability census retains269 missing "
            "catalog/L6 and6 PostgreSQL-without-DSN cases; actual "
            "PostgreSQL/production handler consumers not "
            "established."
        ),
        "DUR + local G actual catalog/DB profile",
        {"dur": [0, 1, 2, 5, 6, 7, 10, 11]},
    ),
    "B39": (
        "closed",
        (
            "Same permanent returned/raised defect has same retry "
            "count; allowed transient faults retry within policy; "
            "unknown external outcome does not blind-retry."
        ),
        (
            "Actual direct/thread/fork/genuine-async classifier "
            "matrix preserves canonical category/code, transient "
            "provider TimeoutError and terminal wrapper expiry."
        ),
        None,
        "root/G integrated retry consumers",
        {"run": [1, 3, 4, 5]},
    ),
    "B40": (
        "limited",
        (
            "One visible effective deadline covers "
            "queue/startup/retry/I/O/publication across sync/async "
            "forms and rejects late current writes."
        ),
        (
            "RUN absolute deadline and unbounded/default "
            "distinctions pass; independent realCAS owner1bd "
            "late-hook cancellation now refuses new "
            "outputs/finalization."
        ),
        (
            "RUN46 and newer EXE1bd are separate checked sources "
            "outside frozen root99af; final owner source/whole "
            "integrated deadline consumer receipt pending."
        ),
        "EXE + RUN + root/G",
        {"run": [0, 1, 2, 5], "exe-owner": [0, 1, 2, 3]},
    ),
    "B42": (
        "closed",
        (
            "Both fresh import orders execute real built two-node "
            "registry chain through common async wrapper; missing "
            "required dependency is diagnostic."
        ),
        (
            "Two actual fresh child import orders produce7→21; "
            "controlled missing async module raises genuine "
            "dependency error rather than permanent unavailable."
        ),
        None,
        "root/G final supported chain profile",
        {"solver": [2], "cmp": [2]},
    ),
    "B43": (
        "closed",
        (
            "Build/freeze/execute consumes ordering-only requires in"
            " one effective graph, preserves independent parallelism"
            " and refuses cycle."
        ),
        (
            "Real required-only chain order, independent "
            "ThreadBarrier pair, true "
            "estimate1→sensitivity→estimate2=31 and ambiguous/cyclic"
            " before-body refusals pass."
        ),
        None,
        "root/G final effective DAG consumers",
        {"solver": [2], "cmp": [0, 2]},
    ),
    "B44": (
        "closed",
        (
            "Static→dynamic→per-call override payload is identical "
            "in sequential/async/checkpoint and native compiled "
            "consumers."
        ),
        (
            "Actual nondefault static/dynamic/override arithmetic "
            "agrees without redundant params_map; changed effective "
            "payload and unknown parameter refuse, real checkpoint "
            "bound-slot output persists."
        ),
        None,
        "root/G supported payload/materialization consumers",
        {"payload": [0, 1], "cmp": [2, 5], "jit": [3, 4]},
    ),
    "B45": (
        "closed",
        (
            "Duplicate scalar target producers cannot silently "
            "last-win by UUID; distinct targets and explicit merge "
            "preserve meaning."
        ),
        (
            "Actual strict duplicate refuses before bodies; WARN "
            "remains visible unexecuted candidate; left10/right20 "
            "explicit merge=30 and neutral UUID controls pass."
        ),
        None,
        "root/G final strict composition acceptance",
        {"solver": [2], "cmp": [2]},
    ),
    "B46": (
        "closed",
        (
            "Ordering uses concrete occurrences, accepting valid "
            "repeated prerequisite and rejecting unsupported early "
            "dependent."
        ),
        (
            "True31 estimate1→sensitivity→estimate2 survives; strict"
            " earlier-dependent and ambiguous future occurrence "
            "refuse before bodies; requires no longer adds every "
            "same-FQN node."
        ),
        None,
        "root/G existing declared ordering-oracle profile",
        {"solver": [2], "cmp": [0, 2]},
    ),
    "B47": (
        "closed",
        (
            "Typed compatibility matching maximizes cardinality then"
            " existing utility; meaningful equivalent optima require"
            " explicit mapping, never lexical choice."
        ),
        (
            "Independent512 finite3×3 graphs×5 integer profiles=2560"
            " exact optimum/alternative comparisons; "
            "flexible/fixed1107, neutral-relabel typed refusal, "
            "explicit711/1107 and exact-name711 actual consumers "
            "pass."
        ),
        None,
        "root/G supported typed compatibility graph",
        {"solver": [0, 1, 2], "cmp": [1, 2]},
    ),
    "B48": (
        "closed",
        (
            "Manual/automatic pair acceptance uses same mandatory "
            "type/unit/shape/contract/semantic rules; final whole "
            "incoming DAG enforces completeness."
        ),
        (
            "Both forbidden modes refuse before bodies; admitted "
            "semantics=21; partial connect+build refuses; full "
            "two-source union=30. Approved oracle boundary change "
            "retained separately from original RED input."
        ),
        None,
        "root/G final pair and whole-DAG admission",
        {"solver": [2], "cmp": [0, 2]},
    ),
    "B49": (
        "closed",
        (
            "Warm current dynamic defaults match cold, old handle "
            "stays unchanged and dynamic-only change reuses same "
            "actual kernel."
        ),
        (
            "Actual nativeJAX coefficient2→3 yields old20/current30 "
            "with one kernel; "
            "source/helper/ABI/static/shape/dtype/backend changes "
            "refuse stale specialization or rebuild as required."
        ),
        None,
        "root/G declared supported JAX specialization profile",
        {"jit": [1, 3, 4], "cmp": [2, 5]},
    ),
    "B50": (
        "limited",
        (
            "Terminal value/error publishes before follower wakeup "
            "and shared cache generation/miss-claim recheck avoids "
            "duplicate useful compile."
        ),
        (
            "Real follower publication/error/deadline/cancellation "
            "and cross-instance flight controls pass; original "
            "final18 has341PASS1FAIL, corrected scheduling barrier "
            "separately has67PASS."
        ),
        (
            "Physical leader cancellation while compilation is "
            "already entered is not established; bound follower "
            "cancellation is established. No false342-green or "
            "inherited-red claim."
        ),
        "CMP/JIT owner + root/G supported cancellation profile",
        {"jit": [1, 3, 4], "cmp": [2, 4, 5]},
    ),
    "B51": (
        "limited",
        (
            "Authorized bounded cache read may reuse paid result "
            "after compute exhaustion; miss/permission/corruption "
            "cannot bypass budget."
        ),
        (
            "Real trace/checkpoint read-budget/run-budget4 controls "
            "and off-loop replay operations pass, with "
            "exhausted-compute warm hit and denied-read refusal "
            "before persisted I/O."
        ),
        (
            "Final journal/alias ownership class and final EXE "
            "source receipt pending; existing recovery cache replay "
            "cannot attest every newly changed state consumer."
        ),
        "EXE + root/G current replay owner",
        {"exe": [0, 2]},
    ),
    "B52": (
        "limited",
        (
            "Real cache read/write/recovery leaves independent "
            "coroutine responsive, shares absolute deadline and "
            "quarantines late cancelled cache publication."
        ),
        (
            "ActualFileSystemCAS trace/checkpoint off-loop ticks, "
            "private-cache ownership, read budget, deadline/cancel "
            "and current owner1bd late-hook CAS publication controls"
            " pass."
        ),
        (
            "Already-entered backend/hook synchronous I/O cannot be "
            "physically interrupted; final EXE journal "
            "successor/merged cohort still pending."
        ),
        "EXE + root/G current store/owner profile",
        {"exe": [0, 2], "exe-owner": [0, 1, 2, 3]},
    ),
    "B53": (
        "closed",
        (
            "Known shape preparation performs no scientific body "
            "work; actual execution uses correct occurrence inputs "
            "and unknown shapes are never invented."
        ),
        (
            "Actual compiled required-alias chain[False/True] and "
            "dtype/materialization readback, declared-shape "
            "body-count and unknown data-dependent-shape refusals "
            "pass; warmup remains separate."
        ),
        None,
        "root/G declared shape and compiled execution profile",
        {"jit": [2, 3, 4], "cmp": [2, 5]},
    ),
    "B55": (
        "limited",
        (
            "Fail-fast rechecks after semaphore acquire, frees every"
            " slot on error/cancellation and preserves "
            "continue/completed outcomes."
        ),
        (
            "Actual saturated semaphore "
            "test_fail_fast_rechecks_cancellation_after_semaphore_acquire"
            " PASS in225 native; source79b try/finally covers "
            "admission and optional record_semaphore_wait."
        ),
        (
            "Existing deciding slice declares per-ID independent "
            "continuation pending; no fresh standalone "
            "removal/metric-fault+cancel denominator for final "
            "successor is published."
        ),
        "EXE + independent root/G semaphore consumer",
        {"exe": [2]},
    ),
    "B57": (
        "open",
        (
            "Replay applies actual assignments including same-value "
            "writes to current base without resurrecting "
            "unrelated/removed fields."
        ),
        (
            "Independent3b81 declared journal/list controls PASS; "
            "actual pop-append/cross-alias/reparent lifetime escapes"
            " remain under repair. Whole284 retains278PASS6FAIL with"
            " exact premises; one old initial_shared_dict_alias row "
            "lacks a post-constructor alias premise and is "
            "NOT_ESTABLISHED, not a source bug."
        ),
        (
            "Final lifetime/memo source and matched typed-base alias"
            " oracle pending. ExperimentState construction can split"
            " aliases; set/assert alias after constructor before "
            "branch. Default scopeFalse versus producer entryTrue is"
            " a changed input profile, never unchanged driver."
        ),
        "EXE writer + RUN independent alias/lifetime reviewer",
        {"exe": [2], "sta": [0, 1, 2]},
    ),
    "B58": (
        "open",
        (
            "Delete/null/no-write replay preserves allowed deletion "
            "and refuses protected-index removal with explicit "
            "conflict semantics."
        ),
        (
            "Declared tree/list delete/null and unchanged protected "
            "evidence controls PASS on3b81; broader shared "
            "graph/held-live-container escape remains part of same "
            "journal publication class."
        ),
        (
            "Final generic alias/reparent lifecycle invariant and "
            "accepted source/consumer receipt pending; no global "
            "journal closure from tree-only controls."
        ),
        "EXE writer + RUN independent alias/lifetime reviewer",
        {"exe": [2], "sta": [1, 2]},
    ),
    "B59": (
        "closed",
        (
            "Declared nested mutable subtree isolates base/neighbor "
            "before commit and failed branch leaves no nested trace;"
            " unrelated immutable subtree may stay shared."
        ),
        (
            "Fresh native "
            "test_branch_state_deeply_isolates_nested_elements_of_declared_leaf"
            " and deep snapshot controls PASS; historical closed "
            "bounded regression is retained."
        ),
        None,
        "root/G declared branching regression scope",
        {"exe": [2]},
    ),
    "B60": (
        "open",
        (
            "Existing adaptive bundle is loaded and checked for "
            "actual context/graph/required parameters; inaccessible "
            "ref never gives presence-only ok."
        ),
        (
            "Author reports actual6 resolver cases within48 "
            "companion onb647/production1bd, but deciding bytes "
            "remain uncommitted ignored scratch; no published per-ID"
            " new consumer receipt."
        ),
        (
            "verification_not_established for this intake; publish "
            "source-bound actual resolver "
            "context/required-parameter/unavailable-ref outputs "
            "before adjudication. No new implementation defect "
            "inferred from absence."
        ),
        "EXE author + root/G actual resolver consumer",
        {"exe": [2]},
    ),
    "B61": (
        "held",
        (
            "Cache key and actual SKG read bind same "
            "immutable/versioned consumed snapshot; changed live "
            "source is never silently reused."
        ),
        (
            "No immutable/versioned SKG data_record and consumed "
            "query/run/custody contract is admitted; prepared "
            "same-read-handle design does not supply authority."
        ),
        (
            "Standing source-owner semantic contract and actual "
            "consumed stable snapshot required; fixture/file hash "
            "cannot invent it."
        ),
        "SKG semantic/source owner + local G + EXE",
        {"exe": [2]},
    ),
    "B62": (
        "open",
        (
            "Declared method input key preserves "
            "missing/null/0/False/empty distinctions, safe "
            "cache-version compatibility and meaningful current-base"
            " replay."
        ),
        (
            "Real default5 presence-aware method/cache/warm/reopened"
            " results PASS on3b81; journal alias/reparent ownership "
            "class still unfrozen and same-class state-operation "
            "escape known."
        ),
        (
            "Freeze successor current graph lifetime law and replay "
            "unchanged independent presence/alias consumer; no full "
            "closure from key-only equality."
        ),
        "EXE writer + RUN independent graph/lifetime reviewer",
        {"exe": [2], "sta": [4]},
    ),
    "B63": (
        "limited",
        (
            "Successful exact ArtifactRef trace/checkpoint "
            "duplicates are read once; "
            "failed/conflicting/profile/tenant refs never become "
            "admitted hits."
        ),
        (
            "Actual100A+1B filesystem read denominator and native "
            "trace reopen retain four-field selected refs; foreign "
            "producer-view including legacy outcome_ref refusals and"
            " failed-load retry pass."
        ),
        (
            "Final EXE state replay/lifetime successor not frozen; "
            "external-store thread affinity/Ray/Temporal paths are "
            "outside measured concreteFileSystemCAS intake."
        ),
        "EXE + root/G exact ref recovery consumer",
        {"exe": [0, 2], "required": [3]},
    ),
    "B64": (
        "closed",
        (
            "Supported named prompt reaches provider once; "
            "user/system/messages preserve meaning and incompatible "
            "forms refuse before external action."
        ),
        (
            "Actual generic accepting provider receives "
            "named/positional prompt once; competing forms fail "
            "before provider; no invented mandatory production "
            "prompt caller."
        ),
        None,
        "root/G supported LLM protocol input",
        {"adapters": [2]},
    ),
    "B65": (
        "closed",
        (
            "Optional metrics/tracing failure preserves obtained "
            "provider response; mandatory accounting failure retains"
            " unknown event and blocks uncontrolled new spend."
        ),
        (
            "Actual optional start/body/exit failures preserve "
            "provider answer; mandatory same-event callback "
            "reconciliation blocks provider2 and property-removal "
            "controls fail defining assertions."
        ),
        None,
        "root/G mandatory callback and durable settlement consumer",
        {"adapters": [2, 8, 14]},
    ),
    "B66": (
        "closed",
        (
            "Miss/hits/followers keep one actual provider cost "
            "event, separate reuse identity and durable idempotent "
            "producer settlement surviving caller cancellation."
        ),
        (
            "Actual configured factory→cache "
            "producer→Traced→enforcer→initializedFileBudgetLedger "
            "fresh reopen charges0.02 once; receiver/issuer/type "
            "negatives bill physical completions, same-event ACK "
            "resolve/dedupe and lost-ACK unknown controls pass."
        ),
        None,
        "root/G actual configured typed cost/ledger profile",
        {
            "adapters": [2, 6, 12, 13, 15, 16, 17, 18],
            "receiver": [0, 1, 2],
            "dur-settlement": [0, 2, 3],
        },
    ),
    "B67": (
        "held",
        (
            "Reuse authorization binds actual "
            "principal/scope/purpose/epoch and exact verified "
            "evidence/model/request at every read/publication."
        ),
        (
            "Functional injected owner fixture verifies realCAS "
            "bytes and actual actor/ref/epoch; "
            "declaration/type/liveURL/revocation negatives refuse."
        ),
        (
            "Institutional production permission grant and atomic "
            "owner-epoch contract not established; CAS readability "
            "or local functional policy cannot confer it."
        ),
        "Deployment permission owner + local G",
        {"adapters": [2, 7, 10]},
    ),
    "B68": (
        "held",
        (
            "Permitted exact scoped identical misses have one "
            "producer event; follower cancellation, error, deadline "
            "and distinct intentional repetitions preserve "
            "ownership."
        ),
        (
            "Actual4follower one-call behavior, distinct "
            "seeds/principals/accounting owners, physical settlement"
            " before wakeup and atomic producer deadline/cache "
            "admission pass."
        ),
        (
            "Production permission premise remains B67-held; final "
            "B66 joint settlement consumer acceptance required. "
            "Foreign cache signature alone is not conformance."
        ),
        "Permission owner + adapters + root/G",
        {"adapters": [2, 6, 9, 10, 19, 20]},
    ),
    "B69": (
        "closed",
        (
            "Shared executor rejects saturated reentry or admits "
            "bounded useful work; callbacks/queued "
            "cancellation/shutdown cannot create hidden occupied "
            "capacity."
        ),
        (
            "Actual ownedFuture callback barrier/late "
            "registration/context/order/error/cancel plus "
            "shutdown-lock progress and physical worker accounting "
            "controls pass; guard removal fails same meaningful "
            "capacity oracle."
        ),
        None,
        "root/G canonical shared executor consumers",
        {"run-executor": [0, 1, 2, 3], "run": [5]},
    ),
    "B70": (
        "open",
        (
            "Original functional fingerprint survives two real "
            "interrupted resumes and complete reopen without "
            "reexecuting successfulA/B; changed request refuses."
        ),
        (
            "RealFileSystemCAS two interruptionA→B→C and changed "
            "invocation controls pass at e56/3b81, but same-class "
            "state graph/lifetime successor is pending after known "
            "journal escapes."
        ),
        (
            "Reopen and replay unchanged complete independent "
            "alias/current-base/resume inputs on final accepted EXE "
            "successor; do not attribute old PASS to future source."
        ),
        "EXE + RUN independent reviewer + root/G",
        {"resume": [0], "sta": [3, 4]},
    ),
    "B71": (
        "limited",
        (
            "Sufficient checkpoint state needs no irrelevant "
            "cache-count seed; truly required selected external "
            "output is verified/repaired or refused before suffix."
        ),
        (
            "Real producer→CASCheckpointHook→reopen tests8: "
            "healthy/optional and missing/corrupt/selected-profile "
            "required refs; same-input baseline2PASS6FAIL, candidate"
            " within71PASS; explicit repair traverses validated "
            "cache."
        ),
        (
            "Final EXE journal/source receipt and integrated exact "
            "required-output consumer wave pending; no universal "
            "arbitrary blob availability or service permission "
            "inferred."
        ),
        "EXE + root/G exact required-ref consumer",
        {"required": [0, 1, 2, 3]},
    ),
    "B72": (
        "closed",
        (
            "Native skip is not silently successful producer; "
            "single/parallel widths and later checkpoints preserve "
            "same completed frontier meaning."
        ),
        (
            "Actual "
            "single_skip_is_not_added_to_checkpoint_completed_set "
            "and "
            "independent_neighbor_does_not_promote_parallel_skip_to_completed"
            " pass; ok/fail paths remain native distinct statuses."
        ),
        None,
        "root/G canonical completion journal consumer",
        {"exe": [2], "resume": [1]},
    ),
    "B73": (
        "limited",
        (
            "Checkpoint state, completed frontier and cache refs "
            "describe same committed generation; fail-fast "
            "rollback/continue and retained result are coherent."
        ),
        (
            "All4 actual spawn process publication cuts/policies "
            "reached; reopened original input/state/frontier/cache "
            "readback matches; deliberate left-frontier removal "
            "fails real assertion."
        ),
        (
            "Newer owner1bd suppress-cancel late-hook controls now "
            "pass but final full EXE state/journal successor and "
            "joint-source frontier wave still pending. Entered "
            "durable I/O is not physically preempted."
        ),
        "EXE + root/G final checkpoint owner",
        {"resume": [1, 2], "exe-owner": [0, 1, 2, 3]},
    ),
    "B74": (
        "limited",
        (
            "Checkpoint strict admission binds effective "
            "plan/input/seed/occurrences, actual supported "
            "implementation graph and exact scoped supplied refs to "
            "same generation."
        ),
        (
            "Actual static helper cold7→10/stale resume7 baseline "
            "FAIL; unchanged successor typed-refuses before "
            "suffix/pointer mutation. "
            "Source/ABI/ref-view/tenant/cell/origin/config/dependency"
            " negatives and unchanged positive pass."
        ),
        (
            "Finite inspectablePython graph and declared refs only; "
            "imported module/builtin versions and context=None do "
            "not establish arbitrary mutable source/data or "
            "decoder/publication authority."
        ),
        "CMP + root/G exact declared source/artifact context",
        {"identity": [1, 2, 3, 4], "source-graph": [0], "cmp": [2]},
    ),
    "B75": (
        "closed",
        (
            "Per-node history restores original "
            "output/seed/runtime/warnings; legacy missing records "
            "remain explicitly incomplete and cannot supply absent "
            "bound predecessor."
        ),
        (
            "Actual outputs6/7 retain separate original records; "
            "false/missing/unknown history headers stay incomplete "
            "through continuation/re-persist; required missing "
            "predecessor refuses before suffix."
        ),
        None,
        "root/G concrete Foundry history consumer",
        {"payload": [0, 2], "identity": [3], "cmp": [2]},
    ),
    "B76": (
        "closed",
        (
            "All JSON/NumPy checkpoint sidecars belong to one "
            "immutable generation; path collision, fault, concurrent"
            " writer or process stop never mix acknowledged old/new."
        ),
        (
            "Actual a_b versusa→b, finite-codec refused inputs, "
            "process writer/reader, sidecar/publication/fsync faults"
            " and same-step concurrent generation controls pass; "
            "original/rootnamespace failures retained."
        ),
        None,
        "root/G supported local filesystem checkpoint codec",
        {"publication": [0, 1, 2], "cmp": [2]},
    ),
    "B77": (
        "limited",
        (
            "Declared independent successor starts when its own "
            "predecessors complete; realB dependency/read-write "
            "overlap retains barrier and scientific inputs/seed "
            "remain unchanged."
        ),
        (
            "Actual "
            "independent_successor_starts_before_slow_sibling, "
            "declared_dependency and unordered_read_write_overlap "
            "controls PASS with native state-launch/journal guards."
        ),
        (
            "Final shared graph/alias lifetime publication invariant"
            " and per-ID successor receipt pending; no authority for"
            " hidden mutable dependencies."
        ),
        "EXE + root/G readiness/current-state consumers",
        {"exe": [2]},
    ),
    "B78": (
        "held",
        (
            "Pre-dispatch fallback is authorized separately; "
            "post-dispatch lost response reconciles actual external "
            "status/idempotency instead of duplicating effect."
        ),
        (
            "Actual typedPrimaryExecutionOutcomeUnknownError "
            "prevents second persistedSQLite+CAS logical effect; "
            "removal gives2 materialFAIL. Healthy/unhealthy/probe "
            "policies pass."
        ),
        (
            "Authoritative external primary "
            "status/idempotency/reconciliation contract absent; "
            "local typedUnknown correctly holds, not fabricated "
            "remote confirmation."
        ),
        "External primary service owner + local G + DUR",
        {"dur": [0, 8, 9]},
    ),
    "B87": (
        "open",
        (
            "Stream subscribe/checkpoint/rewind/close/cancel "
            "transfers pending physical cleanup ownership and leaves"
            " no permanently occupied pool slot."
        ),
        (
            "Fresh "
            "realFileEventStreamConnector+FileSystemCAS+CursorStore "
            "producer cap3 restore undercap1 actual1FAIL (healthy "
            "control passes); B pool ownership half is established."
        ),
        (
            "C alone owns streaming.py; real pending "
            "checkpoint/cap/recovery consumer defect remains "
            "actualFAIL. Pool package PASS cannot replace it."
        ),
        "C stream consumer + local G",
        {"stream": [0, 1], "adapters": [0, 3]},
    ),
    "B89": (
        "closed",
        (
            "Permit/handle is transferred or retired exactly once "
            "under lock/connect/health/disconnect cancellation and "
            "closed-pool release."
        ),
        (
            "Actual event-controlled connectors retire physical "
            "handle before permit release, retain failed cleanup for"
            " retry and distinguish double-release/late "
            "registration; physical/pool removal oracle fails."
        ),
        None,
        ("root/G concrete pool lifecycle; C stream bridge remains separateB87"),
        {"adapters": [0, 2, 3, 13]},
    ),
    "B90": (
        "closed",
        (
            "Network work is outside metadata lock; independent "
            "release proceeds and one absolute acquisition "
            "deadline/epoch gates atomic late publication."
        ),
        (
            "Actual independent connect/release, metadata-lock "
            "expiry and cancellation-suppressing late connector "
            "controls refuse before handle publication; no await "
            "follows transfer."
        ),
        None,
        "root/G concrete connector protocol",
        {"adapters": [0, 2, 3]},
    ),
    "B91": (
        "closed",
        (
            "Unit capacity remains separate from fractional rate; "
            "impossible/nonfinite weights refuse before "
            "wait/provider and cooldown/cancel preserve law."
        ),
        (
            "Actual fake-clock0.1/0.2/1/>1 and defaultunit capacity,"
            " weighted request, cooldown/cancellation and physical "
            "decorator refusal controls pass; finite-rate "
            "baselineFAIL→successorPASS."
        ),
        None,
        "root/G declared generic rate/source quota profile",
        {"adapters": [1, 2, 11, 21, 22]},
    ),
    "B92": (
        "closed",
        (
            "Finalization belongs to admitted circuit generation; "
            "old success/failure preserves provider outcome without "
            "voting on new half-open generation."
        ),
        (
            "Actual oldCLOSED and oldHALF_OPEN, current probe, "
            "cancellation and duplicate-finalization controls "
            "preserve source result and correct active tokens."
        ),
        None,
        "root/G declared circuit lease profile",
        {"adapters": [0, 1, 2]},
    ),
    "B93": (
        "held",
        (
            "TTL/pressure never evicts active/cooldown/balance "
            "history into a second independent regulator; safe "
            "quiescent eviction remains bounded."
        ),
        (
            "Real decorator await/retry lease, exact-key concurrent "
            "state, cooldown/half-open/pressure and cancellation "
            "controls pass; registry-property removal fails actual "
            "assertions."
        ),
        (
            "Historical finding ledger mapping differs from "
            "immutable canonical regulator criterion; G/ledger "
            "semantic owner must reconcile declaration, not rewrite "
            "it from package PASS."
        ),
        "G + standing ledger/permission owner",
        {"adapters": [1, 2, 4]},
    ),
    "B94": (
        "closed",
        (
            "Versioned typed wire preserves "
            "Decimal/budget/union/nested/ref/outcome values and "
            "rejects nonfinite/unsupported/digest corruption "
            "consistently under both backends."
        ),
        (
            "Actual strictstate_wire.v2/outcome_wire.v2 roundtrips "
            "both JSON encoders and real nestedfork state/outcome "
            "consumer; Decimal type and nativeRef preserved; wire "
            "removal gives definingFAIL."
        ),
        None,
        ("root/G supported codec; Ray/Temporal services are not needed to prove codec"),
        {"adapters": [0, 2, 5], "run": [5, 9]},
    ),
    "B95": (
        "closed",
        (
            "Each actual task submission captures current context; "
            "repeated A/B/empty work in same worker never leaks "
            "prior context or invents permissions."
        ),
        (
            "Actual7-boundary attempt files and9 A/B/empty "
            "artifact-consumer rows on reusedthread preserve caller "
            "scope and transfer; forced thread fallback is real, "
            "Linuxfork separately exercised."
        ),
        None,
        "root/G declared context transport profile",
        {"run": [1, 5, 10]},
    ),
    "B96": (
        "closed",
        (
            "Each retry starts from same isolated baseline; "
            "successful result matches cold while failed history and"
            " actual known typed expenses are retained once."
        ),
        (
            "Real mutation→failure→success and8route known-budget "
            "settlement consumer/control matrices preserve one "
            "ordinary effect and exactDecimal expense/history "
            "through canonicalWIRE transport."
        ),
        None,
        (
            "root/G declared retry and budget projection; external "
            "effect owner retains unknown effects"
        ),
        {"run": [5, 6, 7, 8, 9]},
    ),
    "B148": (
        "held",
        (
            "Verified private staging/admission preserves oldCAS on "
            "bad/conflicting/truncated/concurrent import; owner "
            "decides scoped same-view retry law before publication."
        ),
        (
            "Actual bounded pre-stage lease preflight rejects "
            "unbound/foreign scoped import; exact "
            "same-owner/view/profile/signature/bytes retry is no-op."
            " Legacy unbound-to-scoped positive remains1FAIL."
        ),
        (
            "Public cross-tenant/owner semantics are a "
            "recommendation, not ratified law; explicit legacy "
            "positive requires owner decision, no XFAIL/waiver."
        ),
        "CAS semantic ownership owner + G",
        {"cas-admission": [0, 1, 2, 3], "cas": [2]},
    ),
    "B149": (
        "limited",
        (
            "Replacement export has exact new inventory; "
            "A→B/options/fault/path entry changes preserve previous "
            "complete generation without staleA members."
        ),
        (
            "Actual Linux renameat2 generation, transfer independent"
            " importer, signature/inventory, special entry and "
            "concurrent fault controls pass."
        ),
        ("Darwin renamex_np native target profile unrun; no non-atomic fallback claimed."),
        "CAS + G nativeDarwin transfer consumer",
        {"cas": [2]},
    ),
    "B150": (
        "closed",
        (
            "Returned ref and selected persisted manifest profile "
            "match actual first-writer view; equalbytes different "
            "provenance retains separate meaningful views."
        ),
        (
            "Historical closed bounded ref/profile law retained; "
            "actualCachingArtifactStore selected-view/exactbyte "
            "write-through controls prevent conflating default and "
            "selected profile."
        ),
        None,
        "root/G exact CAS reference/profile consumer",
        {"cas-put": [0], "cas-admission": [2], "cas": [2]},
    ),
    "B151": (
        "closed",
        (
            "Public duplicateput never confirms corrupt existing "
            "blob/wrong selected byte_size; legitimate "
            "missing-sidecar repair yields immediately readable "
            "verified result."
        ),
        (
            "Actual5 put filesystem controls plus independently "
            "authored real root oracle readback/refusal and property"
            " removal distinguish successful retry from consumer "
            "failure."
        ),
        None,
        "root/G concrete publicFileSystemCAS put/get/verify",
        {"cas-put": [0, 2], "dur-independent": [1, 3, 4], "cas": [2]},
    ),
    "B152": (
        "closed",
        (
            "Size/hash/signature/report consume same independently "
            "computed immutable byte+manifest snapshot while "
            "trust/revocation/current access remain enforced."
        ),
        (
            "Independent actual signedbyteswap, wrongsize, "
            "symlink/FIFO/socket, revoked/untrusted keys, tenantA/B "
            "and real quality reports/GC controls pass; stale second"
            " manifest/read never supplies signature authority."
        ),
        None,
        "root/G concrete FileSystemCAS snapshot/report consumer",
        {"cas-snapshot": [0, 1], "snapshot-independent": [0, 1, 2], "cas": [1, 2]},
    ),
    "B153": (
        "closed",
        (
            "Resident local lock ownership is bounded without "
            "evicting active same-key holder/waiter or losing "
            "scoped-view mutual exclusion."
        ),
        (
            "Historical closed striping regression preserved; actual"
            " competing import/writer lease admission and same-key "
            "controls preserve local first-writer semantics."
        ),
        None,
        "root/G cooperating local CAS lock consumers",
        {"cas-put": [0], "cas-admission": [2], "cas": [2]},
    ),
    "B154": (
        "limited",
        (
            "Typed per-item complete/aborted batch preserves "
            "local/global/cancel results; all-confirmations "
            "publisher requires exact full valid report before "
            "publication."
        ),
        (
            "Actual signedcrypto/CLI/import-integrity "
            "producer+consumer controls and all8 completeness "
            "removals distinguish complete/partial/aborted; unsigned"
            " integrity importer does not fabricate signature "
            "authority."
        ),
        (
            "Actual A all-signature-confirmations publisher missing;"
            " typedrequire_complete_valid API and tests are "
            "producer/contract, not consumer closure."
        ),
        "A actual signature all-confirmations publisher + G",
        {"cas": [0, 1, 2, 3, 10]},
    ),
    "B155": (
        "limited",
        (
            "Producer advancement and pending window are bounded "
            "together; cancellation/deadline stop new intake while "
            "exact admitted result identities remain complete."
        ),
        (
            "Actual finite/infinite child "
            "duplicate-source,40-itempending window, real "
            "defaultcensus cancel/deadline controls pass; "
            "stop/window removals fail actual cases."
        ),
        (
            "One arbitrary already-entered next/iter/filesystem "
            "syscall or callback cannot be physically preempted; "
            "complete returned details/seen set remainO(N)."
        ),
        "CAS + root/G declared iterator/filesystem profile",
        {"cas": [0, 4, 5, 7]},
    ),
    "LA-057": (
        "limited",
        (
            "Only incidental moduleT/TypeVar cleanup preserves four "
            "local generic identities, imports/context/cancel/bridge"
            " and supported consumers/tooling/package compatibility."
        ),
        (
            "Fresh198 already lacks moduleT; full6444-file "
            "scope-aware Python/type-config census and "
            "correct-namespace native "
            "typehint/direct/loop/context/cancellation consumers "
            "preserve intended law."
        ),
        (
            "No new deletion claimed; opaque computed "
            "reflection/imports and actual installed "
            "distribution/API consumer profile remain G97-local "
            "obligations."
        ),
        "G installed distribution consumer + RUN",
        {"run": [5, 11, 12], "run-executor": [2]},
    ),
}


def identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "path": PLAN + "current-all60-independent-evidence/" + path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def main() -> None:
    denominator = json.loads((HERE / "denominator.json").read_text())
    catalog = json.loads((HERE / "evidence-catalog.json").read_text())
    if not set(DECISIONS) == {row["finding_id"] for row in denominator["findings"]}:
        raise ValueError("metadata invariant failed")
    rows = []
    for owned in denominator["findings"]:
        finding = owned["finding_id"]
        proposal, criterion, observed, residual, owner, refs = DECISIONS[finding]
        checks = []
        for key, indices in refs.items():
            receipt = catalog["receipts"][key]
            for index in indices:
                check = receipt["checks"][index]
                checks.append(
                    {
                        "catalog_key": key,
                        "index": index,
                        "receipt_git_sha": receipt["git_sha"],
                        "receipt_path": receipt["path"],
                        "check_pointer": check["receipt_pointer"],
                        "executed_source_sha": check["target_sha"],
                        "executed_source_tree": check["target_tree"],
                        "environment_input_command_output": PLAN
                        + "current-all60-independent-evidence/evidence-catalog.json"
                        + f"#/receipts/{key}/checks/{index}",
                        "observed_outcome": check["outcome"],
                    }
                )
        technical = proposal
        if finding in {"B38", "B40", "B51", "B52", "B63", "B68", "B71", "B73", "B154"}:
            technical = "closed"
        if finding in {"B67", "B148"}:
            technical = "limited"
        if finding in {"B78", "B93"}:
            technical = "closed"
        rows.append(
            {
                "finding_id": finding,
                "bundle_id": owned["source_closure_owner"],
                "historical_source_status": owned["source_status"],
                "canonical_criterion": owned["criterion"],
                "criterion": criterion,
                "technical_property_proposal": technical,
                "technical_scope": (
                    "Only the named concrete supported runtime/input/owner "
                    "profile and observed discriminator; no universal "
                    "backend, permission or scientific authority inferred."
                ),
                "finding_status_proposal": proposal,
                "actual_distinguishing_observation": observed,
                "deciding_checks": checks,
                "baseline_navigation_cell_ids": owned["baseline_cell_ids"],
                "remaining_consumer_or_contract": residual,
                "next_owner": owner,
                "closure_applied": False,
                "root_joint_source_acceptance": "pending",
                "closure_reason": (
                    "Proposal concerns criterion semantics, not a formal "
                    "ledger write; root/G reconcile exact final "
                    "source/cohort before applying any closure."
                ),
            }
        )
    newer = []
    for sha, purpose in [
        (
            "1bd1fd11b683bbade5411a71b02706ea206b149d",
            (
                "EXE owner/deadline source, independent realCAS packet "
                "available; final journal/owner receipt pending"
            ),
        ),
        (
            "3b81bf197be10e20208f8d1925fd8d63eca74da9",
            (
                "EXE intermediate journal source with positive and "
                "actual escaping consumer evidence; not accepted final "
                "lifetime source"
            ),
        ),
        (
            "d71be6cbfcd34ca95e0763bc41d565f47d7d8d76",
            (
                "CMP latest published source; algorithm-equivalent54ef "
                "with exact test/oracle correction separated"
            ),
        ),
        (
            "54efb24d87ef9b50beba0e9e8d2ca5bef6bbb96f",
            ("Independently tested weighted matching and actual15 registry consumers"),
        ),
    ]:
        # Fixed Git executable and immutable repository metadata arguments; no shell.
        tree = subprocess.check_output(  # noqa: S603
            ["/usr/local/bin/git", "rev-parse", sha + "^{tree}"], text=True
        ).strip()
        ancestor = (
            # Fixed Git executable and immutable repository metadata arguments; no shell.
            subprocess.run(  # noqa: S603
                ["/usr/local/bin/git", "merge-base", "--is-ancestor", sha, ROOT], check=False
            ).returncode
            == 0
        )
        newer.append(
            {"sha": sha, "tree": tree, "purpose": purpose, "ancestor_of_root99af": ancestor}
        )
    output = {
        "schema": "policyos.e02.implementation_handoff.v1",
        "unit": "B",
        "independent_schema": "polisyos.e02.B.current-all60-independent-adjudication.v1",
        "slice": "current-all60-independent-adjudication",
        "slice_base_sha": REVIEW_SOURCE,
        "implementation_commits": [
            subprocess.check_output(["/usr/local/bin/git", "rev-parse", "HEAD"], text=True).strip()
        ],
        "candidate_tree_sha": subprocess.check_output(
            ["/usr/local/bin/git", "rev-parse", "HEAD^{tree}"], text=True
        ).strip(),
        "branch": "codex/e02-B-current-durability",
        "pull_request": "https://github.com/DenisKopylov/polisyos/pull/43",
        # Fixed Git executable and immutable repository metadata arguments; no shell.
        "changed_paths": subprocess.check_output(  # noqa: S603
            ["/usr/local/bin/git", "diff", "--name-only", REVIEW_SOURCE, "HEAD"], text=True
        ).splitlines(),
        "bundle_ids": sorted({row["bundle_id"] for row in rows}),
        "baseline_cells": denominator["baseline_cells"],
        "checks": [
            {
                "command": [sys.executable, PLAN + "current-all60-independent-evidence/" + script],
                "target_sha": subprocess.check_output(
                    ["/usr/local/bin/git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "environment": {
                    "cwd": "/workspace/e02-B-current-durability",
                    "python": sys.version,
                    "python_executable": sys.executable,
                    "git_executable": "/usr/local/bin/git",
                    "execution_kind": (
                        "read-only Python stdlib/Git metadata reconciliation; no"
                        " product runtime execution"
                    ),
                },
                "input_closure": {
                    "root_source_sha": ROOT,
                    "canonical_card_sha": "69780761ae091d8fcc6ab8778c7f5f7227eeef0b",
                    "immutable_receipts": len(catalog["receipts"]),
                    "exact_git_blobs": catalog["unique_check_artifacts"],
                    "script": identity(HERE / script),
                },
                "outcome": "PASS",
                "output": identity(HERE / artifact),
            }
            for script, artifact in [
                ("denominator.py", "denominator.json"),
                ("audit_evidence.py", "evidence-catalog.json"),
            ]
        ],
        "property": {
            "statement": (
                "Exactly all60 owned canonical criteria join immutable "
                "source/evidence and independently proposed bounded "
                "statuses without applying closure."
            ),
            "runtime_path": [
                "canonical TSV/cards and original runtime receipts",
                "committed source/output-byte catalogue",
                "independent semantic reconciliation",
                "root/G final cohort and owner decision",
            ],
            "proxy_divergence": (
                "Baseline green cells do not attest a newer source; old "
                "initial_shared_dict_alias row lacked the actual "
                "post-constructor alias premise and is not source-bug "
                "evidence."
            ),
            "negative_controls": [
                "Actual C cap1 FAIL retained",
                "CAS unbound-to-scoped compatibility FAIL retained",
                (
                    "missing A publisher/external "
                    "reconciliation/institutional permission stay "
                    "unestablished"
                ),
            ],
        },
        "predicate_basis": "independently_reconciled",
        "capability_state_or_finding_state": (
            "Proposal only; no formal closure applied; final root cohort/source acceptance pending."
        ),
        "limitations_and_next_owner": [
            (
                "Root/G reconcile final accepted source/cohort; standing"
                " A/C, permission/cross-tenant and external-service "
                "owners remain authoritative."
            ),
            (
                "No product runtime rerun or new source acceptance "
                "inferred by this metadata-only intake."
            ),
        ],
        "reviewer": "/root/dur_probe",
        "mode": (
            "Independent read-only evidence/criterion adjudication "
            "proposal; no runtime reruns/source writes/new "
            "trees/helpers."
        ),
        "root_source_sha": ROOT,
        "root_source_tree": denominator["root_source_tree"],
        "own_review_source_sha": REVIEW_SOURCE,
        "own_review_source_tree": "23d8e038716a43ef19e8ffbaf8a08fa0a2ebd169",
        "root_source_qualification": (
            "root99af is a source snapshot, not an executed "
            "all-green cohort. Newer EXE/CMP exact source/check pins"
            " are separate; no future SHA or transitive PASS "
            "attribution."
        ),
        "newer_exact_owner_source_refs": newer,
        "denominators": denominator["counts"],
        "finding_status_proposal_counts": dict(
            Counter(row["finding_status_proposal"] for row in rows)
        ),
        "technical_property_proposal_counts": dict(
            Counter(row["technical_property_proposal"] for row in rows)
        ),
        "formal_closure_authority": (
            "root/G final accepted source/cohort plus standing semantic/source owners"
        ),
        "closure_ids": [],
        "publication_status": (
            "Commit/remote hash is supplied by append-only topic "
            "readback; not fabricated as a self-referential future "
            "SHA."
        ),
        "input_and_audit_evidence": [
            identity(HERE / name)
            for name in (
                "denominator.py",
                "denominator.json",
                "audit_evidence.py",
                "evidence-catalog.json",
                "requested-failures-query.json",
                "adjudicate.py",
            )
        ],
        "metadata_audit": {
            "existing_receipts_read": len(catalog["receipts"]),
            "exact_checks_read": catalog["check_count"],
            "content_bound_check_artifacts": catalog["unique_check_artifacts"],
            "content_bound_check_artifact_bytes": catalog["unique_check_artifact_bytes"],
            "criterion_cards_read": 25,
            "runtime_checks_executed_by_this_intake": 0,
            "scope": (
                "Committed output hash/size and native XML node/outcome "
                "custody verified; behavioral conclusions use named "
                "discriminators, not aggregate exit/count."
            ),
            "admission": (
                "Existing own create/resume admission retained; imported"
                " author/root checks keep their exact original "
                "source/projection/resume qualifiers. No blanket "
                "all-checkouts-admitted claim, no retrospective "
                "admission."
            ),
        },
        "status_semantics": {
            "closed": (
                "Criterion met on named concrete supported profile; "
                "proposal only, not applied finding closure."
            ),
            "limited": (
                "Useful technical property proved but exact criterion "
                "consumer/platform/final-source coverage or material "
                "supported boundary remains."
            ),
            "held": (
                "Missing standing semantic/permission/external owner "
                "decision prevents truthful finding closure."
            ),
            "open": (
                "Actual same-class escape or required published deciding"
                " evidence absent; verification absence is not "
                "automatically a source bug."
            ),
        },
        "nonblocking_scope_boundaries": [
            (
                "Generic real-runtime fixture proof does not require "
                "full production data unless the criterion consumer "
                "needs it."
            ),
            (
                "No physical power-loss/multihost/cryptographic "
                "ledger-attestation requirement invented."
            ),
            (
                "Finite compatibility/shape/source inputs do not acquire"
                " scientific or institutional authority; warning "
                "candidates remain candidates."
            ),
            (
                "Opaque external services/billing/permissions are not "
                "synthesized from constructor, callback, local database "
                "or green package."
            ),
        ],
        "findings": rows,
    }
    destination = HERE.parent / "current-all60-independent-adjudication.json"
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                "path": str(destination),
                "rows": len(rows),
                "bundles": len({row["bundle_id"] for row in rows}),
                "proposals": output["finding_status_proposal_counts"],
                "closure_ids": [],
            },
            ensure_ascii=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
