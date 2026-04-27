# Scientist Best-in-Class Wave 1 Acceptance

Related references: [Scientist](index.md), [Best-in-class readiness](best-in-class-readiness.md), [Claims](claims.md), [Research DAG](research-dag.md), [Deep research evidence](deep-research-evidence.md), [Agent capability promotion](agent-capability-promotion.md), [Benchmark authority](benchmark-authority.md), [Human oversight](human-oversight.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`, `tools/ci/check_scientist_best_in_class_wave1.py`, `tools/ci/check_scientist_best_in_class_phase1_0.py`, `tools/ci/check_scientist_best_in_class_phase1_1.py`, `tools/ci/check_scientist_best_in_class_phase1_2.py`, `tools/ci/check_scientist_best_in_class_phase1_3.py`, `tools/ci/check_scientist_best_in_class_phase1_4.py`, `tools/ci/check_scientist_benchmark_authority.py`, `tools/ci/check_scientist_best_in_class_phase1_6.py`, `src/polisyos/scientist/claims/**`, `src/polisyos/scientist/research_dag/**`, `src/polisyos/scientist/evidence/**`, `src/polisyos/scientist/agent/promotion.py`, `src/polisyos/scientist/evals/**`, `src/polisyos/scientist/human_review/**`, and `tests/tools/test_scientist_best_in_class_wave1.py`.

Wave 1 acceptance is the closure contract for Scientist best-in-class phases
1.0 through 1.7. It does not add a new runtime feature. It verifies that the
new control surfaces agree: claim projection, evidence, readiness, research
DAG, agent promotion, BenchmarkAuthority and human review.

## Acceptance Matrix

| Phase | Acceptance state | Evidence |
| --- | --- | --- |
| 1.0 Status reconciliation | `closed` | [best-in-class-readiness.md](best-in-class-readiness.md), [scientist-capability-inventory.md](scientist-capability-inventory.md), `check_scientist_best_in_class_phase1_0.py`. |
| 1.1 Claim/Evidence/Readiness spine | `closed` | [claims.md](claims.md), `src/polisyos/scientist/claims/**`, `claims_ref` packet and governance projection, `check_scientist_best_in_class_phase1_1.py`. |
| 1.2 Research DAG runtime object | `closed` | [research-dag.md](research-dag.md), `src/polisyos/scientist/research_dag/**`, `research_dag_ref` sidecar, replay/diff tests, `check_scientist_best_in_class_phase1_2.py`. |
| 1.3 Deep research evidence stack | `closed` | [deep-research-evidence.md](deep-research-evidence.md), additive Scholar `WebEvidenceBundle` safety/quality fields, safe fetch/snippet/claim-support tests, `check_scientist_best_in_class_phase1_3.py`. |
| 1.4 Agent and tool runtime promotion gates | `closed` | [agent-capability-promotion.md](agent-capability-promotion.md), capability registry, tool contract summary, supervisor eval adapter, frontier projection, `check_scientist_best_in_class_phase1_4.py`. |
| 1.5 Benchmark authority and hidden eval packs | `closed` | [benchmark-authority.md](benchmark-authority.md), `BenchmarkAuthority` over `BenchmarkRegistry`, leakage/staleness/policy-case contracts, `check_scientist_benchmark_authority.py`. |
| 1.6 Human oversight and accountable release packets | `closed` | [human-oversight.md](human-oversight.md), review packets, decisions, queue, oversight policy, governance links and decision-packet validation, `check_scientist_best_in_class_phase1_6.py`. |
| 1.7 Wave 1 closeout | `closed` | This page, `check_scientist_best_in_class_wave1.py`, `tests/tools/test_scientist_best_in_class_wave1.py`. |

## Cross-Phase Invariants

Wave 1 is accepted only when all of the following are true:

- All phase gates 1.0, 1.1, 1.2, 1.3, 1.4, 1.5 and 1.6 pass.
- Selected decision-bearing workflows cannot publish naked decision text or
  numbers without a `claims_ref`.
- Decision packets expose both `claims_ref` and `research_dag_ref`, and mirror
  those refs through the packet artifact index.
- Agent and frontier default-enable paths cannot bypass `BenchmarkAuthority`.
- Human review status is explicit for high-risk and public-sector claims, and a
  packet cannot claim `human_reviewed` readiness without review refs.
- Deep-research evidence remains untrusted input: snippets, source quality and
  safety events can support claims, but retrieved text is not instruction
  context.

## Selected Workflow Coverage

The fail-closed Wave 1 acceptance surface applies to:

| Workflow | Required Wave 1 refs | Gate posture |
| --- | --- | --- |
| `scientist_policy_design` | `claims_ref`, `research_dag_ref`, optional human-review refs when high-risk | Naked claims fail closed when the flag is enabled. |
| `scientist_policy_verified` | `claims_ref`, `research_dag_ref`, optional human-review refs when high-risk | Legal and factual decision claims must project into the claim ledger. |
| `scientist_causal_full` | `claims_ref`, `research_dag_ref`, optional human-review refs when high-risk | Causal readiness and validity claims must remain tied to ledger/DAG evidence. |

Legacy artifacts without refs remain loadable, but they render an explicit
`legacy_missing` status instead of pretending to satisfy Wave 1 readiness.

## CI Gate

The Wave 1 gate checks:

- required deliverables exist;
- every earlier phase gate reports `passes_all = true`;
- local runtime fixtures prove naked decision claims are blocked in selected
  workflows when fail-closed mode is enabled;
- synthetic decision-packet refs for `claims_ref` and `research_dag_ref` remain
  coherent;
- agent and frontier default-enable fixtures remain blocked by benchmark
  authority when evidence is missing;
- high-risk public-sector review requires two-person human review and blocks
  `human_reviewed` readiness without refs;
- this page, the readiness page, the capability inventory, the Scientist index
  and mkdocs navigation all mention the Wave 1 acceptance surface.

Run:

```bash
uv run python tools/ci/check_scientist_best_in_class_wave1.py --repo-root . --output-format json --require-passing
uv run pytest tests/tools/test_scientist_best_in_class_wave1.py -q
```

The gate is deliberately offline. It does not call LLM providers, web search,
or live fetch tools.
