# ORCH03 intake/admission transport review

Read-only verification for intake `de7b08ebbac72232c98d96ea74c3c0410864a7ba` (tree `fe76cc863f551b834b29aa78b659f688d52b1fad`) against base `3a9e374a7d23a67e31fff073bebf164d61c0ab41` (tree `682b043138464c912dd728c12e80049dd44b47f1`) and fetched dispatch inputs. No scripts from the pack, tests, source, environment, refs, or worktrees were executed or changed. The seven gzip JSON payloads were streamed into bounded memory for SHA/length and JSON metadata comparisons only; nothing was extracted to disk.

## Commit and input identity

- `3a9e` → `386c50cdf9306a76816ea30110c8595f9e46c312` adds only `implementation-handoffs/ORCH03/parallel-20261008-intake.json`. `de7b08e` is its child and adds only the admission `manifest.json` plus seven `.json.gz` outputs. The complete base→head delta is nine added paths, all beneath `implementation-handoffs/ORCH03/`; there is no new product source/test/config path.
- `manifest.intake_commit` equals `386c50…`; the intake bytes at that commit equal the copy at `de7b08e`. All 11 `intake.input_manifest` references were read from exact fetched-G `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b` and matched the recorded Git blob, byte count and SHA-256.
- `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b` / tree `d9a4e73a0e85fa11f865bf643c1b63fbe66c2767` is a docs-only child of G source pin `fe5ccf9ce90c336fff749da48bd0138d321baf23` / tree `17f2b3e019b7ae82b85ad10af52dd9fb14049617`. The intake is based on old F receipt `3a9e…`, not on G: G/f00 is not an ancestor of `de7b08e`, by design. The captured G/input reference is metadata, not a wholesale source merge. The dispatch in f00 pins `G=fe5ccf…`; its lane `initial_source_sha` is f00, whose added files are prompts/dispatch/docs.

## Gzip custody checks

For every row, stored byte count and SHA-256 matched the compressed Git blob; bounded gzip decode byte count and SHA-256 matched the manifest; decoded `requested`, `status` and `unresolved_inputs` matched the manifest. All seven statuses are `admitted`, with empty unresolved inputs. The six lane rows also match the intake lane’s create/resume fields (`requested`, status, decoded bytes/hash, unresolved list). C07/C08/C09 create and resume requests each name the same branch and absolute path. The root resume is a distinct manifest-only coordinator record.

| Output | Requested branch / path | Stored bytes · SHA-256 | Decoded bytes · SHA-256 |
|---|---|---|---|
| `root-resume.json.gz` (resume) | `codex/e02-F-closeout-20261006` · `/workspace/e02-F-closeout-20261006` | 11984 · `57009193b8819e7419171a1b881b88c60f94ab76c85efa2ba20093492b4828a3` | 147971 · `4d6f8573d44eb90b6fdc151b988fb1c04ca2c8f05f135febc999d10a60123536` |
| `c07-create.json.gz` | `codex/e02-E-c07-20261008` · `/dev/shm/e02-orch03-20261008/c07` | 12028 · `96af4f3060b5e2b326de5ff79fef3b192c02a8e33ba0738ca9e959266318bd29` | 147849 · `99435c62e397b68cea1df499fd33bd315356e924184f5573bf28ca2c77118f59` |
| `c07-resume.json.gz` | same C07 branch/path | 12530 · `3b3671d3e99a042f0bb274bb04263b9b72928398b515b029d68d2bce510085cb` | 153610 · `bb0e40fb0a887ce920ae42595839d104ffef7877ee43cfdf30873b26588cee7` |
| `c08-create.json.gz` | `codex/e02-F-c08-20261008` · `/dev/shm/e02-orch03-20261008/c08` | 12549 · `140617aa82eca369d2a9ce40b3e0627b20df5c17428e1675c512476801fc1ca5` | 153523 · `085dc629bd52f5949a5d51409ae9ba66bc6eab897bcfbe40c74a2ab4a9a79d54` |
| `c08-resume.json.gz` | same C08 branch/path | 12867 · `9a1df036722e9a7354fc3015b84e20e1b947459f6035a7bfc837e2e606fe5e9d` | 159284 · `9eef5cdece5fb027a9af391f58d59a2640f14f23cfb7ff04320f20bc5e37a85e` |
| `c09-create.json.gz` | `codex/e02-E-c09-20261008` · `/dev/shm/e02-orch03-20261008/c09` | 12880 · `f8c5eaf8d83eebfa8e889415c1ed835489833002d8b31cd3b0d9c1174f14d157` | 159197 · `c9c345bbb9de07585d23017f4d5be86f459911e68ddaa67c101034274ef89e5f` |
| `c09-resume.json.gz` | same C09 branch/path | 13192 · `e8dd7bb9747dd0132f2f67e87882cf60840e46677d2f55aad91a53d7bede2576` | 164958 · `6a2a61fb546416e8d65bdadadb9550c052279f6422ea025285c0ec4a01f551ef` |

## Current dispatch and source qualification

- Intake `dispatch_lease` copies for C07/C08/C09 match every corresponding current-dispatch role field. Each has one distinct `/root/c07`, `/root/c08`, or `/root/c09` source writer; every `root_source_writer` is false. The recorded duplicate-root check is false. Pairwise source-scope and test-selector checks among C07/C08/C09 have no intersections. Across dispatch roles, no source-scope overlaps remain after explicit exclusions; the only broad test-selector intersections are C01/C03 budget tests, and selectors are not write leases.
- **C07:** pins `E_source=8d8e7b319e7eb6b57bc4ab3c4db5ca3070393f8c`, `E=7bf53fd0cf69a568b37d8a881e26bfb16c315653`, `A=8bfea70b2e2090ad5c541b103b7521efc01b30eb`, `G=fe5ccf9…`. Its lease is the IR uncertainty/subject relation slice; it leads S1:B31 and supplies S3. Intake preserves B31's original A/EMP-01 finding ownership, with E as relation supplier; C10 owns the fresh ValuePort/S10 reader. No closure is assigned.
- **C08:** pins `F_source=852cc3707bfc7dee132ec07a9ed5adcb5911fdf2`, `F_receipt=3a9e374a7d23a67e31fff073bebf164d61c0ab41`, `G=fe5ccf9…`. F852 is already in G; the receipt is separate and not in G. C08 owns B214 graph/query plus R4/TMLE on its listed paths; C01 owns budget admission, C07 the central IR export, C11 builtin assembly. It must not re-import the F source wholesale.
- **C09:** pins the same exact E_source/E pair plus G and owns S2, V7 producer, V4 forecast supplier on separate calibration/UQ/DOE/backtesting scopes. Its fresh consumers and task routes remain C10/L02; S2/V7 wait on their relevant S1 decision/input, while the predictive V4 route can proceed independently.
- Ancestry is qualified: E_source is an ancestor of E, and neither is in G; A is not in G; F_source is in G, while F_receipt is not. Dispatch therefore provides the minimum distinct source/receipt/supplier inputs for these lanes without asserting their compatibility or source acceptance. Intake explicitly records `no_source_acceptance_inferred=true` and `formal_closure=not_assigned`.

The intake and manifest support transport/admission custody only. The importer result recorded in the intake was not rerun, and these receipts do not establish implementation, test success, or finding closure.
