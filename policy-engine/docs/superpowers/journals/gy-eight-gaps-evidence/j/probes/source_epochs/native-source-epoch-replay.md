# Exact native source epoch reconstruction

This supplies historical replay inputs, not a source repair or a new test result. All transformations and syntax checks happened in memory. No product source, test, artifact, receipt or Python helper was written; no gate or test ran. Only the two minimal patches and this note were created in this scratch retention directory.

## Exact deltas and application order

Apply `reverse-cli-custody-bridge.patch` only to a disposable copy of the exact current input bytes below. It restores the two former owner lines (the check branch passes the JSON freeze instead of the sealed family, and the builder annotation says dictionary) plus the existing test's former direct-comparator body. This reconstructs the actual enumerator-correction epoch.

Apply `reverse-enumerator-splats.patch` next to reconstruct the original complete-native epoch. It reverses only the two generator splats and their added grouping parentheses in the independent raw-contract path enumerator. Deleting only the stars did not match; the actual native traceback's `set().union(` form and the exact recorded hash require reversing those parentheses as well.

| Path | Current input SHA256 | After CLI reverse SHA256 | After enumerator reverse SHA256 |
|---|---|---|---|
| `tools/quality/validation/check_layer3_gy_loop_artifacts.py` | `c18de7dda8d26f63cfe5ef07b6a04c71ef8d570867c63ae52ee79db18bcb67bb` | `fd111670fb109e80b5a516825ee1ada4c79ec432a3f9a3b1276edd40ee39444e` | unchanged |
| `tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py` | `69f2bda8ef0d6b9f599d04343e94968d5dfd20daac3867bad4436d0273944341` | `9f0ec3fe866330e346d7b34b65db5525efa4dfe6df00fd7abaa41a7e6b047fcf` | `d068e65cc22863e1bfad7bb03de396718d0ca991fcd8ec1696180e5867329c05` |

| Patch | SHA256 |
|---|---|
| `reverse-cli-custody-bridge.patch` | `a172402a476cd9ecfb9101b0f9988be2e174a5aee023db390fef69f51ae09dbc` |
| `reverse-enumerator-splats.patch` | `97f272169798cbd08f2f7bf3c91bfa36c23b12dd2cae732e3baca992da49c0c7` |

These are unified differences with product-relative `a/` and `b/` paths, not source copies. Require exact input hashes before applying and exact output hashes after; never use fuzz or invent a future commit. Do not apply them to the active lane. No auxiliary worktree or copied source tree was created. If replay later uses an auxiliary worktree, its name must start `gygaps-lane-` and its creation must be journaled.

## Complete source-fence evidence

The complete actual runner population is contained `.py` files in `src/`, `tools/`, `tests/`, with its existing resolved-path containment and `__pycache__` rule. A full `Path.rglob` traversal and an independent `os.walk` traversal read and hashed every member: **5601 / 5601 files**. The full path/hash mappings were equal, with no unreadable member or identity difference. Another full walk and byte read after reconstruction was unchanged. The current whole-source digest is `d3001ba4d618288763592461fbe4191b28ca3c227813742e2803c2cded015964`.

The digest is exactly SHA256 of `json.dumps(path_to_raw_sha, sort_keys=True, separators=(",", ":"))`, using unprefixed file SHA256 strings. Only the two named paths were substituted into each independently derived full mapping. Each reconstructed map equals both the actual receipt initial `source_fence.path_and_raw_sha256_digest` and final `source_fence_after_digest`; `source_fence_unchanged` is true. Every specifically pinned test-source member also agrees. The redundant full derived map is not retained.

| Actual retained receipt | Raw receipt SHA256 | Reconstructed complete source digest | Denominator |
|---|---|---|---|
| `j/native-live-wave.json` | `40a742ecbef10bd4af05445d49f4112ac9d0266ca645d8099b8a14fef88b80c7` | `4f8575c57ff4b56438691a05cd899720a8cda3b5a1237f6849895b6b641889a5` | 5601 |
| `j/native-enumerator-correction.json` | `b50b8637d2aa6ef2e93400544ed4a114cd5f0de1e56bc6cb38481839b800e58c` | `d206ad46d44d2b05bdb3822884eeaed25e28b80a9e3d32eb0a6edaab98c9513b` | 5601 |

Receipt paths are relative to `docs/superpowers/journals/gy-eight-gaps-evidence/`. Their raw bytes and correction ancestry were not modified. Reconstruction does not turn the original failed native test into a pass, make its correction a full wave, or claim the later CLI integration test ran on either earlier epoch. Native runner/recorder execution pins remain separate and unchanged.

## Necessity and remaining boundary

The current attached-lane HEAD at readback was `8a9b92b416aaf5b2bc68fc6901fc5dbe098ced11`. Ordinary repository-root `git ls-tree --full-tree` and exact blob reads show:

- `tools/quality/validation/check_layer3_gy_loop_artifacts.py`: present with raw SHA256 `74fa3d23f55f25e4dbb2c42bbb4add802799e5545a2807514c3b9b156217471b`.
- `tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py`: absent from this HEAD (not null and not an unreadable blob).

The completed native/correction receipts measured later uncommitted epochs. The final current source alone cannot reproduce their whole-source fences; these small reverse patches preserve the otherwise missing replay inputs without whole source snapshots. They are necessary source deltas rather than redundant views of a committed source file. The current anchoring hashes above, not a guessed future SHA, decide whether they apply.

If another product-source change lands before final commit, append its minimal exact reverse delta or reestablish reconstruction from the true committed input. Never silently relabel this whole-source equality. Parent owns final retention/commit/readback; no docs retention or replay manifest issuance is authorized by this note. No scientific, source-authenticity or positive-admission claim is made.

The first auxiliary Git-presence attempt accidentally applied a product-relative cwd prefix to a repository-root path; it was corrected with `--full-tree` at the repository root. This affected only that metadata attempt, not the independently verified complete source fences or patch hashes. The explicit present/absent rows above are the corrected readback.
