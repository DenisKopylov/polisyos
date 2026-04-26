from __future__ import annotations

from polisyos.foundry.coupling.messages import (
    TARGET_DES,
    CouplingMessage,
    entity_index,
    sort_messages,
)


def test_entity_index_accepts_agent_ids_and_numeric_ids() -> None:
    assert entity_index("agent-1042") == 1042
    assert entity_index("17") == 17
    assert entity_index(3) == 3
    assert entity_index("agent") is None


def test_sort_messages_is_deterministic_for_same_time_messages() -> None:
    messages = (
        CouplingMessage(time=2.0, source="abm", target=TARGET_DES, kind="z", priority=2),
        CouplingMessage(time=1.0, source="abm", target=TARGET_DES, kind="a", priority=1),
        CouplingMessage(time=1.0, source="abm", target=TARGET_DES, kind="a", priority=0),
    )

    ordered = sort_messages(messages)

    assert [message.priority for message in ordered] == [0, 1, 2]
