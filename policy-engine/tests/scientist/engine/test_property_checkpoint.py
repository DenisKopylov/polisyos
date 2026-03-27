"""Property-based tests for checkpoint fingerprinting."""
from __future__ import annotations

import copy

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from polisyos.scientist.engine.checkpoint import compute_workflow_fingerprint
from polisyos.scientist.engine.retry import RetryPolicy
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

pytestmark = pytest.mark.property


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_alias = st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True)
_node_id = st.builds(
    lambda seg1, seg2, major, minor, patch: f"{seg1}.{seg2}@{major}.{minor}.{patch}",
    st.from_regex(r"[a-z][a-z0-9_]{1,6}", fullmatch=True),
    st.from_regex(r"[a-z][a-z0-9_]{1,6}", fullmatch=True),
    st.integers(min_value=0, max_value=9),
    st.integers(min_value=0, max_value=9),
    st.integers(min_value=0, max_value=9),
)


@st.composite
def workflow_specs(draw):
    n_nodes = draw(st.integers(min_value=1, max_value=5))
    aliases = list({draw(_alias) for _ in range(n_nodes + 5)})[:n_nodes]
    nodes = []
    for i, alias in enumerate(aliases):
        deps = aliases[:i][:2]  # at most 2 deps from prior nodes
        nodes.append(NodeInvocation(
            alias=alias,
            node_id=draw(_node_id),
            depends_on=deps,
        ))
    return WorkflowSpec(
        workflow_id=draw(st.from_regex(r"[a-z][a-z0-9_]{2,15}", fullmatch=True)),
        nodes=nodes,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(spec=workflow_specs())
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_fingerprint_determinism(spec: WorkflowSpec):
    """fingerprint(spec) == fingerprint(deepcopy(spec))."""
    fp1 = compute_workflow_fingerprint(spec)
    fp2 = compute_workflow_fingerprint(copy.deepcopy(spec))
    assert fp1 == fp2
    assert len(fp1) == 64


@given(spec=workflow_specs())
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_fingerprint_ignores_retry_and_timeout(spec: WorkflowSpec):
    """Retry and timeout_s changes don't affect fingerprint."""
    fp_base = compute_workflow_fingerprint(spec)

    # Add retry and timeout to each node
    modified = spec.model_copy(deep=True)
    for node in modified.nodes:
        node.retry = RetryPolicy(max_retries=3, backoff_base_s=2.0)
        node.timeout_s = 120.0

    fp_modified = compute_workflow_fingerprint(modified)
    assert fp_base == fp_modified


def test_different_workflow_id_different_fingerprint():
    """Two specs with different workflow_ids produce different fingerprints."""
    node = NodeInvocation(alias="start", node_id="test.node@1.0.0")
    spec_a = WorkflowSpec(workflow_id="workflow_alpha", nodes=[node])
    spec_b = WorkflowSpec(workflow_id="workflow_beta", nodes=[node])
    assert compute_workflow_fingerprint(spec_a) != compute_workflow_fingerprint(spec_b)


def test_node_order_matters():
    """Reordering nodes changes the fingerprint."""
    n1 = NodeInvocation(alias="aaa", node_id="test.alpha@1.0.0")
    n2 = NodeInvocation(alias="bbb", node_id="test.beta@1.0.0")
    spec_ab = WorkflowSpec(workflow_id="test_order", nodes=[n1, n2])
    spec_ba = WorkflowSpec(workflow_id="test_order", nodes=[n2, n1])
    assert compute_workflow_fingerprint(spec_ab) != compute_workflow_fingerprint(spec_ba)
