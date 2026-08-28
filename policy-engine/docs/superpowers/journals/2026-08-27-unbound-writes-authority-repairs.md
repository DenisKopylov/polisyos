# Unbound writes authority repairs — execution journal

## Timing Task 3 completed once-only receipt

Status: **completed**. The once-only serialized run completed under source
freeze `deee40fafb2ad627130f12cfdbef9bf947170803`; its preserved raw receipt and
one wall-clock catalog lane are recorded below.

### Source-freeze and once-only rule

The source freeze was the attached `HEAD` produced by the prelaunch commit that
contained this journal and the evidence-admission test:

```sh
SOURCE_FREEZE="deee40fafb2ad627130f12cfdbef9bf947170803"
```

The completed launch passed that exact value using `--corrupt-field-drift-check`
and `--expected-source-freeze "$SOURCE_FREEZE"`. No tracked source changes
occurred between capture and process launch. The serialized expensive command
ran exactly once. It executed in a fail-closed subshell with `ulimit -t 600`,
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

### Completed receipt fields

| Field | Completed receipt |
| --- | --- |
| Source freeze | `deee40fafb2ad627130f12cfdbef9bf947170803`, matched by the validator |
| Direct process exit | `0`, read before report or timing-record parsing |
| JSON report | `status="pass"`, `issues=[]`, 12 result rows, all `rejected=true` |
| `/usr/bin/time -p` real | `142.84` seconds, wall-clock |
| `/usr/bin/time -p` user | `128.74` seconds, CPU component |
| `/usr/bin/time -p` sys | `12.91` seconds, CPU component |
| CPU total | `141.65` core-seconds (`user + sys`), below the declared 600 core-second ceiling |
| ToolRunRecord `duration_ms` | `141380.475` milliseconds, wall-clock catalog sample |
| Uptime before / after | `4:41` loads `2.52/2.22/2.30` -> `4:43` loads `2.88/2.56/2.43` |
| Timing log | exactly one record at `.polisyos-tools/unbound-writes-epoch-timing-deee40fafb2ad627130f12cfdbef9bf947170803/gy-n12-epoch-corrupt-field-drift.jsonl` |
| Promoted evidence | `docs/superpowers/timing-evidence/2026-08-27-gy-n12-epoch-corrupt-field-drift.jsonl:1`, byte-preserved raw record |
| Timing catalog lane | one serialized lane, `samples_ms=[141380.475]`, p95 `141380.475`, timeout `282760.95` |

Wall-clock: `/usr/bin/time real=142.84s`; ToolRunRecord
`duration_ms=141380.475ms`. CPU: `user + sys = 141.65 core-seconds`. The
historical `180 -> 264.30 core-second` correction remains only in this CPU
ceiling lane; neither CPU quantity enters `samples_ms`.

### Independent completed-set derivations

| Set | Derivation 1 | Derivation 2 | Result |
| --- | --- | --- | --- |
| Corrupt-field cases | completed JSON report: 12 results, 12 rejected | AST literal `CORRUPT_FIELD_CASE_IDS`: 12 members | agree: 12 |
| Catalog lanes and keys | raw JSON: 23 lanes, 23 unique keys, one target key | `load_timing_budget_catalog()`: 23 lanes, 23 unique keys, one target key | agree: 23 / 23 / 1 |

There is no count disagreement. The historical debt-register closure command is
defective because it compares aggregate CPU `264.30` core-seconds as `264300`
wall-clock milliseconds; that protected register was not edited.

### A. Local promotion proof — nonportable

At promotion time only, the ignored scratch raw line (with its trailing newline
removed) and the committed wrapper's decoded `raw` bytes compared equal. The
local comparison command exited `0`; both SHA-256 digests were
`e6e68194fdb758306538ae15ee7116b7eb334ef621b0bd97b4a7ebc987d478f5`.
This proves the local promotion transfer, but is explicitly nonportable because
the scratch directory is ignored. It is not part of the durable catalog-row
closure command.

### B. Durable corrected closure command and receipt

```bash
PYTHONPATH=src:. .venv/bin/python -S -c 'import dataclasses,json; from datetime import datetime; from pathlib import Path; from tools.lib.timing import ToolRunRecord,_coerce_record,admit_duration_sample,healthy_terminal_exit_codes_for,load_healthy_terminal_declarations,load_timing_budget_catalog; key="quality.validation.check_layer3_gy_epoch_chronology_contract:corrupt-field-drift-check"; freeze="deee40fafb2ad627130f12cfdbef9bf947170803"; expected_source_path=".polisyos-tools/unbound-writes-epoch-timing-deee40fafb2ad627130f12cfdbef9bf947170803/gy-n12-epoch-corrupt-field-drift.jsonl"; catalog=Path("tools/quality/timing_budgets.json"); evidence=Path("docs/superpowers/timing-evidence/2026-08-27-gy-n12-epoch-corrupt-field-drift.jsonl"); journal=Path("docs/superpowers/journals/2026-08-27-unbound-writes-authority-repairs.md"); rows=[lane for lane in load_timing_budget_catalog(catalog) if lane.timing_key == key]; assert len(rows) == 1, len(rows); lane=rows[0]; assert lane.tool == "quality.validation.check_layer3_gy_epoch_chronology_contract" and lane.mode == "corrupt-field-drift-check" and lane.regime == "serialized"; assert lane.command == f".venv/bin/python tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py --corrupt-field-drift-check --expected-source-freeze {freeze} --output-format json"; assert lane.sample_admission_predicate == "declared_healthy_terminal:v1" and lane.source_refs == (f"{evidence}:1",); lines=evidence.read_text(encoding="utf-8").splitlines(); assert len(lines) == 1; entry=json.loads(lines[0]); assert set(entry) == {"salvaged_at","source_path","source_line","raw"}; assert isinstance(entry["salvaged_at"],str) and entry["salvaged_at"].strip(); datetime.fromisoformat(entry["salvaged_at"]); assert entry["source_path"] == expected_source_path and type(entry["source_line"]) is int and entry["source_line"] == 1 and isinstance(entry["raw"],str) and entry["raw"].strip(); raw=json.loads(entry["raw"]); assert isinstance(raw,dict) and set(raw) == {field.name for field in dataclasses.fields(ToolRunRecord)}; record=_coerce_record(raw); assert record.tool == lane.tool and record.category == "quality" and record.category == record.tool.split(".",1)[0] and record.output_format == "json" and record.mode == lane.mode and record.regime == lane.regime; assert record.exit_code == 0 and record.status == "ok" and record.preflight_status == "ok" and record.duration_ms == 141380.475; terminals=healthy_terminal_exit_codes_for(record.tool,record.mode,load_healthy_terminal_declarations()); assert terminals == (0,); assert admit_duration_sample(record,healthy_terminal_exit_codes=terminals).admitted; assert lane.samples_ms == (record.duration_ms,) and lane.measured_p95_ms == record.duration_ms and lane.recommended_timeout_ms == 2 * record.duration_ms and lane.budget_basis == "max_observed" and lane.ceiling_is_declared is False; text=journal.read_text(encoding="utf-8"); assert "Wall-clock: `/usr/bin/time real=142.84s`; ToolRunRecord" in text and "`duration_ms=141380.475ms`" in text and "CPU: `user + sys = 141.65 core-seconds`" in text and "180 -> 264.30 core-second" in text; assert "264300" not in json.dumps({"samples_ms":lane.samples_ms,"measured_p95_ms":lane.measured_p95_ms,"recommended_timeout_ms":lane.recommended_timeout_ms})'
```

Durable closure command exit: `0`.
