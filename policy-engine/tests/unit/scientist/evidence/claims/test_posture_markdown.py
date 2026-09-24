"""Exercise Markdown syntax through strict, byte-bound posture admission."""

from copy import deepcopy

import pytest
from _helpers.custody_markdown import VECTORS, bind_source, rebind_payload, rebound_register
from pydantic import ValidationError

from polisyos.scientist.evidence.claims.posture import validate_posture_register


@pytest.mark.parametrize("subject", VECTORS["custody_subjects"])
def test_custody_source_pipes_preserve_strict_admission(subject: str) -> None:
    payload = rebound_register(subject)
    before = deepcopy(payload)
    admitted = validate_posture_register(payload)
    assert payload == before
    assert [source.source_content for source in admitted.custody_appointment_sources] == [
        source["source_content"] for source in payload["custody_appointment_sources"]
    ]


@pytest.mark.parametrize("subject", VECTORS["malformed_subjects"])
def test_custody_unprotected_delimiters_fail_fixed_grammar(subject: str) -> None:
    with pytest.raises(ValidationError):
        validate_posture_register(rebound_register(subject))


@pytest.mark.parametrize(
    "mutation",
    ["digest", "id", "owner", "status", "command", "empty_owner", "extra_cell", "duplicate_id"],
)
def test_custody_tokenization_cannot_authorize_invalid_appointment(mutation: str) -> None:
    payload = rebound_register("``left`|right``")
    source = payload["custody_appointment_sources"][0]
    row = source["source_content"]
    if mutation == "digest":
        source["source_content"] += " "
    else:
        if mutation == "id":
            row = row.replace(source["debt_id"], "NOT-APPOINTED")
        elif mutation == "duplicate_id":
            row = row.replace(
                f"`{source['debt_id']}`", f"`{source['debt_id']}` `{source['debt_id']}`"
            )
        elif mutation == "owner":
            row = row.replace("`team-scientist`", "`team-fabricated`")
        elif mutation == "empty_owner":
            row = row.replace("`team-scientist`", "")
        elif mutation == "status":
            row = row.replace(f"`{source['status']}`", "`unsupported`")
        elif mutation == "command":
            row = row.replace("uv run pytest ", "python forged.py ")
        elif mutation == "extra_cell":
            row += " forbidden |"
        source["source_content"] = row
        bind_source(payload, source)
    rebind_payload(payload)
    with pytest.raises(ValidationError):
        validate_posture_register(payload)
