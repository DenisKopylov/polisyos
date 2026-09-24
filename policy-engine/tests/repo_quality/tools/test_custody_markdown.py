"""Compare compiler and strict custody consumers using only synthetic source rows."""

from hashlib import sha256
from pathlib import Path

import pytest
from _helpers.custody_markdown import VECTORS, rebound_register

from polisyos.scientist.evidence.claims.posture import (
    CUSTODY_APPOINTMENT_SOURCE_PATH,
    validate_posture_register,
)
from tools.quality.validation.check_trust_claim_posture import derive_custody_appointments


def write_synthetic_source(root: Path, payload: dict) -> tuple[Path, bytes]:
    path = root / CUSTODY_APPOINTMENT_SOURCE_PATH
    path.parent.mkdir(parents=True)
    raw = (
        "Synthetic source only\n"
        + "\n".join(source["source_content"] for source in payload["custody_appointment_sources"])
        + "\n"
    ).encode()
    path.write_bytes(raw)
    return path, raw


@pytest.mark.parametrize("subject", VECTORS["custody_subjects"])
def test_custody_compiler_and_strict_consumer_agree_without_rewriting_source(
    tmp_path: Path, subject: str
) -> None:
    payload = rebound_register(subject)
    path, before = write_synthetic_source(tmp_path, payload)
    appointments = derive_custody_appointments(tmp_path)
    admitted = validate_posture_register(payload)
    assert path.read_bytes() == before
    assert [item.source_content for item in appointments] == [
        source.source_content for source in admitted.custody_appointment_sources
    ]
    for index, item in enumerate(appointments, 2):
        assert item.line == index
        assert item.source_ref.endswith(
            "@sha256:" + sha256(item.source_content.encode()).hexdigest()
        )


@pytest.mark.parametrize("subject", VECTORS["malformed_subjects"])
def test_custody_compiler_rejects_malformed_fixed_grammar(tmp_path: Path, subject: str) -> None:
    write_synthetic_source(tmp_path, rebound_register(subject))
    with pytest.raises(ValueError):
        derive_custody_appointments(tmp_path)


@pytest.mark.parametrize(
    "mutation", ["id", "owner", "status", "command", "empty_owner", "duplicate_row"]
)
def test_custody_compiler_preserves_appointment_negatives(tmp_path: Path, mutation: str) -> None:
    payload = rebound_register("``left`|right``")
    source = payload["custody_appointment_sources"][0]
    if mutation == "id":
        source["source_content"] = source["source_content"].replace(
            source["debt_id"], "NOT-APPOINTED"
        )
    elif mutation == "owner":
        source["source_content"] = source["source_content"].replace(
            "`team-scientist`", "`team-fabricated`"
        )
    elif mutation == "empty_owner":
        source["source_content"] = source["source_content"].replace("`team-scientist`", "")
    elif mutation == "status":
        source["source_content"] = source["source_content"].replace(
            f"`{source['status']}`", "`unsupported`"
        )
    elif mutation == "command":
        source["source_content"] = source["source_content"].replace(
            "uv run pytest ", "python forged.py "
        )
    else:
        payload["custody_appointment_sources"].append(source.copy())
    write_synthetic_source(tmp_path, payload)
    with pytest.raises(ValueError):
        derive_custody_appointments(tmp_path)


@pytest.mark.parametrize("malformation", ["extra_cell", "duplicate_id", "contradictory_id"])
def test_custody_compiler_rejects_malformed_duplicate_of_accepted_row(
    tmp_path: Path, malformation: str
) -> None:
    payload = rebound_register("plain")
    malformed = payload["custody_appointment_sources"][0].copy()
    if malformation == "extra_cell":
        malformed["source_content"] += " unexpected |"
    else:
        other_id = malformed["debt_id"] if malformation == "duplicate_id" else "NOT-APPOINTED"
        malformed["source_content"] = malformed["source_content"].replace(
            f"`{malformed['debt_id']}`", f"`{malformed['debt_id']}` `{other_id}`"
        )
    payload["custody_appointment_sources"].append(malformed)
    write_synthetic_source(tmp_path, payload)
    with pytest.raises(ValueError):
        derive_custody_appointments(tmp_path)
