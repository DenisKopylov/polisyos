# Agent Layer (`polisyos.scientist.agent`)

`agent` — опциональный контур генерации и ревью политики (PI -> Drafter -> Formalizer -> Critic).

## Роль в системе

- формирует `ProblemFrame` и декомпозирует задачу;
- генерирует черновик политики (`DraftResult`);
- формализует черновик в `TrinityBundle`;
- критикует IR и возвращает `CritiqueReport`;
- поддерживает self-healing артефакты (`FailureCard`, `ReflexionOrchestrator`).

Важно: default workflow `run_experiment()` этот контур автоматически не запускает.

## Ключевые модули

- `protocols.py` — typed async-протоколы `PIAgent`, `DrafterAgent`, `FormalizerAgent`, `CriticAgent` и базовые dataclass-модели.
- `pi.py` — `MockPIAgent`, `LLMPIAgent`.
- `drafter_clients.py` + `drafter_factory.py` — `MockDrafterAgent`, `LLMDrafterAgent`, фабрика `create_drafter_agent`.
- `formalizer.py` — `MockFormalizerAgent`, `LLMFormalizerAgent`.
- `critic.py` — `MockCriticAgent`, `LLMCriticAgent`, `create_critic_agent`.
- `drafter_multipass_parts.py` + `drafter_models.py` — multipass-режим drafter, конфиг и findings.
- `failure_card.py`, `reflexion.py`, `memory.py` — loop восстановления после ошибок.
- `rag.py`, `knowledge_base.py`, `norm_loader.py`, `feasibility*.py`, `code_verifier.py` — расширения для informed critique/drafting.

## Публичные точки входа

Через `polisyos.scientist.agent` экспортируются:

- протоколы и типы (`ProblemFrame`, `DraftResult`, `CritiqueReport`, ...);
- mock/LLM реализации агентов;
- `create_drafter_agent`, `create_critic_agent`;
- RAG/feasibility/verifier и вспомогательные классы.

`create_drafter_agent()` переключает режим по `POLISYOS_DRAFTER_MULTIPASS_MODE`:
- `off` (по умолчанию) -> single-pass `LLMDrafterAgent`;
- `active`/`shadow` -> `MultiPassLLMDrafter`.

## Минимальный сценарий (mock)

```python
import asyncio

from polisyos.scientist.agent import (
    MockPIAgent,
    MockDrafterAgent,
    MockFormalizerAgent,
    MockCriticAgent,
)


async def run() -> None:
    pi = MockPIAgent()
    drafter = MockDrafterAgent()
    formalizer = MockFormalizerAgent()
    critic = MockCriticAgent()

    frame = await pi.create_problem_frame("Reduce poverty through targeted transfers")
    draft = await drafter.draft_policy(frame)
    bundle = await formalizer.formalize(draft)
    report = await critic.critique(bundle, frame)
    print(report.verdict)


asyncio.run(run())
```

## Связи с другими директориями

- `ir` — целевой формат `TrinityBundle`.
- `llm`/`core.llm` — traced LLM клиенты.
- `governance`/`kernel` — источники feedback для reflexion.
- `search` — может использовать агента как candidate generator.

## Runtime env для gateway/multi-model

При запуске через runtime control (`/api/v1/control/runs/nl`) используются:

- `POLISYOS_LLM_MULTIMODEL_ENABLED`
- `POLISYOS_LLM_GATEWAY_BASE_URL`
- `POLISYOS_LLM_GATEWAY_API_KEY`
- `POLISYOS_LLM_GATEWAY_TIMEOUT_S`
- `POLISYOS_LLM_GATEWAY_MAX_RETRIES`
- `POLISYOS_LLM_GATEWAY_PROVIDER`
- `POLISYOS_LLM_CAPTURE_PROMPT`
- `POLISYOS_LLM_MAX_PROMPT_CAPTURE_CHARS`

Если gateway не сконфигурирован, модельный variant автоматически уходит в mock fallback (это фиксируется в status/notes варианта).
