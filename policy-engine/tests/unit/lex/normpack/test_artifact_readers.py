from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.lex.normpack.artifact_readers import load_json_artifact


def test_lex_artifact_reader_loads_profiled_json_from_cas(tmp_path) -> None:
    """Read a canonical JSON artifact emitted by the current Core producer."""
    cas = FileSystemCAS(tmp_path / "cas")
    spec = CanonSpec()
    expected = {"source": "lex", "version": 1}
    reference = cas.put_json(
        expected,
        PutOptions(
            kind="test.lex_artifact",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    assert reference.manifest_profile_sha256 is not None

    payload = load_json_artifact(
        cas,
        str(reference.artifact_id),
        payload_label="test artifact",
    )

    assert payload == expected
