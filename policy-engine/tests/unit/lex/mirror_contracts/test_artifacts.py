from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import to_canonical_bytes
from polisyos.lex.artifacts import load_json_artifact


def test_lex_artifact_reader_loads_canonical_json_from_cas(tmp_path) -> None:
    """Lex readers preserve artifact validation without importing Data Forge readers."""
    cas = FileSystemCAS(tmp_path / "cas")
    reference = cas.put_bytes(
        to_canonical_bytes({"source": "lex", "version": 1}),
        PutOptions(kind="test.lex_artifact", media_type="application/json"),
    )

    payload = load_json_artifact(cas, str(reference.artifact_id), payload_label="test artifact")

    assert payload == {"source": "lex", "version": 1}
