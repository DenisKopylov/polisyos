# C12 real HTTP witness output scope

**Proposal only; not applied or executed.** The product-script preimage remains `LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.py` at SHA-256 `b7e656b6f0653821228d5ca5ee2f2521893df419a8a782e8c156a289ce6833ab`. The unapplied one-file patch is `LOCAL/raw/c12-real-http-output-scope.patch`, SHA-256 `a666173ee65c8cc99a3a4f202fba05fa49e4b407a7355429616d61c619831984`. The patch deletes the random output path under the source/profile directory, requires an absolute `--case-root`, refuses an existing (including dangling-symlink) target and any target that overlaps the script/profile tree, then reserves the target with `mkdir(..., exist_ok=False)`. It removes the `uuid` dependency. It does not change the producer, request intent, selected generation, encoder, or HTTP assertions.

## Planned invocation

Working directory is `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`. After the patch is applied to the script, the root-owned source freeze is refreshed, and the output path is declared in the plan, the invocation is:

```sh
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src:. \
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/venv/bin/python \
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.py \
  --case-root /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/c12-real-http/case
```

The script continues to resolve the model from its own `ROOT/hf-cache`, so the profile, 143-package interpreter, and model snapshot stay in their existing read-only input locations. The case root owns all witness outputs: `output/lex_knowledge_graph.duckdb`, selected embedding generations and HNSW indexes, `runtime-cas/`, `runtime-cache/`, and `result.json`. A separate root capture should write logs/exit/timing/RSS under its already declared capture directory. The proposed case path is outside the script/profile tree and must be absent at invocation; the final plan must bind that exact absent output root before running.

## Required frozen inputs and retained behavior

Before execution, bind the post-patch witness script bytes and the final committed product source/import tree. The script imports the actual Legal generation builder/projections, `LegalQueryProfile`, immutable `LegalQueryGenerationIntentV1`, HTTP app/container/provider, and test client. Rebind the isolated interpreter entrypoint, `pyvenv.cfg`, all 143 installed distributions and module origins. Keep the existing model ID/revision and all nine content-hashed files from `asset-file-manifest.txt` (SHA-256 `191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca`) unchanged, and include that manifest and the command/profile records as explicit inputs in the root freeze.

The real producer must still generate entity, fact, and provision embeddings from the pinned local E5 model; select complete generations; recompute members; and prove the encoder-bound generator rule. After releasing the producer, a distinct fresh real encoder must serve the selected immutable profiles through the actual in-process `POST /api/v1/control/lex/search` consumer. Preserve the positive vector-mode/result assertion and the stale-fact-generation control requiring text fallback with `query_profile_stale_or_mismatched`. The fixture is synthetic; this is a compatibility witness, not production authority, verified legal grounding, or a live-catalog currentness claim.

The run remains unperformed until source/input freeze and plan binding are complete. The earlier model attempt failed before generation publication and before either HTTP request; the tokenizer-only follow-up does not substitute for this witness. No source, environment, asset, output directory, or product API was changed by preparing this patch artifact.
