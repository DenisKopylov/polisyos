from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from polisyos.data_forge.domains.legal.batch.embedder import build_embeddings_and_index
from polisyos.data_forge.kernel.embeddings import derive_encoder_identity, resolve_embedding_generation
from polisyos.lex.knowledge.store import LegalKnowledgeStore

ROOT = Path(sys.argv[1]).resolve()
WHEEL = Path(sys.argv[2]).resolve()
SOURCE = Path(sys.argv[3]).resolve()
ROOT.mkdir(parents=True, exist_ok=True)

modules = {
    "legal.batch.embedder": sys.modules["polisyos.data_forge.domains.legal.batch.embedder"],
    "kernel.embeddings": sys.modules["polisyos.data_forge.kernel.embeddings"],
    "lex.knowledge.store": sys.modules["polisyos.lex.knowledge.store"],
}
site_packages = Path(__import__("sysconfig").get_paths()["purelib"]).resolve()
package_root = site_packages / "polisyos"
module_proofs = {}
with zipfile.ZipFile(WHEEL) as archive:
    for label, module in modules.items():
        origin = Path(module.__file__).resolve()
        if not origin.is_relative_to(package_root):
            raise AssertionError(f"{label} did not import from site-packages: {origin}")
        relative = origin.relative_to(package_root).as_posix()
        wheel_bytes = archive.read("polisyos/" + relative)
        source_bytes = (SOURCE / "polisyos" / relative).read_bytes()
        installed_bytes = origin.read_bytes()
        identical = installed_bytes == wheel_bytes == source_bytes
        module_proofs[label] = {
            "origin": str(origin),
            "member": "polisyos/" + relative,
            "installed_sha256": hashlib.sha256(installed_bytes).hexdigest(),
            "wheel_sha256": hashlib.sha256(wheel_bytes).hexdigest(),
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "installed_wheel_source_identical": identical,
        }
        if not identical:
            raise AssertionError(f"installed module bytes do not match wheel/source: {label}")


class FixtureTokenizer:
    model_max_length = 128
    padding_side = "right"
    truncation_side = "right"
    init_kwargs = {"name_or_path": "fixture-no-weights"}

    def get_vocab(self) -> dict[str, int]:
        return {"<unk>": 0, "legal": 1, "fixture": 2}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {"unk_token": "<unk>"}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


class RecordingEncoder:
    def __init__(self, model_name: str = "legacy-recording-fixture", device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self.config = {"model_name": model_name, "fixture_dimension": 4}
        self.tokenizer = FixtureTokenizer()
        self.encoded_texts: list[str] = []

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"fixture.parameters": np.asarray([4.0, 1.0], dtype=np.float32)}

    def modules(self) -> list[RecordingEncoder]:
        return [self]

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar
        self.encoded_texts.extend(texts)
        rows = []
        for text in texts:
            base = float(sum(str(text).encode("utf-8")) % 31 + 1)
            vector = np.asarray([base, base + 1.0, base + 2.0, base + 3.0], dtype=np.float32)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)


def create_legal_db(path: Path) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE lex_entities (entity_id VARCHAR, name_en VARCHAR, name_uk VARCHAR, "
            "entity_type VARCHAR, aliases_en VARCHAR, aliases_uk VARCHAR)"
        )
        con.execute(
            "CREATE TABLE lex_facts (fact_id VARCHAR, subject_en VARCHAR, subject_uk VARCHAR, "
            "predicate VARCHAR, object_en VARCHAR, object_uk VARCHAR, fact_text VARCHAR, "
            "norm_type VARCHAR, action_canon VARCHAR, norm_type_canon VARCHAR, "
            "condition_text_uk VARCHAR, exception_text_uk VARCHAR, procedure_text_uk VARCHAR, "
            "thresholds_json VARCHAR, source_quote_uk VARCHAR)"
        )
        con.execute("CREATE TABLE lex_provisions (provision_id VARCHAR, provision_text VARCHAR)")
        con.execute(
            "INSERT INTO lex_entities VALUES (?, ?, ?, ?, ?, ?)",
            ["entity-1", "Fixture legal entity", "Fixture legal entity", "concept", "", ""],
        )
        con.execute("CHECKPOINT")


def expect_unsupported_without_writes(db_path: Path, out_path: Path, backend: object) -> str:
    try:
        build_embeddings_and_index(db_path, out_path, backend=backend, chunk_size=1)
    except ValueError as exc:
        message = str(exc)
        if "unsupported backend" not in message:
            raise AssertionError(f"unexpected typed refusal: {message}") from exc
        if db_path.exists() or out_path.exists():
            raise AssertionError("unsupported backend created DB or output before refusing")
        return message
    raise AssertionError("unsupported backend was accepted")


db_path = ROOT / "legal.duckdb"
out_path = ROOT / "index"
create_legal_db(db_path)
encoder = RecordingEncoder()
stats = build_embeddings_and_index(db_path, out_path, backend=encoder, chunk_size=1)
if stats.entities_embedded != 1 or not encoder.encoded_texts:
    raise AssertionError("legacy wrapper did not invoke its supplied encoder and producer")

generation_dir = out_path / ".legal_embedding_generations" / "lex_entity_embeddings"
reference = resolve_embedding_generation(
    generation_dir,
    legacy_embeddings_path=out_path / "lex_entity_embeddings.npz",
    legacy_index_path=out_path / "lex_entity_index.hnsw",
)
if reference is None or reference.status != "complete":
    raise AssertionError("legacy wrapper did not publish a complete selected entity generation")
identity = derive_encoder_identity(encoder)
rule_version = str(reference.inventory["basis"]["generator_rule_version"])
if identity.content_identity not in rule_version:
    raise AssertionError("selected generation does not bind the supplied encoder identity")
with np.load(str(reference.embeddings_path), allow_pickle=True) as payload:
    query = np.asarray(payload["vectors"][0], dtype=np.float32)
reader = LegalKnowledgeStore(db_path, out_path)
try:
    results = reader.search_entities_by_vector(query, top_k=1, min_similarity=0.0)
finally:
    reader.close()
if [result.entity_id for result in results] != ["entity-1"]:
    raise AssertionError("installed LegalKnowledgeStore did not consume the selected entity")

invalid_root = ROOT / "negative"
wrong_backend_message = expect_unsupported_without_writes(
    invalid_root / "wrong.duckdb", invalid_root / "wrong-index", object()
)
device_message = expect_unsupported_without_writes(
    invalid_root / "device.duckdb",
    invalid_root / "device-index",
    RecordingEncoder(device=None),
)

print(
    json.dumps(
        {
            "runtime": {
                "cwd": os.getcwd(),
                "python": sys.executable,
                "version": sys.version.split()[0],
                "isolated_mode": bool(sys.flags.isolated),
                "safe_path": bool(sys.flags.safe_path),
                "PYTHONPATH": os.environ.get("PYTHONPATH"),
                "site_packages": str(site_packages),
                "sys_path": list(sys.path),
            },
            "installed_module_bytes": module_proofs,
            "producer": "installed legal.batch.embedder.build_embeddings_and_index",
            "encoder_calls": len(encoder.encoded_texts),
            "selected_generation_status": reference.status,
            "encoder_identity_bound": identity.content_identity in rule_version,
            "reader_entity_ids": [result.entity_id for result in results],
            "wrong_backend_refusal": wrong_backend_message,
            "undeclared_device_refusal": device_message,
            "negative_paths_absent": not invalid_root.exists(),
            "model_weights_used": False,
            "native_hnsw_profile_required": True,
        },
        sort_keys=True,
    )
)
