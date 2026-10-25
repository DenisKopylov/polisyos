from __future__ import annotations

from collections.abc import Iterator, Mapping


def hte_source_data_field_names() -> frozenset[str]:
    """Return the field set from the producer-owned HTE observational-data DTO."""
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    return frozenset(HTEObservationalData.model_fields)


def hte_source_array_field_names() -> frozenset[str]:
    """Return fields serialized from producer-owned NumPy source arrays."""
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    serializer = HTEObservationalData.__pydantic_decorators__.field_serializers.get(
        "_serialize_numpy_fields"
    )
    if serializer is None:
        raise ValueError("hte_source_array_serializer_missing")
    source_array_fields = frozenset(serializer.info.fields)
    if source_array_fields != frozenset(
        {"outcome", "treatment", "covariates", "confounders", "sample_ids"}
    ):
        raise ValueError("hte_source_array_serializer_roles_changed")
    return source_array_fields


def hte_private_array_field_names() -> frozenset[str]:
    """Return raw array field roles from the source DTO and persisted HTE result DTO."""
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
    from polisyos.ir.analytics.hte import HTEResult

    source_array_roles = frozenset({"covariates", "sample_ids"}).intersection(
        HTEObservationalData.model_fields
    )
    result_array_roles = frozenset({"cate_values"}).intersection(HTEResult.model_fields)
    private_array_roles = source_array_roles | result_array_roles
    if private_array_roles != frozenset({"covariates", "sample_ids", "cate_values"}):
        raise ValueError("hte_private_array_roles_changed")
    return private_array_roles


def _walk_wire_nodes(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk_wire_nodes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_wire_nodes(child)


def _walk_wire_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str):
                yield key
            yield from _walk_wire_strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_wire_strings(child)


def hte_source_privacy_violations(
    response_wire: object,
    *,
    source_payload: Mapping[str, object],
    source_only_sample_id: str,
) -> tuple[str, ...]:
    """Find source arrays or a source-only identifier anywhere in the full public wire.

    Contract identifiers, contract FQNs, typed artifact-reference metadata, generic
    metadata, and descriptor-name lists remain valid. Structural private-array names come
    from the source and result DTOs; exact copies of source arrays selected by the producer's
    NumPy JSON serializer and the unique sample-ID canary are checked recursively across
    the complete response, including siblings of the selected projection.
    """
    if not source_only_sample_id:
        raise ValueError("source_only_sample_id_required")

    dto_field_names = hte_source_data_field_names()
    private_array_field_names = hte_private_array_field_names()
    violations: set[str] = set()
    if set(source_payload) != dto_field_names:
        violations.add("source_payload_does_not_match_producer_dto")

    if any(source_only_sample_id in text for text in _walk_wire_strings(response_wire)):
        violations.add("source_only_sample_id_present")

    wire_nodes = tuple(_walk_wire_nodes(response_wire))
    for node in wire_nodes:
        if not isinstance(node, Mapping):
            continue
        if "contract_payload" in node:
            violations.add("raw_contract_payload_key_present")
        leaked_private_fields = private_array_field_names.intersection(
            key for key in node if isinstance(key, str)
        )
        violations.update(
            f"private_array_field_present:{field_name}" for field_name in leaked_private_fields
        )

    for field_name in hte_source_array_field_names():
        source_value = source_payload.get(field_name)
        if not isinstance(source_value, list) or not source_value:
            continue
        if any(isinstance(node, list) and node == source_value for node in wire_nodes):
            violations.add(f"source_array_value_present:{field_name}")

    return tuple(sorted(violations))
