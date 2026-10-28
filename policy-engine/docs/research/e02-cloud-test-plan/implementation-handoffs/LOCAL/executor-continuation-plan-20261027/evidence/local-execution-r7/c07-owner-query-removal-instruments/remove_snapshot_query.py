"""Root-only removal control: restore full-index reads without disabling checks."""


def pytest_configure(config):
    from polisyos.core.artifacts import ownership

    def original_full_index_path(self, artifact_id, *, blob_readers):
        payload = self._load_payload()
        mapping = (
            ownership._blob_readers_mapping(payload)
            if blob_readers
            else ownership._artifacts_mapping(payload)
        )
        return [dict(row) for row in mapping.get(str(artifact_id), [])]

    ownership.ArtifactOwnershipIndex._claim_rows_for_query = original_full_index_path
