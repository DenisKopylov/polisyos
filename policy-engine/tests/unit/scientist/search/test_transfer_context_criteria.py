"""Original context acceptance controls without a new tenant policy."""

from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    resolve_transfer_context,
)


def test_nested_serialized_and_equivalent_explicit_fields_have_the_same_scope():
    base = TransferContext(task_family="discovery", domain="education", run_id="scope")
    contexts = [
        resolve_transfer_context(context={"transfer_context": base}),
        resolve_transfer_context(context={"transfer_context": base.model_dump(mode="json")}),
        resolve_transfer_context(task_family="discovery", domain="education", run_id="scope"),
    ]
    assert {(c.task_family, c.domain, c.run_id) for c in contexts} == {
        ("discovery", "education", "scope")
    }
    changed = resolve_transfer_context(
        context={"transfer_context": base}, task_family="policy", domain="health"
    )
    assert (changed.task_family, changed.domain, changed.run_id) == ("policy", "health", "scope")


def test_invalid_base_does_not_leak_partial_scope_and_explicit_scope_remains_addressed():
    invalid = {"task_family": "discovery", "domain": "education", "run_id": "", "extra": 1}
    resolved = resolve_transfer_context(
        context={"transfer_context": invalid}, domain="known", run_id="caller"
    )
    assert (resolved.task_family, resolved.domain, resolved.run_id) == ("policy", "known", "caller")
    assert resolved.tenant_hash is None


def test_truly_unknown_domain_keeps_a_run_addressed_isolated_fallback():
    unknown = resolve_transfer_context(run_id="unknown-run")
    assert (unknown.task_family, unknown.domain, unknown.run_id) == (
        "policy",
        "isolated::unknown-run",
        "unknown-run",
    )
