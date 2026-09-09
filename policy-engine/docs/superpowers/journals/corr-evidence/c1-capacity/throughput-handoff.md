# C1 bounded throughput experiment — 2026-09-09

This lane-local measurement extends the existing SDK adapter, extractor codec,
structural intake, typed `ArticleExtractionResult` owner, and process observer.
It changes no production extraction or authority algorithm. No provider call or
real-frame enumeration has been executed by this helper's author. Root owns
credentials, declaration emission/commit, live dispatch and final C1 reporting.

## Predeclared design and ownership

`throughput_declaration.py` independently reconciles the complete held work set,
eligible identity/length/hash set, and original input-length tercile identity sets
in Python and SQL. Unknown types, duplicate/null identities and differences fail
as ambiguous. It excludes the frozen six pilot identities, selects 60 new IDs per
tercile by a separate fixed salted hash, and interleaves the tiers. The 180 IDs are
shared across models but assigned to disjoint per-model level blocks:

| Concurrency | New inputs | Inputs per tercile | Wall cap |
| --- | --- | --- | --- |
| 1 | 12 | 4 | 2400 seconds |
| 4 | 24 | 8 | 1500 seconds |
| 16 | 48 | 16 | 900 seconds |
| 32 | 96 | 32 | 900 seconds |

The original draft used nested 12/24/48/96 prefixes over 96 inputs. Before any
throughput declaration or call, root observed identical response bytes and usage
with markedly different MiniMax request latency. Caching is plausible, not
established. The design therefore changed to disjoint blocks, removing within-model
input repetition. Provider/global/cross-model caching remains unknown. The earlier
`throughput-green-initial.json` is a historical three-test result for the superseded
96-input design, not evidence for current selection. `throughput-red.json` retains
the initial missing-owner red.

Each level uses direct `_extract` only: no screening, self-verification, fulltext
acquisition, or full-corpus pass. It therefore measures that phase, not whole-pipeline
throughput. Different input blocks and workload sizes also confound causal attribution
to concurrency; the result describes an operational knee, not a proven optimum.

`throughput_runner.py` reads back committed, content-bound plan/frame/configuration
bytes and the exact successful model contract. At most the declared number of workers
retain source/parsed/typed objects; results are persisted individually and only scalar
metadata accumulates in SQLite. Each selected source is read-only and reconciles its
Python and SQL content hash before dispatch. The existing contract probe's observed
client checks the real owner's extraction structure before normalization. The actual
`_extract` result must validate as `ArticleExtractionResult`. No catalog default,
alternative parser, or reconstructed design is introduced.

Outcome JSON, provider observations, source fixtures, checkpoint provenance and
measurement outputs carry their own synthetic status. Measurement artifacts remain
candidate-only and grant no authority. This new path replaces no legacy default, so
there is no separate production path to strangle. P27/P29/P35/P38 apply through shared
owners, actual executions/removals, complete identity reconciliation and explicit
measurement boundaries. No closed A/B/C2 mechanism is reopened.

## Measures and stopping

`throughput_analysis.py` recomputes all-terminal and typed-success median/p95/p99,
complete/error/success rates over the entire declared level, and typed successes per
active second. Latency starts at persisted work admission before owner/client creation
and ends at the typed outcome; source resolution precedes that admission. The raw
provider observation separately retains SDK transport duration. Import/startup time
is distinct from the active interval, aligned using the observer's exact monotonic
origin. Native CPU/RSS/disk include the worker and observed descendants; observer cost
and unseen short-lived-child limitations remain explicit in the telemetry owner.

Memory trends are descriptive OLS slopes of sampled summed RSS against elapsed time
and completed work during the active interval. Physical RAM/logical CPU denominators
are observed, not inferred. The 3 GiB RSS cap and 2 GiB native-write cap are sampled
operational stops; actual sample gaps and bounded shutdown describe overshoot.

Only complete levels can establish a knee: a typed-success throughput gain below 20%
over the preceding complete level or an error fraction above 10% stops higher levels.
Median/tail latency is reported independently without an invented latency stop.
Partial, timed-out or unreconciled levels are `not_established`, keep the full declared
denominator, and stop progression without knee credit. Unreadable checkpoint measures
are null/ambiguous, never observed zeros. Retries are classified but not performed.

