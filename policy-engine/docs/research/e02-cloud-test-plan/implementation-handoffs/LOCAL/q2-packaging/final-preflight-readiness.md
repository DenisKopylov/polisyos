# Q2 installed-wave preflight readiness

Captured 2026-10-10. This closes the selector denominator and binding preflight only. It does not claim a final frozen source SHA, build a wheel/sdist/GCP archive, install a package, or run the installed consumer bodies.

The primary runner now consumes the exact `current_primary_suite` set in [installed-wave-manifest.json](installed-wave-manifest.json). It names all 125 source-qualified pytest IDs and binds the list to a canonical sorted-ID SHA-256 of `61189a3b41592600556a7d63dff970fd05358a406ee8598b7211f0f6535aafd8`. The five whole-file selectors plus nine additional consumer selectors collected exactly 125/125 with no missing, extra, or duplicate IDs. The historical 91 baseline JUnit IDs plus nine selected consumers remain a named, required 100-ID subset with SHA-256 `a1da373ad502cb17fe1932757cae15fd91450063587720e1ec727e32676f751b`.

The manifest binds the seven selected test files by exact SHA-256. Before a wave, the runner checks that path set, current bytes, sorted unique IDs, declared count and digest, required historical subset, and required additional selectors agree. The transitive fixture binder now resolves every one of the 125 selected IDs; its current source collection covers 82 unique test function bodies, including all declared `dowhy` and `gcm` fixture callbacks. A lightweight negative control removes a current ID while leaving the manifest digest stale and confirms the runner refuses it. The timeout driver and supplemental runner reconcile the same full current collection and JUnit set; subsequent profile timeouts are authorized only by an immediately preceding exact-set, zero-skip/failure/error pass.

The supplement no longer carries a second hardcoded primary denominator. It names the primary selector contract as `current_primary_suite`, verifies all three primary profiles against that exact set and their installed origins, and separately collects its six supplemental IDs. Its own collection was exact 6/6. `hatch.toml` still declares the same 11 force-includes; the preflight confirmed their source byte counts and SHA-256 values match the manifest and current Hatch/sdist configuration. The actual source-wheel → sdist rebuild → GCP archive rebuild → installed consumers and all 11 installed asset bytes remain pending the frozen Linux wave.

The retained source-only collection and complete command record are in [raw/final-preflight-20261010-r6](raw/final-preflight-20261010-r6). The run used the worktree `.venv` Python 3.14.3, explicit catalog/profile expectation fixtures, `PYTHONPATH=src:.`, and `PYTHONDONTWRITEBYTECODE=1`. It ran `pytest --collect-only`; no test bodies ran. The full 125 and six-ID sets, transitive binding receipt, eleven asset rows, inputs, and commands are in `results.json`. The primary and supplement exits were 0 and `overall` is true. The result is SHA-256 `f048a16cc23a3d18c1557b64b6faf558debc3ce1a54940d29ef7a478439983f8`; complete stdout/stderr remain beside it.

The lightweight timeout harness passed 12/12 cases, including exact current-set and stale-ID-digest refusal, a same-count wrong-ID refusal, failed-prior-profile blocking, actual timeout/nonzero child stream retention, stream tamper detection, and nonregular-file controls. Its full deciding output and harness report are retained in [raw/timeout-driver-harness](raw/timeout-driver-harness); this is runner-mechanism verification, not a package-wave result. The four runner/harness modules also passed `py_compile`. Ruff was run on the four raw runner/harness modules against the pre-edit backup; the configured check had no new diagnostic signatures and six fewer findings overall, while the raw utility files remain non-clean under the repo-wide rule set.

Current runner input hashes for the Linux transport owner to bind are:

~~~text
run.py                     c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf
timeout_driver.py          7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073
installed-wave-manifest    26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6
supplemental_run.py        4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49
supplemental-manifest      ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df
~~~

The final source commit/tree is still unassigned. After freeze and the separate input review, use the already prepared Linux transport recipe and root-admitted serialized Q2 slot. Its old copy-time hashes and text describing a 100-node primary suite must be refreshed from these inputs before transport; this note does not authorize or start that wave.
