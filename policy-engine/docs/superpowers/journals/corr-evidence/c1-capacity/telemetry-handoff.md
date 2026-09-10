# C1 local process telemetry — 2026-09-09

This is the lane-local observation mechanism and its marked synthetic smoke;
it is not a live provider profile or a throughput/correctness result. Root owns
the campaign declaration, credentials, live calls, final report and commits.
No production source, closed A/B/C2 mechanism or governed register changed here.

## Entry point

Import `docs.superpowers.journals.corr-evidence.c1-capacity.process_telemetry`
with `importlib.import_module`, then call:

```python
profile_module(
    module,
    module_args,
    cwd=product_root,
    output_root=new_lane_output,
    limits=ProfileLimits(
        max_wall_seconds=600,
        max_rss_bytes=declared_rss_limit,
        max_disk_write_bytes=declared_write_limit,
        sample_interval_seconds=0.25,
    ),
    completion_reader=read_completed_count,
    interrupt_requested=stop_event.is_set,
    synthetic=False,
)
```

The worker is launched with the current interpreter and `-m` in its own process
group. It inherits the calling process's environment without inspecting or
persisting it. Raw child stdout/stderr are discarded; the campaign worker must
persist its application outcomes itself. The observer persists `samples.jsonl`
and returns a summary for the caller to persist once. Neither module arguments,
process commands, environment, raw exception messages nor application content
enter the telemetry. `synthetic=True` is required for synthetic workloads.

`sqlite_completion_reader(path, terminal_statuses=(...))` is an optional read-only
adapter over `work_items.status`; it reconciles the SQL count against the full
row/status identity set in memory. An arbitrary `() -> int` callback also works.
A missing, locked, unreadable or invalid checkpoint gives null / `ambiguous`,
not zero. Root/C must supply the campaign's actual terminal statuses.

## Measurement and stopping scope

The native ABI is SDK `rusage_info_v2` plus `mach_timebase_info`. PID and native
process-start identity prevent mixing recycled PIDs. The complete numeric-only
`ps` PID/PPID inventory discovers descendants; previously seen children remain
tracked after reparenting. Samples contain RSS, footprint, cumulative user/system
CPU, native disk bytes, completion count, elapsed time and ambiguity status.
CPU Mach ticks and the conversion ratio remain in the process observations.

Cumulative counters are lower bounds over observed process lifetimes. An unknown
child that starts and exits between samples can be missed; native reads racing
exit are `ambiguous`. This is a declared bounded limitation, not complete lifetime
process accounting. The peak is a simultaneous sampled RSS sum; footprint and
disk-write bytes are separate quantities. File size is not substituted for disk
I/O. The observer and its `ps` children are excluded from the worker tree; the
separately reported observer CPU covers only the observer process.

Ceilings are sampled operational stops, not kernel-enforced hard resource limits.
The interval is a target cadence: use the recorded maximum sample gap and shutdown
grace when interpreting overshoot, including observer/OS scheduling latency.
Wall, summed RSS, native disk-write and requested-interruption stops signal the
owned group, then escalate within the bounded shutdown sequence. Unexpected
observer failures also terminate the owned group and expose only the exception
class. `shutdown_not_established` remains an explicit unsuccessful shutdown result.

## Red, correction and deciding wave

The first command was:

```text
.venv/bin/python -S -m unittest docs.superpowers.journals.corr-evidence.c1-capacity.test_process_telemetry -v
```

`telemetry-red.json` is RC1: the three then-declared tests fail on
`process_telemetry_owner_missing`. `telemetry-initial-smoke.json` preserves the
initial low native-CPU red. The intermediate file named `telemetry-green.json`
is also RC1 and earns no green credit. It independently observes `getrusage`
user time 0.440025 seconds versus raw native ticks divided by 1e9 at 0.01056072.
That refutes the preliminary clock-polling explanation: native CPU values need
the Mach timebase ratio on this station. The workload now batches arithmetic
between clock reads, and both native CPU axes use the actual conversion.
`telemetry-observer-failure-red.json` additionally records the unsanitized error
and missing cleanup behavior before the owned-worker cleanup was added.