Observed usage on failed as well as successful replies contributes to the token-cost
lower bound. Unknown usage stays distinct. Cost uses the configuration's frozen live
metadata rate; it is not proof of provider billing and cannot establish correctness.

## Deciding evidence

`throughput-disjoint-green.json` records four tests passing in 7.634 seconds: the whole
240-row marked synthetic frame, actual SDK fixture through the real typed owner,
bounded workers, full failed denominator, saved-outcome corruption refusal, arithmetic
stops, and real native memory growth. The latter deliberately retains 4 MiB per item;
the actual analysis observed 4,227,660 bytes (about 4.03 MiB) per completion and a
positive RSS/time slope. This is a synthetic instrumentation witness, not provider
performance. Its complete output records the observed 8 logical CPUs and 16 GiB RAM.

The five property-removal captures each return RC1 at the intended assertion:

| Capture | Removed property, with markers retained |
| --- | --- |
| `throughput-zero_memory_slope-removal.json` | Actual memory slope replaced with zero while the real growing worker succeeds. |
| `throughput-skip_owner_structure-removal.json` | Existing structural intake bypassed; empty object becomes a vacuous typed success. |
| `throughput-unbounded_workers-removal.json` | Real worker count exceeds the declared concurrency. |
| `throughput-reuse_level_inputs-removal.json` | Real block offset reset, reusing prior-level inputs. |
| `throughput-skip_input_binding-removal.json` | Selected-input content comparison removed; fake hash admitted. |

A subsequent narrow companion adds the checkpoint artifact's own provenance table
through the same initializer used by the worker. Its pure-stdlib refusal/positive are
`throughput-checkpoint-provenance-red.json` and `throughput-checkpoint-provenance-green.json`
(RC1 then RC0, 0.016 seconds green). `throughput-final-ruff.json` records six-path RC0.
The final combined five-test wave is intentionally pending the root's resource-window
release. Prior captures retain their original bindings; they are not restamped.

## Root commands after the final test wave

Run from `policy-engine/`. The following declaration command makes no inference call
but reads the credential through the existing safe writer; root must execute it.
It writes a separate frame and two plans, all of which must then be committed before
the live runner admits them. No declaration has been emitted yet.

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m docs.superpowers.journals.corr-evidence.c1-capacity.throughput_declaration --deepseek-contract docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-deepseek-contract-declaration.json --deepseek-verdict docs/superpowers/journals/corr-evidence/c1-capacity/deepseek-contract-verdict.json --minimax-contract docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-minimax-contract-v2-declaration.json --minimax-verdict docs/superpowers/journals/corr-evidence/c1-capacity/minimax-codec-v2-contract-verdict.json --deepseek-configuration docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-deepseek-pilot-v3-declaration.json --minimax-configuration docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-minimax-pilot-v3-declaration.json
```

The final targeted gate, when released, is:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m docs.superpowers.journals.corr-evidence.c1-capacity.throughput_verification --output docs/superpowers/journals/corr-evidence/c1-capacity/throughput-final-green.json
```

After root explicitly releases the live quiet window, each model's runner is:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m docs.superpowers.journals.corr-evidence.c1-capacity.throughput_runner docs/superpowers/journals/corr-evidence/c1-capacity/2026-09-09-deepseek-throughput-declaration.json --output .tmp/corr-c1-capacity/throughput/deepseek
```

Use the corresponding `minimax` declaration/output for the second model. The internal
`--worker-level` flag belongs to the profiler's child launch. Each output root is new
and immutable; no interrupted throughput stage is silently retried. This is separate
from the campaign's interruption/resume experiment. The root may stop the sweep and
retain a partial result; no command in this handoff authorizes a full re-extraction.

## Routed remaining work

- C1/root: final combined gate, real-frame declaration/commit, live quiet-window
  profiles, model/corpus cost and correctness-claim limitations in the final report.
- C1/measurement scope: unknown provider caching, observational concurrency/input-mix
  confounding, sampled resource ceilings and unseen short-lived descendants.
- C1/campaign owner: complete three-phase six-input comparison and durable resume;
  direct-extraction throughput cannot substitute for those acceptance signals.
- No new A, B, C2, governed-register, authority-verifier, or public-surface repair is
  proposed by this measurement helper.
