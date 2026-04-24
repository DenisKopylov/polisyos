"""Tests for RegistryAuditLog.export_jsonl fix (G-12)."""

from __future__ import annotations

import json

from polisyos.foundry.methods.registry import RegistryAuditLog


def test_export_jsonl_writes_valid_file(tmp_path):
    """Record events, export, and verify valid JSONL output."""
    log = RegistryAuditLog()
    log.record("register", "ns.method_a@1.0", caller="test", version="1.0")
    log.record("register", "ns.method_b@2.0", caller="test", version="2.0")

    out = tmp_path / "audit.jsonl"
    log.export_jsonl(out)

    text = out.read_text()
    lines = [line for line in text.strip().split("\n") if line]
    assert len(lines) == 2

    for line in lines:
        obj = json.loads(line)
        assert "event" in obj
        assert "fqn" in obj
        assert "timestamp" in obj
        assert "caller" in obj
        assert obj["event"] == "register"


def test_export_jsonl_empty_log(tmp_path):
    """Empty audit log produces an empty file."""
    log = RegistryAuditLog()
    out = tmp_path / "empty.jsonl"
    log.export_jsonl(out)

    text = out.read_text()
    assert text == ""
