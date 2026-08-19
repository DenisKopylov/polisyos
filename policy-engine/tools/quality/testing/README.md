# Testing Tools

`tools/quality/testing` содержит Phase 4 tooling для локального smoke path и экономики тестов.

## Команды

Рабочая директория: `policy-engine/`.

### Local integration stack

```bash
uv run python tools/quality/testing/local_integration_stack.py up
uv run python tools/quality/testing/local_integration_stack.py smoke
```

Что делает:

- поднимает fixture-backed Runtime API на `127.0.0.1:8000`;
- поднимает dashboard dev server на `127.0.0.1:5173`;
- проверяет `/health`, корневую страницу dashboard и proxy health на `/api/v1/health`;
- в режиме `smoke` запускает `corepack pnpm run test:e2e:smoke` и затем корректно останавливает стек.

### Test economics report

```bash
uv run python tools/quality/testing/report_test_economics.py \
  --report quality=_build/.tmp/test-reports/quality-and-unit.xml \
  --report runtime-http=_build/.tmp/test-reports/runtime-http.xml \
  --report integration=_build/.tmp/test-reports/integration.xml \
  --allow-missing \
  --output _build/.tmp/test-reports/test-economics-summary.md
```

Что рендерит:

- totals по suite lanes;
- top slowest tests;
- active/expired quarantines из `tests/quarantine.toml`.

### Playwright quarantine guardrail

```bash
uv run python tools/quality/testing/check_playwright_quarantines.py
```

Что валидирует:

- каждый `@flaky` / `@quarantine` Playwright test имеет запись в `tests/quarantine.toml`;
- selector для `runner = "playwright"` совпадает с полным tagged title теста;
- в registry нет устаревших Playwright selectors, которые больше ни на что не указывают.

### E11 review freeze and batch gate

`review_freeze.py` is E11's lane-local, committed freeze/disposition bridge. It owns the minimum
append-only scheduling record that the existing `build_review_package.py` does not own, then hands
the packager raw checklist bytes unchanged. It is deliberately a direct script: this is
`implemented_but_not_orchestrated`, not a new unified-tool registry or a claim that replay producers
are automatically wired to require it.

From the repository worktree root, declare one lane's required independent-review roster and append
a candidate freeze. The marker is not a frozen boundary until the exact ledger bytes are committed.
The ledger must live at `.e11/<lane>.ledger`; opaque results, findings, checklists, and packages
must live below ignored `tmp/e11/` and remain byte-for-byte available while the ledger is consumed.
Use one ledger per lane wave; a later independent wave opens a new ledger rather than rewriting or
reopening a closed transcript.

```bash
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  open --lane gy-def6 --receipt-chain layer3-gy-confidence-chain \
  --review-base <prior-reviewed-commit> \
  --required-review architecture --required-review quality \
  --at 2026-08-08T12:00:00Z
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  freeze --lane gy-def6 --receipt-chain layer3-gy-confidence-chain \
  --at 2026-08-08T12:01:00Z
git add .e11/gy-def6.ledger
git commit -m "chore: freeze GY-DEF6 review source"
```

`--review-base` is frozen with the opening roster: it must be an ancestor of, and different from,
the frozen source commit. Full packages are accepted only from that exact base to the frozen source;
successor delta packages are accepted only from their superseded freeze's source to the repaired
source. An empty canonical package therefore cannot be used as a review receipt.

The freeze recomputes an implementation-source identity over all tracked `policy-engine/` paths
except `policy-engine/docs/`, `policy-engine/architecture/`, and the exact ledger file. There is no
caller-supplied receipt exclusion: that would let a declaration hide source movement. The ledger's
transient lock is also excluded so the gate can atomically append its own marker. The gate also
fails closed when a source path is marked assume-unchanged or skip-worktree, or when local Git stat
cache settings weaken freshness checks. E11 does **not** use E12's authority import closure—E12
binds an artifact's identity, whereas this boundary binds reviewed implementation source. This
choice intentionally does not cover ignored/untracked ambient inputs, runtime environment,
documentation, governed-artifact semantics, reviewer independence, or receipt-chain semantics.

Build a full package for the frozen source with the existing packager, commit the byte binding, and
record one opaque result for every named reviewer. The gate recomputes the package bytes with the
canonical packager and re-binds package/result bytes at every consuming operation. Roster membership
and presence are recomputed; actual reviewer identity, independence, and real-world completeness
remain institutionally supplied. Missing required results fail closed.

```bash
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  build-full --lane gy-def6 --freeze-id <freeze-id> \
  --base <review-base> --head <frozen-source-commit> \
  --output tmp/e11/gy-def6.full.review
git add .e11/gy-def6.ledger && git commit -m "chore: bind GY-DEF6 full review package"

# The reviewer writes opaque bytes below ignored tmp/e11/.
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  record-review-result --lane gy-def6 --freeze-id <freeze-id> \
  --package-id <package-id> --reviewer architecture \
  --result tmp/e11/architecture.result --at 2026-08-08T12:10:00Z
git add .e11/gy-def6.ledger && git commit -m "chore: bind architecture review result"
```

Disposition consumes a result ID, so a finding is traceable to a package bound to the frozen source.
Normal human classifications are always conservative while frozen:

