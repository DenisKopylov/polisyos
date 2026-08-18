# Timing evidence — salvaged tool-run records

This directory holds tool-timing records rescued from ephemeral locations. It is **evidence, not a
live log**: nothing appends here during normal operation. The live log is described in
`tools/lib/timing.py`.

## `2026-08-17-salvaged-timing-records.jsonl`

One JSON object per line:

| field | meaning |
| --- | --- |
| `salvaged_at` | when the salvage ran |
| `source_path` | repository-relative path the record was read from |
| `source_line` | 1-indexed line within that file |
| `raw` | the original record line, **byte-for-byte verbatim** |

`raw` is preserved as text rather than re-serialized, so the salvage cannot have normalised,
reordered or reformatted its input. A consumer recovers the record with `json.loads(entry["raw"])`.
Records were **not** edited, deduplicated or reordered — near-duplicate runs (for example
`test-timing.jsonl` and `test-timing-final.jsonl`) are both retained, because which of them is
redundant is a judgement the salvage is not entitled to make.

### Method

Enumerated the whole candidate set rather than sampling it: every file under the repository tree
matching `*timing*.jsonl` (16 files), then every line of each, admitting a line only if it parses as
a JSON object carrying the full `ToolRunRecord` field set. Zero lines were rejected.

### What was recovered

- **18 records** from **16 files**, covering **5 distinct tools** and **12 distinct lanes**
  (`tool:mode`).
- All surviving sources were per-run logs written under
  `.worktrees/gy-defc-3-retry/policy-engine/tmp/**`, an active worktree's scratch tree.

### What was NOT recovered, and why it matters

**The primary substrate is gone.** `tools/lib/timing.py` defaulted the log to
`/tmp/polisyos-tools/timing.jsonl`, `POLISYOS_TOOLS_TIMING_LOG` was unset, and that directory no
longer exists on this host. The plan (`GY-DI3`, Rev 36) measured that file at **32 KB** carrying
"every budget this plan now quotes". None of it survives; it was not recoverable from
`/private/tmp` or `/private/var/folders` either.

Concretely, the evidence base for `GY-DI2`'s headline numbers is lost:

- The plan cites **six successful `second_domain_pack:write` samples** at `194.9`, `233.1`, `292.9`,
  `334.6`, `397.5`, `426.3` s, giving that lane a `p95` of `426.3` s. **This salvage recovers exactly
  one `write` sample, at `815.662` s** — and that one was measured under contention, not serialized.
  The quoted `426.3` s `p95` can no longer be reconstructed from surviving data.
- The plan's `GY-DI2` extent measurement — "successful samples for **19** lanes, **15 absent from the
  catalog**" — cannot be re-derived either. This salvage sees **12** lanes total.
- The plan's `GY-DI4` measurement of N10a's corrupt lane — five healthy runs at `13.403`–`24.675` s
  and one `exit 2` at `14.153` s — is likewise absent. The single surviving `corrupt-field-drift-check`
  record for that tool is at `31.661` s, above the whole quoted range, again consistent with a
  contended regime.

Those plan figures remain the architect's recorded measurement; they are simply no longer
independently checkable against raw records. Treat them as cited history, not as reproducible data.

### Count correction

The task brief expected **9** salvaged records. The true recoverable count is **18**. The difference
is not a disagreement about the data: the brief's figure counts only files named exactly
`timing.jsonl` (9 files, 1 record each), while seven further files hold timing records under
run-specific names chosen via `POLISYOS_TOOLS_TIMING_LOG` — `guardrail-timing.jsonl`,
`guardrails-timing.jsonl`, `test-timing.jsonl`, `test-timing-final.jsonl`, `check-timing.jsonl`,
`corrupt-timing.jsonl`, `rederive-timing.jsonl` — carrying 9 more records between them. Because the
log path is configurable, **filename is not a sound denominator for this set**; record shape is.
