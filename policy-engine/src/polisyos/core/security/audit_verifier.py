from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from polisyos.core.observability import get_metrics

from .audit_models import ChainedLogEntry


@dataclass
class ChainVerificationResult:
    total_entries: int = 0
    valid_entries: int = 0
    tampered_entries: list[int] = field(default_factory=list)
    missing_entries: list[int] = field(default_factory=list)
    chain_intact: bool = True
    first_tampered_sequence: int | None = None


class ChainVerifier:
    """Verify contiguous chained-audit segments for tamper evidence."""

    def verify_segment(self, entries: list[ChainedLogEntry]) -> ChainVerificationResult:
        result = ChainVerificationResult(total_entries=len(entries))
        if not entries:
            return result

        expected_seq = entries[0].sequence_number
        expected_prev_hash = entries[0].prev_hash

        for index, entry in enumerate(entries):
            if entry.sequence_number != expected_seq:
                if entry.sequence_number > expected_seq:
                    result.missing_entries.extend(range(expected_seq, entry.sequence_number))
                result.chain_intact = False

            computed = entry.compute_hash()
            if computed != entry.entry_hash:
                result.tampered_entries.append(entry.sequence_number)
                if result.first_tampered_sequence is None:
                    result.first_tampered_sequence = entry.sequence_number
                result.chain_intact = False
            elif index > 0 and entry.prev_hash != expected_prev_hash:
                result.tampered_entries.append(entry.sequence_number)
                if result.first_tampered_sequence is None:
                    result.first_tampered_sequence = entry.sequence_number
                result.chain_intact = False
            else:
                result.valid_entries += 1

            expected_seq = entry.sequence_number + 1
            expected_prev_hash = entry.entry_hash

        if entries[0].sequence_number == 0 and entries[0].prev_hash != ChainedLogEntry.genesis_prev_hash():
            result.chain_intact = False
            if result.first_tampered_sequence is None:
                result.first_tampered_sequence = 0

        return result

    def verify_jsonl_file(self, path: Path) -> ChainVerificationResult:
        entries: list[ChainedLogEntry] = []
        for raw in path.read_text("utf-8").splitlines():
            if not raw.strip():
                continue
            entries.append(ChainedLogEntry.model_validate_json(raw))
        result = self.verify_segment(entries)
        if result.tampered_entries:
            chain_id = entries[0].chain_id if entries else "unknown"
            get_metrics().record_audit_chain_tamper(
                chain_id=chain_id,
                count=len(result.tampered_entries),
            )
        return result