```bash
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  disposition --lane gy-def6 --finding-id DEF6-001 --finding tmp/e11/DEF6-001.review \
  --declared-class blocking --classification-provenance institutionally_supplied \
  --review-result-id <architecture-result-id> --at 2026-08-08T12:11:00Z
```

The v1 debt path is deliberately narrow: only a re-run, byte-bound Ruff `I001` import-order
diagnostic is `recomputed` and may become `debt`. Docstring, naming, style synonyms, missing
evidence, and institutional classifications conservatively become `batch`; a false `cosmetic`
declaration cannot produce debt. The ledger re-runs that I001 predicate when it is read, so a
self-hashed hand-authored `debt` event is rejected too. This sole permissive path intentionally
does not consume a caller-supplied review base or roster: it is a source-local scheduling debt,
not proof that the independent reviews are complete, and it cannot advance `replay`.

```bash
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  derive-ruff-i001 --source-path <policy-engine-source-with-I001> --output tmp/e11/I001.review
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  admit-ruff-i001 --lane gy-def6 --finding tmp/e11/I001.review \
  --at 2026-08-08T12:11:00Z
```

An open batch blocks `replay`. After one or more accepted repairs, commit the source, append and
commit a superseding freeze, then pass every carried unresolved member to the existing delta
packager. Build the delta **before** resolving its members; the delta package preserves the exact
raw finding bytes as `--prior-findings`.

```bash
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  freeze --lane gy-def6 --receipt-chain layer3-gy-confidence-chain \
  --supersedes-freeze-id <old-freeze-id> --at 2026-08-08T12:20:00Z
git add .e11/gy-def6.ledger && git commit -m "chore: freeze repaired GY-DEF6 source"
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  build-delta --lane gy-def6 --freeze-id <successor-freeze-id> \
  --checklist-output tmp/e11/gy-def6-batch.checklist \
  --base <old-frozen-source-commit> --head <repair-commit> \
  --output tmp/e11/gy-def6-delta.review
git add .e11/gy-def6.ledger && git commit -m "chore: bind GY-DEF6 delta review package"
```

After every required reviewer records a result for the successor delta, resolve each carried member
with a structural witness. Build the delta before resolving members; a free-form “done” string is
refused.

```json
{"accepted":true,"finding_id":"DEF6-001","repair_freeze_id":"<successor-freeze-id>","review_result_sha256":"sha256:<delta-result-digest>","schema_version":"policyos.review_freeze.resolution.v1"}
```

```bash
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  resolve --lane gy-def6 --finding-id DEF6-001 \
  --review-result-id <delta-result-id> --resolution tmp/e11/DEF6-001.resolution.json \
  --at 2026-08-08T12:30:00Z
git add .e11/gy-def6.ledger && git commit -m "chore: bind GY-DEF6 batch resolution"

# The receipt must already be a committed governed artifact owned by the chain workflow.
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  replay --lane gy-def6 --freeze-id <successor-freeze-id> \
  --receipt policy-engine/architecture/policy_design_case/<replay-receipt>.json --at 2026-08-08T12:31:00Z
git add .e11/gy-def6.ledger && git commit -m "chore: record GY-DEF6 replay receipt"
python3 policy-engine/tools/quality/testing/review_freeze.py \
  --ledger .e11/gy-def6.ledger \
  close --lane gy-def6 --freeze-id <successor-freeze-id> --at 2026-08-08T12:32:00Z
git add .e11/gy-def6.ledger && git commit -m "chore: close GY-DEF6 scheduling ledger"
```

`replayed` and `closed` are explicitly **E11 scheduling-ledger states only**. They carry
`state_scope=e11_scheduling_ledger_only`, `state_claim_grade=degraded_institutional_scheduling_record`,
and `state_semantic_validity=not_established`: the tool content-binds an already committed receipt
but cannot establish its chain membership, semantic validity, reviewer independence, or repair
acceptance. The ledger, checklist, and generated I001 evidence carry `research_only: true`,
`authoritative_for`, and `may_not_use_for` boundaries. The unchanged canonical review package and
opaque external inputs retain their own formats; this bridge does not relabel them or authorize
implementation, appoint an owner, validate receipt semantics, or amend a plan.

### Mutation testing

```bash
uv run python tools/quality/testing/mutation.py --suite foundry --target backends
uv run python tools/quality/testing/mutation.py --suite scientist --target governance
uv run python tools/quality/testing/mutation.py --suite scientist --target all
uv run python tools/quality/testing/mutation.py --suite foundry --target results
```

Что делает:

- предоставляет canonical mutation-testing surface через `polisyos-tools`;
- запускает `mutmut` по reviewed Foundry/Scientist target maps;
- считает kill rate и валидирует threshold в одном месте.

## Sharding guidance

Инструменты раннеров уже поддерживают нативное шардирование:

- `pytest`: шардировать по top-level directories и historical durations;
- `vitest`: `vitest --shard=<index>/<count>`;
- `playwright`: `playwright test --shard=<index>/<count>`.

Политика и рекомендуемые границы описаны в [`tests/TESTING_POLICY.md`](/Users/deniskopylov/polisyos/policy-engine/tests/TESTING_POLICY.md).
