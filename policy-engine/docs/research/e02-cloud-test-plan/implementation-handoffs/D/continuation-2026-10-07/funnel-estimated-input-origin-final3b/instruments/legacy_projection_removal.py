"""Interpreter-only removal of the reported-subset admission predicate.

Retain estimated fields, typed settlement/event markers and ordinary consumers.
Never rewrite tracked production source or canonical B ledger/decoder code.
"""
import hashlib
import inspect
import json
from pathlib import Path
import textwrap


def pytest_configure(config):
    from polisyos.scientist.methods.search.funnel import orchestrator

    original = orchestrator.FunnelOrchestrator.advance
    source = inspect.getsource(original)
    amount = "str(sum(reported_inputs, Decimal(0))) if reported_inputs else None"
    status = 'else "reported"\n                        if reported_inputs\n                        else "not_reported"'
    assert source.count(amount) == 1
    assert source.count(status) == 1
    widened = source.replace(
        amount,
        "str(sum(reported_inputs, Decimal(0))) if reported_inputs or not unknown_input else None",
    ).replace(
        status,
        'else "reported"\n                        if reported_inputs or not unknown_input\n                        else "not_reported"',
    )
    retained = (
        'feedback["resource_estimated_input_usd"]',
        'feedback["resource_estimated_input_status"]',
        'feedback["resource_settlement_pending"]',
        'feedback["resource_settlement_status"]',
        'feedback["resource_unknown_ack_readback_ids"]',
        '"payload_digest": value.event.payload_digest',
        '"budget_keys": list(value.budget_keys)',
        'else "not_reported"',
    )
    assert all(token in source and token in widened for token in retained)
    namespace = dict(original.__globals__)
    exec(compile(textwrap.dedent(widened), "<D interpreter-only reported-subset removal>", "exec"), namespace)
    replacement = namespace[original.__name__]
    replacement.__qualname__ = original.__qualname__
    replacement.__module__ = original.__module__
    orchestrator.FunnelOrchestrator.advance = replacement
    record = {
        "scope": "Interpreter-only predicate removal, not a product-source change or inherited-red attribution",
        "source_path": original.__code__.co_filename,
        "function": original.__qualname__,
        "original_function_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "removed_function_sha256": hashlib.sha256(widened.encode()).hexdigest(),
        "changed_predicates": ["reported amount subset admission", "reported status subset admission"],
        "retained_tokens": list(retained),
        "expected_divergence": "estimated-only known input produces old synthetic reported zero; estimated and pending markers remain",
    }
    Path("/dev/shm/e02-D-funnel-oct07/estimated-origin-removal-installed.json").write_text(json.dumps(record, indent=2) + "\n")
