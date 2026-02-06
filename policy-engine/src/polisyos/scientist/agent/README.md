# Agent Layer: Иерархическая система AI агентов

**Протокольная архитектура для генерации и валидации экономических политик**

Иерархическая система агентов (PI → Drafter → Formalizer → Critic) с self-healing через Reflexion pattern.

## Структура

```
agent/
├── protocols.py      # AgentRole, ProblemFrame, SubTask, CritiqueReport
├── pi.py            # PI Agent - декомпозиция задач
├── drafter.py       # Drafter Agent - генерация политик
├── formalizer.py    # Formalizer Agent - формализация в IR
├── critic.py        # Critic Agent - валидация политик
├── failure_card.py  # Self-healing артефакты
├── memory.py        # Conversation tracking
├── reflexion.py     # Intelligent error recovery
├── prompts.py       # LLM промпты
└── base.py          # Legacy поддержка
```

## Ключевые компоненты

- **Иерархическая система**: PI декомпозирует задачи, Drafter генерирует политики, Formalizer формализует в IR, Critic валидирует
- **Self-Healing**: FailureCard, ShortTermMemory, ReflexionOrchestrator для автономного исправления ошибок
- **Протоколы**: Typed contracts для всех взаимодействий между агентами
- **Mock реализации**: Полная система для тестирования без LLM зависимостей

## API Использование

```python
from polisyos.scientist.agent import MockPIAgent, MockDrafterAgent

# Создание агентов
pi_agent = MockPIAgent()
drafter_agent = MockDrafterAgent()

# Декомпозиция задачи
subtasks = await pi_agent.decompose_task("Reduce poverty through subsidies")

# Генерация политики
draft = await drafter_agent.draft(subtasks[0])
```

## Связи

- Интегрируется с **engine** layer через workflow nodes
- Использует **IR** модуль для TrinityBundle
- Поддерживает **llm** layer для LLM взаимодействий