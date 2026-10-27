def _load_reusable_vectors(*, index_dir: Path, legacy_embeddings_path: Path, legacy_index_path: Path, current_basis, embedding_model: str, embedding_device: str, embedding_dimension: int, basis_kind: str, projection_rule_version: str, encoder_identity: GenerationIdentity, incremental: bool) -> dict[str, np.ndarray]:
    """Load only vectors proven reusable by the selected generation metadata."""
    if not incremental:
        return {}
    reference = resolve_embedding_generation(index_dir, legacy_embeddings_path=legacy_embeddings_path, legacy_index_path=legacy_index_path)
    if reference is None or not reference.selected or reference.status != 'complete':
        if reference is not None and reference.generation_id == 'legacy-flat' and (reference.status == 'legacy') and (reference.selected is False):
            try:
                with np.load(str(reference.embeddings_path), allow_pickle=True) as payload:
                    legacy_ids = tuple((str(value) for value in payload['ids'].tolist()))
                    legacy_vectors = np.asarray(payload['vectors'], dtype=np.float32)
            except (KeyError, OSError, TypeError, ValueError):
                return {}
            if len(set(legacy_ids)) != len(legacy_ids) or legacy_vectors.ndim != 2 or legacy_vectors.shape != (len(legacy_ids), int(embedding_dimension)) or (not np.isfinite(legacy_vectors).all()):
                return {}
            vectors_by_id = {identifier: legacy_vectors[row_number] for row_number, identifier in enumerate(legacy_ids)}
            current_ids = {member.identifier for member in current_basis.members}
            return {identifier: vectors_by_id[identifier] for identifier in current_ids if identifier in vectors_by_id}
        return {}
    inventory = reference.inventory
    if inventory.get('embedding_model') != embedding_model or inventory.get('embedding_device') != embedding_device:
        return {}
    try:
        if int(inventory['embedding_dimension']) != int(embedding_dimension):
            return {}
    except (KeyError, TypeError, ValueError):
        return {}
    expected_rule_version = _generator_rule_version(projection_rule_version=projection_rule_version, embedding_model=embedding_model, embedding_device=embedding_device, embedding_dimension=embedding_dimension, encoder_identity=encoder_identity)
    persisted_basis = inventory.get('basis')
    if not isinstance(persisted_basis, dict):
        return {}
    if persisted_basis.get('basis_kind') != basis_kind or persisted_basis.get('generator_rule_version') != expected_rule_version:
        return {}
    old_identities: dict[str, str] = {}
    raw_members = persisted_basis.get('members')
    if not isinstance(raw_members, list):
        return {}
    for raw_member in raw_members:
        if not isinstance(raw_member, dict):
            return {}
        identifier = raw_member.get('identifier')
        content_identity = raw_member.get('content_identity')
        if not isinstance(identifier, str) or not isinstance(content_identity, str):
            return {}
        old_identities[identifier] = content_identity
    current_identities = {member.identifier: member.content_identity for member in current_basis.members}
    if not current_identities:
        return {}
    try:
        with np.load(str(reference.embeddings_path), allow_pickle=True) as payload:
            old_ids = tuple((str(value) for value in payload['ids'].tolist()))
            old_vectors = np.asarray(payload['vectors'], dtype=np.float32)
    except (KeyError, OSError, TypeError, ValueError):
        return {}
    if old_ids != reference.ids or old_vectors.ndim != 2 or old_vectors.shape != (len(old_ids), int(embedding_dimension)) or (not np.isfinite(old_vectors).all()):
        return {}
    old_vectors_by_id = {identifier: old_vectors[index] for index, identifier in enumerate(old_ids)}
    return {identifier: old_vectors_by_id[identifier] for identifier, content_identity in current_identities.items() if old_identities.get(identifier) == content_identity and identifier in old_vectors_by_id}
