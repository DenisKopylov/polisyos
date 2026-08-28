# Unbound writes authority repairs — execution journal

## Timing Task 3 prelaunch declaration

Status: **not launched**. This is the prelaunch receipt only; it is not timing
evidence and does not add a timing-catalog row.

### Source-freeze and once-only rule

The source freeze is the attached `HEAD` produced by the prelaunch commit that
contains this journal and the red/green evidence-admission test. Immediately
after that commit, capture exactly:

```sh
SOURCE_FREEZE="$(git rev-parse HEAD)"
```

Pass that exact value using `--corrupt-field-drift-check` and
`--expected-source-freeze "$SOURCE_FREEZE"`. No tracked source changes may occur
between that capture and the process launch. The serialized expensive command
runs exactly once. It executes in a fail-closed subshell with `ulimit -t 600`,
checks the attached branch, source freeze, and clean tree immediately before
the process, and creates a source-freeze-named fresh run directory only when no
prior directory has that name; it does not use `mkdir -p` for the run directory.
A nonzero direct exit, a non-pass report, a signal or killed `/usr/bin/time`
process, or anything other than one well-formed
exit-0/`ok`/`serialized` tool record is a non-receipt; it is not rerun to obtain
a timing number.

### Healthy-terminal derivation

This admission does not infer health from the epoch validator's missing
`TIMING_HEALTHY_TERMINAL_EXIT_CODES` declaration. The code establishes the
semantics directly:

1. `corrupt_field_drift_results()` records `rejected=bool(issues)` for every
   candidate mutation in
   `tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py`
   lines 1475–1493.
2. In corrupt-field mode, a row with `rejected=False` becomes an issue; a
   case-denominator mismatch is separately an issue (lines 1551–1560).
3. An empty issue set yields `status="pass"` (lines 1561–1565), and `main()`
   maps `status="pass"` to direct exit `0` (lines 1613–1643).

Therefore a complete corrupt-field denominator whose mutations are all
rejected is healthy only with direct exit `0`; direct exit `1` is a validator
failure and cannot become a catalog sample. The shared timing default is also
exit `0` (`tools/lib/timing.py` lines 85–93), but that is only compatible with
the independently derived result, never its authority.

#### Opposite-polarity sibling warning

`check_layer3_gy_depth_n_universality_contract.py` explicitly declares
`{"corrupt-field-drift-check": [1]}` and documents the inverse polarity at
lines 17–22: its healthy path is exit `1`, while exit `0` is its defect
terminal. If the epoch tool had that sibling's polarity, an absent declaration
plus the shared default would admit defects and reject healthy work. This is why
the code path above, rather than declaration absence, is the admission proof.

#### Declaration count, derived twice at prelaunch HEAD

Both complete-set AST enumerations found **8 declaring modules out of 431
`tools/**/*.py` modules** at prelaunch `HEAD 68b8490d0031eb171760856de08724e028b8ad8b`:

| Method | Python-module denominator | `TIMING_HEALTHY_TERMINAL_EXIT_CODES` declarers |
| --- | ---: | ---: |
| Filesystem AST walk of `tools/**/*.py` | 431 | 8 |
| Git-object AST walk of `HEAD:policy-engine/tools/**/*.py` | 431 | 8 |

The eight paths agree in both derivations and each declares exit `1` for
`corrupt-field-drift-check`:

- `tools/quality/validation/check_layer3_gy_acquisition_contract.py`
- `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`
- `tools/quality/validation/check_layer3_gy_generation_cycle_contract.py`
- `tools/quality/validation/check_layer3_gy_generation_cycle_disposition_ledger.py`
- `tools/quality/validation/check_layer3_gy_joint_simulation_horizon_contract.py`
- `tools/quality/validation/check_layer3_gy_promotion_contract.py`
- `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- `tools/quality/validation/check_layer3_gy_value_gate_contract.py`

### Resource and unit declaration

The implementation run has a declared ceiling of **600 core-seconds**, measured
as `/usr/bin/time -p` `user + sys`. The historical corrected CPU observation is
**180 -> 264.30 core-second**. `180 core-second` is the invalid prior
declaration; `264.30 core-second` is the valid historical CPU observation used
to motivate the ceiling.

Neither CPU value is wall-clock timing evidence. `tools/lib/timing.py` measures
`duration_ms` using wall-clock `perf_counter`; only the newly observed
ToolRunRecord `duration_ms` may populate catalog `samples_ms`. `/usr/bin/time`
`real` is separately recorded as wall-clock, and `user + sys` stays separately
recorded as core-seconds.

### Planned receipt fields

| Field | Prelaunch value |
| --- | --- |
| Source freeze | pending; capture from the prelaunch commit immediately before launch |
| Direct process exit | not launched |
| JSON report status | not launched |
| `/usr/bin/time -p` real | not launched; wall-clock |
| `/usr/bin/time -p` user | not launched; CPU component |
| `/usr/bin/time -p` sys | not launched; CPU component |
| CPU total | not launched; `user + sys` core-seconds, ceiling 600 |
| ToolRunRecord `duration_ms` | not launched; wall-clock catalog candidate only |
| Uptime before / after | not launched; capture an `uptime` pair |
| Timing log | not launched; fresh `.polisyos-tools/unbound-writes-epoch-timing-$SOURCE_FREEZE/gy-n12-epoch-corrupt-field-drift.jsonl` |
| Promoted evidence | not launched; no JSONL evidence row exists yet |
| Timing catalog lane | not launched; no catalog edit exists yet |

The planned launcher uses `POLISYOS_TOOLS_TIMING_REGIME=serialized`, captures
the direct process exit before parsing any report, and redirects the
`/usr/bin/time -p` output to the planned receipt. It records both `uptime`
values around the single process invocation after the fresh-directory and
resource-ceiling guards succeed.
