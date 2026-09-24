"""Production audit replay of response packets through the CR2/CR1 custody path.

This producer returns observations only. The independently owned oracle and grade
consumer live in tools/check_response_corpus.py; runtime does not import them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.runtime.quality import constrained_response as response

if TYPE_CHECKING:
    from pathlib import Path


def replay_corpus(*, root: Path, raw: bytes) -> list[dict[str, Any]]:
    """Run immutable inputs against real durable owners and return audit facts."""
    corpus = response.decode_packet(raw)
    if not isinstance(corpus, response.ResponseCorpus):
        raise ValueError("runtime_packet_decode_invalid")
    observations = []
    for packet in corpus.packets:
        runtime = response.ConstrainedResponseRuntime.open(
            root=root / packet.scenario_id, tenant_id="response-corpus", cell_id="candidate-audit"
        )
        tickets: dict[int, str] = {}
        prior_bytes: dict[str, str] = {}
        for offset, template in enumerate(packet.events):
            event = template.model_copy(
                update={"previous_ticket": tickets.get(template.sequence - 1)}
            )
            receipt = runtime.append(event)
            duplicate = event.sequence in tickets
            tickets[event.sequence] = receipt.ticket
            history_intact = all(
                runtime.read(ticket).model_dump_json() == before
                for ticket, before in prior_bytes.items()
            )
            prior_bytes[receipt.ticket] = receipt.model_dump_json()
            snapshot = runtime.custody.snapshot(receipt.ticket, as_of=datetime.now(UTC))
            observations.append(
                {
                    "scenario_id": packet.scenario_id,
                    "offset": offset,
                    "event_id": event.event_id,
                    "sequence": event.sequence,
                    "assessment": receipt.assessment.model_dump(mode="json"),
                    "status": receipt.status,
                    "reaction": receipt.reaction,
                    "request_ref": receipt.request_ref,
                    "decision_ref": receipt.decision_ref,
                    "ticket": receipt.ticket,
                    "previous_ticket": receipt.previous_ticket,
                    "history_intact": history_intact,
                    "duplicate": duplicate,
                    "missing_role": snapshot.missing_role,
                    "authority_predicate": "not_established",
                }
            )
    return observations
