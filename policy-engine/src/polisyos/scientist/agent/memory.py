"""
Short-term memory for the Reflexion pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TurnRole(str, Enum):
    USER = "user"
    PI = "pi"
    DRAFTER = "drafter"
    FORMALIZER = "formalizer"
    CRITIC = "critic"
    SYSTEM = "system"
    SELF_CRITIQUE = "self_critique"


@dataclass
class MemoryTurn:
    role: TurnRole
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Attempt:
    attempt_number: int
    draft_summary: str
    ir_summary: str
    critique_verdict: str
    critique_hint: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ShortTermMemory:
    """Short-term memory for a single experiment run."""

    def __init__(self, max_turns: int = 50, max_attempts: int = 10) -> None:
        self._turns: list[MemoryTurn] = []
        self._attempts: list[Attempt] = []
        self._max_turns = max_turns
        self._max_attempts = max_attempts
        self._hints: list[str] = []

    def add_turn(self, role: TurnRole | str, content: str, **metadata) -> None:
        """Add a conversation turn to memory."""
        if isinstance(role, str):
            role = TurnRole(role.lower())
        turn = MemoryTurn(role=role, content=content, metadata=metadata)
        self._turns.append(turn)
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns :]

    def add_attempt(
        self,
        draft_summary: str,
        ir_summary: str,
        critique_verdict: str,
        critique_hint: str,
    ) -> None:
        """Record a formalization attempt for Reflexion."""
        attempt = Attempt(
            attempt_number=len(self._attempts) + 1,
            draft_summary=draft_summary,
            ir_summary=ir_summary,
            critique_verdict=critique_verdict,
            critique_hint=critique_hint,
        )
        self._attempts.append(attempt)
        if critique_hint:
            self._hints.append(critique_hint)
        if len(self._attempts) > self._max_attempts:
            self._attempts = self._attempts[-self._max_attempts :]

    def add_pass_findings(
        self,
        pass_name: str,
        findings: list[dict[str, str]],
        cost_usd: float = 0.0,
    ) -> None:
        """Store multipass self-critique findings as a compact memory turn."""
        if not findings:
            return
        top_findings = findings[:5]
        summary = "; ".join(
            f"{item.get('severity', '?').upper()}: {item.get('description', '')[:100]}"
            for item in top_findings
        )
        content = f"[Self-Critique:{pass_name}] {summary}"
        self.add_turn(
            TurnRole.SELF_CRITIQUE,
            content,
            pass_name=pass_name,
            findings_count=len(findings),
            cost_usd=round(max(cost_usd, 0.0), 6),
        )

    def get_hints(self) -> list[str]:
        """Get all accumulated hints from Critic reviews."""
        return self._hints.copy()

    def get_last_hint(self) -> str | None:
        """Get the most recent hint."""
        return self._hints[-1] if self._hints else None

    def get_history_as_text(self, last_n: int | None = None) -> str:
        """Format conversation history as text for LLM context."""
        turns = self._turns[-last_n:] if last_n else self._turns
        lines = [f"[{turn.role.value.upper()}]: {turn.content}" for turn in turns]
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all memory."""
        self._turns.clear()
        self._attempts.clear()
        self._hints.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize memory to dictionary."""
        return {
            "turns": [
                {
                    "role": turn.role.value,
                    "content": turn.content,
                    "timestamp": turn.timestamp.isoformat(),
                    "metadata": turn.metadata,
                }
                for turn in self._turns
            ],
            "attempts": [
                {
                    "attempt_number": attempt.attempt_number,
                    "draft_summary": attempt.draft_summary,
                    "ir_summary": attempt.ir_summary,
                    "critique_verdict": attempt.critique_verdict,
                    "critique_hint": attempt.critique_hint,
                    "timestamp": attempt.timestamp.isoformat(),
                }
                for attempt in self._attempts
            ],
            "hints": self._hints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShortTermMemory":
        """Deserialize memory from dictionary."""
        memory = cls()
        for turn_data in data.get("turns", []):
            memory.add_turn(
                turn_data["role"],
                turn_data["content"],
                **(turn_data.get("metadata") or {}),
            )
        for attempt_data in data.get("attempts", []):
            if not isinstance(attempt_data, dict):
                continue
            memory.add_attempt(
                attempt_data.get("draft_summary", ""),
                attempt_data.get("ir_summary", ""),
                attempt_data.get("critique_verdict", ""),
                attempt_data.get("critique_hint", ""),
            )
        memory._hints = data.get("hints", [])
        return memory
