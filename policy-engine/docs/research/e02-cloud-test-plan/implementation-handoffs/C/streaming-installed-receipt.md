# Installed streaming consumer receipt

## Frozen input

- Commit: `789e9e906cc52ff544fb05d4faa5db13359fee84`
- Commit tree: `bc9e32dd74ad094c24c6012d161f7a669fb4f115`
- `policy-engine/` source subtree tree: `3bc5c0ff3f556ae8340a9fc16fd965b211ae8152`
- Base: `c40d4acae1ce58b597267255026d9356565828fd`
- Candidate changes: `streaming.py` plus two mirrored unit-test files; `pyproject.toml` and `hatch.toml` have no base-to-candidate diff.

The build source was extracted with `git archive <commit> policy-engine`, so the denominator is the complete `policy-engine/` package subtree at the subtree tree above, not a working-tree overlay.

## Build/install/consumer

Commands, run from `/tmp`:

```sh
git archive 789e9e906cc52ff544fb05d4faa5db13359fee84 policy-engine | tar -x -C "$SCRATCH/source"
UV_CACHE_DIR="$SCRATCH/cache" uv build --wheel --no-sources --out-dir "$SCRATCH/dist" "$SCRATCH/source/policy-engine"
uv venv --python /opt/homebrew/bin/python3 "$SCRATCH/venv-clean"
uv pip install --no-deps --python "$SCRATCH/venv-clean/bin/python" "$SCRATCH/dist/policy_engine-0.1.0-py3-none-any.whl"
printf '%s\n' "import sys; sys.path.append('/Users/deniskopylov/polisyos/policy-engine/.venv/lib/python3.14/site-packages')" > "$SCRATCH/venv-clean/lib/python3.14/site-packages/readonly-deps.pth"
env -u PYTHONPATH LOG_LEVEL=WARNING "$SCRATCH/venv-clean/bin/python" "$SCRATCH/probe_streaming.py"
```

`readonly-deps.pth` points only at the existing dependency site-packages directory. It appends that path directly without processing the editable-install `.pth`; the source checkout root and `src/` are absent from `sys.path`. `PYTHONPATH` was unset. The consumer ran from `/tmp`, without repository pytest/conftest.

## Evidence

- Wheel: `policy_engine-0.1.0-py3-none-any.whl`, SHA-256 `b7ecd5302a9839a4c76b728a11996fad429eb9b7fd4635f8dfe3f656a61c3eb3`.
- Consumer script SHA-256: `4a1863de027a9a6c863d83c374adcae911b6f4d083a1d521b13004c6b72173a2`.
- Complete concise consumer output: `consumer.log` (34 lines, 4,240 bytes), SHA-256 `e10283c648d37e8a779ab946a0f8e8bfe8386b716468f0a6ac54bfd1369e1db1`.
- Build output: `build.log`, SHA-256 `3f3486c23ebe1a3229e3a027e31b8cbe9bac77917890363b15f5699e21c9b80f`.
- The archived `streaming.py`, wheel entry, and installed `streaming.py` are byte-identical (107,665 bytes; SHA-256 `f096387f19db865674b653a9d76849589d26b3370f089b9839a2a0c63bc39367`).
- Installed imports of `streaming`, `cursor_store`, `event_stream`, and CAS `store` all resolved under the private venv's `site-packages/polisyos/`.

## Behavioral denominator and result

The standalone consumer drives the installed JSONL connector through `process_stream_dataset` into filesystem CAS and `CursorStore`; it reads persisted chunk/window bytes back. Input fixtures are four rows (`m0`–`m3`), chunk size 2, with isolated CAS/cursor state per scenario.

- All four strategies (`pause`, `throttle`, `spill_to_disk`, `fail_closed`): cap 3 rejects the second 2-row chunk; only chunk 0 remains in CAS; cursor/checkpoint stay at offset 0; paused checkpoint retains `m0,m1` and their chunk-0 refs while recording observed offset 1. Restart at cap 4 commits chunks 0/1 and the window readback contains each of `m0`–`m3` once; final cursor/checkpoint are offset 1/closed.
- All four strategies: exact 2-row closing transitions pass for session, count, and tumbling windows; each readback contains `m0`–`m3` once and closes at offset 1 (12 combinations).
- UTF-8 JSON-byte case: row sizes `[119, 115, 104, 86]`, exact initial cap `234`; rows `m0,m1` at equality commit, `m2` overflows before chunk 1 is persisted, and restart at a larger byte cap reads all four rows exactly once.

Result: `PASS installed-wheel JSONL -> process_stream_dataset -> CAS/CursorStore`. This receipt and the wheel remain in scratch only; no tracked files were written.