The deciding command shape is:

```text
PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -S -m docs.superpowers.journals.corr-evidence.c1-capacity.telemetry_verification --mode MODE --output OUTPUT
```

Each invocation runs only its stated gate; the runner propagates the actual test
return code and stores its complete output. The frozen wave is:

| MODE | OUTPUT in this directory | RC | Seconds | Decisive observation |
| --- | --- | --- | --- | --- |
| `baseline` | `telemetry-final-green.json` | 0 | 7.269 | Four tests, including real descendant CPU/disk/memory, checkpoint, caps, interruption, missing inputs and failure cleanup. |
| `zero_cpu` | `telemetry-cpu-removal.json` | 1 | 2.867 | Aggregate CPU is zero while the independent child consumed 0.457403 seconds; CPU assertion fails. |
| `zero_disk` | `telemetry-disk-removal.json` | 1 | 3.121 | Aggregate disk is zero while the child wrote 33,554,432 bytes; disk assertion fails. |
| `without_descendants` | `telemetry-descendant-removal.json` | 1 | 2.885 | Parent-only CPU 0.111651 seconds cannot cover child CPU 0.459055 seconds; descendant omission fails. |

All removals keep the report fields, status markers, independent child observer
and successful workload intact. The child uses a separately represented SDK
buffer and also compares its CPU against `resource.getrusage`; its uncached
32 MiB file carries a synthetic JSON preamble and matches the independent hash.
The final positive native user delta is 0.438454792 seconds versus independent
`getrusage` 0.438447 seconds. Its process-tree peak RSS is 123,371,520 bytes.

The full test denominator is the four methods discovered by the stdlib unittest
loader; the final output names them all. Each removal reruns the same actual
descendant witness alone. The four Python source bindings are identical across
the entire frozen positive/removal wave and are retained in those captures.
`telemetry-ruff.json` retains the exact four-path Ruff command and RC0 output.

## Routed limits

- C1 owns the upcoming live profile, throughput knee, memory trend, corpus growth,
  interruption/resume campaign and declared cost estimates; none is claimed by
  this smoke.
- C1 observation scope owns short-lived unseen descendants and missed final native
  reads. Complete lifetime coverage would require child-launch/final-snapshot
  cooperation or OS lifecycle tracing; this polling observer declares the gap.
- C1 owns completion-status semantics through its checkpoint callback; this helper
  cannot decide that an application work item is durably complete.
- The initial CPU-unit finding belongs to this observer and is fixed here; the
  preliminary clock-polling explanation is superseded, not assigned elsewhere.

## Pre-live origin and hardware delta

The summary now retains its exact `monotonic_started_seconds`, allowing worker
request timestamps to be aligned with the samples without a guessed offset.
Before launch, `os.cpu_count()` and the numeric `sysctl hw.memsize` observation
establish the logical-CPU and physical-memory denominators. Missing observations
remain null/ambiguous. CPU capacity fraction is observed worker CPU seconds divided
by wall seconds and logical CPUs; RSS fraction is the measured simultaneous peak
divided by physical RAM. These are resource descriptions, not benchmark scores.

`telemetry-origin-hardware-delta-green.json` retains the unchanged complete four-test
suite plus the new origin/denominator/fraction assertions: RC0, 5.652 seconds.
The actual station observation is 8 logical CPUs and 17,179,869,184 bytes of RAM.
The 3 GiB throughput limit would therefore be an 18.75% cap, not observed usage.
`telemetry-origin-hardware-ruff.json` retains the exact four-path lint command, RC0.
The earlier positive/removal captures remain historical proofs under their own
source bindings; this delta does not reclassify them as current byte-identical runs.
