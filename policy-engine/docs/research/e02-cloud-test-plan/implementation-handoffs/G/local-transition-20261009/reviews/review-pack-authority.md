# Skeptical review: unified local execution pack

Review scope: `execution-prompts/unified-local-2026-10-09/{README,CURRENT-STATE,EXECUTION-PLAN,DECISIONS,MASTER-PROMPT,TASKS,INPUTS}`. Read-only review; no tests, source edits, ref changes, or production access. Pending `PACK-VALIDATION.json` and G admission artifacts were intentionally excluded while G prepares them.

## Corrections before dispatch

### Blocking: the exact G base is local, not fetchable from the named remote branch

`INPUTS.json` and README pin development source `78be3aff64185e2de24abe710523e14491e36ba6` / tree `7dc9df15aebbdac1e2ba6ba894fff4c31b84b59c`. At review time the named checkout is attached to `codex/e02-integration` at that SHA, but `origin/codex/e02-integration` is only `dee58973f7673299070b7c7374f419b0adb8175c`; local G is ahead 52 commits. The MASTER-PROMPT instruction “Fetch опубликованный G checkpoint” cannot produce the pinned base and risks silently starting from the old remote tip.

Before dispatch, change this to: verify the existing local G checkout's branch/HEAD/tree/status read-only; create the separate candidate worktree/branch from the exact local `78be…` commit if available. If it is absent on the new executor, recover that exact commit from an explicitly named artifact/transfer channel and verify tree/parents. Never substitute remote `dee589…`, and do not publish integration merely to make it fetchable. This is the main execution blocker.

### High-priority input pin omission: current C05 source lane

`INPUTS.json` pins `origin/codex/e02-C-orch02-c05-r2-gproposal` at `42987be62c48356211e1ce4397ca67cd45249997`, tree `ab1aa6a9cfe98d4a613fe04f83cc4bd56124c628`. That is the G-proposal lane; it does not identify the separate C05 recovery lane containing source `5ccbfa15c5671623a4c1ff7a3145460c5ca5a857`, tree `9633ae3e5fdbdcc6a6a76af3d7ef29bdaa12fd09`, with handoff tip `eee090e345d1121d3d53cdd93a7ab32f818d5ef7`, tree `4a9af5064f47b795bfb5d00533b19f2e39bcb1c9`. All these objects/refs were present locally during review, but the pack does not name that recovery ref in `pinned_remote_heads`.

I1 asks the new root to compose C05's currentness/cache/session/WVS behavior and the prompt says its own-source is available. Add the exact recovery ref/head/tree and source-vs-handoff relationship, labelled candidate evidence rather than G acceptance. Keep the G proposal ref separately. Otherwise the executor may inspect only the older proposal or repeat discovery. This is a pack-intake correction, not a reason to wait for the cloud agent.

### Non-blocking freshness note: ORCH03 archive custody

`INPUTS.json` says the ORCH03 recovery archive remains on the VM with no local bytes/new source. A later user-provided report says a separate 31 MB archive was verified (276 members), but the corresponding `/workspace/ORCH03-r2-local-recovery-20261008.tar.gz` and report are not present at those paths in this G checkout. The plan's “try ordinary recovery once; if unavailable, reconstruct only the minimum necessary delta with a new identity” is sound and prevents waiting on the failed VM. Update the custody line to distinguish the verified archive in its prior workspace from unavailability on this executor, then have BOOT0 try that named transfer once. Do not treat the user's report as locally byte-verified here.

## Scope and authority findings

- **CAN:** The pack accurately bounds the admitted code to a strict reader of a *presented persisted profile*. It does not claim that this reader creates/attests producer profiles or settles Core-vs-IR law, raw-sidecar conformance, or profileless legacy history. Those are left as execution or G decision work. The pinned `328d91…` CAN handoff descends from source `2762cec3…`, so this source lineage is represented in the G base.
- **C10:** The pack calls out owner-bound recursion/context/CAS and records the one fresh final CAS selector check separately from a normal parsed served POST→N5→CAS→fresh-GET/browser positive. Missing DTO/intake/readers, N4 producer/qualified child profiles, and authentic root/context input are not papered over. This is bounded source, not full capability acceptance.
- **C11:** “bounded history/refit/intake” and the exact G-local 11-case result `4 PASS / 7 SKIP` are properly qualified; the task still requires an actual joined Search/receiver/MethodJob/CAS path and supported GP profile. SKIP is not reported as product failure or numerical success.
- **DFK:** The pack says the source is integrated with a serializer fix and treats the broader census/release/CLI companions and a supported Linux invalid-byte filename case as remaining work. It does not infer historical, external, ignored/binary retirement from the bounded local census. The pinned DFK handoff `6c565…` descends from source `3a0d5549…`; current G includes the forward JSON-emission fix at `78be…`.
- No formal G closures are claimed; author proposals remain separate from G adjudication. The 198/54/23/7 author-proposal distribution and 9/260/12/1 historical ledger are explicitly distinct. Original tasks number 23; the new plan has those 23 plus BOOT0/DX0/DEC0. All 282 original finding IDs route at least once across TASKS; no unknown dependency or dependency cycle was found.
- The prompt allows internal producer/API/DTO/UI/contract research and repair across prior team boundaries, while explicitly forbidding self-issued law, issuer, release/currentness, custody, production workload, causal calibration, or refinement authority. It also permits a controlled source-bound local witness without calling it live-production evidence. This is a sound boundary.
- The task is execution-oriented: it requires completing all ready work, reconstructing missing internal mechanisms after a bounded retrieval attempt, researching alternatives/prototypes for genuine contract ambiguity, and continuing independent work while G reviews. It does not instruct hourly polling or a return for generic permission. Append-only history, source freeze, independent reviews, and one composed expensive replay are stated coherently.

## Disposition

**Dispatch after the two blocking preflight corrections:** (1) use the exact local G base rather than claiming it is published/fetchable; (2) pin the current C05 recovery source/handoff lane separately from its proposal lane. The ORCH03 custody text should be refreshed but its prescribed recovery/reconstruction ladder is already adequate. No scope correction is needed for CAN/C10/C11/DFK or for the production/external-authority boundary.

No conclusion here admits source, accepts G integration, or adjudicates findings. The focused counts and final admission link remain subject to the separate deciding admission receipt that G is preparing.
