"""Constraint context normalization for drafter/critic prechecks.

This module bridges two coexisting ProblemFrame contracts:
- Agent-level dataclass (`scientist.agent.protocols.ProblemFrame`)
- IR-level typed model (`ir.problem_frame.ProblemFrame`)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from polisyos.ir.governance.problem_frame import ConstraintSpec
from polisyos.ir.governance.problem_frame import ProblemFrame as IRProblemFrame
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.scientist.agent.protocols import ProblemFrame as AgentProblemFrame

_BUDGET_HINT_RE = re.compile(
    r"(budget|spend|spending|cost|envelope|cap|ceiling|allocation)",
    flags=re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_PATH_NUMBER_RE = re.compile(r"\[(\d+)\]")

_OPERATOR_TEXT: dict[str, str] = {
    "<": "be less than",
    "<=": "not exceed",
    "==": "equal",
    "!=": "not equal",
    ">=": "be at least",
    ">": "be greater than",
}


@dataclass(frozen=True, slots=True)
class NormalizedConstraint:
    """Constraint normalized into text + optional numeric value for prechecks."""

    constraint_id: str
    text: str
    hard: bool
    source_kind: str
    operator: str | None = None
    numeric_value: Decimal | None = None
    slot_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConstraintContext:
    """Unified constraint context for downstream constitution and critic checks."""

    domain: str
    hard_constraints: tuple[NormalizedConstraint, ...]
    soft_constraints: tuple[NormalizedConstraint, ...]
    budget_envelope: Decimal | None
    source_kind: str

    @property
    def total_constraints(self) -> int:
        return len(self.hard_constraints) + len(self.soft_constraints)


class ConstraintContextAssembler:
    """Builds a typed `ConstraintContext` from Agent or IR ProblemFrame."""

    def build(
        self,
        problem_frame: AgentProblemFrame | IRProblemFrame | None,
    ) -> ConstraintContext:
        if problem_frame is None:
            return ConstraintContext(
                domain="general",
                hard_constraints=(),
                soft_constraints=(),
                budget_envelope=None,
                source_kind="none",
            )

        if isinstance(problem_frame, IRProblemFrame):
            return self._from_ir(problem_frame)

        return self._from_agent(problem_frame)

    def _from_ir(self, problem_frame: IRProblemFrame) -> ConstraintContext:
        hard: list[NormalizedConstraint] = []
        soft: list[NormalizedConstraint] = []
        budget_candidates: list[Decimal] = []

        for spec in problem_frame.hard_constraints:
            normalized = self._normalize_ir_constraint(spec, hard=True)
            hard.append(normalized)
            maybe_budget = self._extract_budget_candidate_from_ir(spec)
            if maybe_budget is not None:
                budget_candidates.append(maybe_budget)

        for spec in problem_frame.soft_constraints:
            soft.append(self._normalize_ir_constraint(spec, hard=False))

        domain = str(getattr(problem_frame.domain, "value", problem_frame.domain or "general"))
        budget_envelope = min(budget_candidates) if budget_candidates else None

        return ConstraintContext(
            domain=domain,
            hard_constraints=tuple(hard),
            soft_constraints=tuple(soft),
            budget_envelope=budget_envelope,
            source_kind="ir_problem_frame",
        )

    def _from_agent(self, problem_frame: AgentProblemFrame) -> ConstraintContext:
        hard: list[NormalizedConstraint] = []
        budget_candidates: list[Decimal] = []

        for idx, raw in enumerate(problem_frame.constraints):
            text = str(raw).strip()
            if not text:
                continue
            numeric = self._extract_first_decimal(text)
            hard.append(
                NormalizedConstraint(
                    constraint_id=f"agent_constraint_{idx + 1}",
                    text=self._sanitize_text(text),
                    hard=True,
                    source_kind="agent_problem_frame",
                    operator=None,
                    numeric_value=numeric,
                )
            )
            if self._looks_like_budget(text) and numeric is not None:
                budget_candidates.append(abs(numeric))

        return ConstraintContext(
            domain=(problem_frame.domain or "general"),
            hard_constraints=tuple(hard),
            soft_constraints=(),
            budget_envelope=min(budget_candidates) if budget_candidates else None,
            source_kind="agent_problem_frame",
        )

    def _normalize_ir_constraint(self, spec: ConstraintSpec, *, hard: bool) -> NormalizedConstraint:
        operator = spec.operator
        op_text = _OPERATOR_TEXT.get(operator or "", "satisfy")
        constraint_id = spec.constraint_id

        if isinstance(spec.value, MoneyValue):
            value_text = f"{spec.value.amount} {spec.value.currency}"
            numeric = Decimal(spec.value.amount)
            if spec.value.nominal_year is not None:
                value_text = f"{value_text} ({spec.value.nominal_year} nominal)"
        elif isinstance(spec.value, RateValue):
            suffix = "%" if spec.value.base == "percent" else ""
            value_text = f"{spec.value.value}{suffix}"
            numeric = Decimal(spec.value.as_ratio())
        elif isinstance(spec.value, CountValue):
            label = spec.value.label or "units"
            value_text = f"{spec.value.value} {label}"
            numeric = Decimal(spec.value.value)
        elif isinstance(spec.value, DurationValue):
            value_text = f"{spec.value.value} {spec.value.unit}"
            numeric = Decimal(spec.value.value)
        else:
            value_text = str(spec.value)
            numeric = self._extract_first_decimal(value_text)

        text = f"{constraint_id} MUST {op_text} {value_text}."
        if spec.notes:
            notes = "; ".join(self._sanitize_text(note) for note in spec.notes if note)
            if notes:
                text += f" Notes: {notes}."

        return NormalizedConstraint(
            constraint_id=constraint_id,
            text=text,
            hard=hard,
            source_kind="ir_problem_frame",
            operator=operator,
            numeric_value=numeric,
            slot_id=spec.slot_id,
        )

    def _extract_budget_candidate_from_ir(self, spec: ConstraintSpec) -> Decimal | None:
        id_or_slot = f"{spec.constraint_id} {spec.slot_id or ''}".lower()
        notes_blob = " ".join(spec.notes).lower()
        hint_blob = f"{id_or_slot} {notes_blob}"
        if not _BUDGET_HINT_RE.search(hint_blob):
            return None

        if isinstance(spec.value, MoneyValue):
            return abs(Decimal(spec.value.amount))
        numeric = self._extract_first_decimal(str(spec.value))
        if numeric is None:
            return None
        return abs(numeric)

    @staticmethod
    def _extract_first_decimal(text: str) -> Decimal | None:
        match = _NUMBER_RE.search(text)
        if match is None:
            return None
        try:
            return Decimal(match.group(0))
        except InvalidOperation:
            return None

    @staticmethod
    def _looks_like_budget(text: str) -> bool:
        return _BUDGET_HINT_RE.search(text) is not None

    @staticmethod
    def normalize_location(location: str) -> str:
        if not location:
            return ""
        return _PATH_NUMBER_RE.sub("[]", location)

    @staticmethod
    def _sanitize_text(text: str) -> str:
        sanitized = text.replace("\r", " ").replace("\n", " ").strip()
        sanitized = re.sub(r"\s+", " ", sanitized)
        return sanitized[:500]


def extract_budget_envelope(
    problem_frame: AgentProblemFrame | IRProblemFrame | None,
) -> Decimal | None:
    """Convenience helper for quick budget extraction from any ProblemFrame variant."""

    assembler = ConstraintContextAssembler()
    return assembler.build(problem_frame).budget_envelope


__all__ = [
    "ConstraintContext",
    "ConstraintContextAssembler",
    "NormalizedConstraint",
    "extract_budget_envelope",
]
