"""Public artifacts signing module API."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from polisyos.common.logger import get_logger

from ..canon import content_hash
from ..canon.canon_json import to_canonical_bytes
from .ids import ArtifactID

logger = get_logger(__name__)

SIGNATURE_FORMAT_VERSION = "1"
SIGNATURE_ALGORITHM = "Ed25519"
SIGNATURE_STATEMENT_TYPE = "polisyos.cas.signature_statement"

DEFAULT_PRIVATE_KEY_ENV = "POLISYOS_SIGNING_KEY"
DEFAULT_PRIVATE_KEY_FILE_ENV = "POLISYOS_SIGNING_KEY_FILE"

DEFAULT_PRIVATE_KEY_PATH = Path("~/.polisyos/keys/polisyos-signing.pem")
DEFAULT_TRUST_DIR = Path(".polisyos/keys/trusted")
DEFAULT_REVOKED_DIR = Path(".polisyos/keys/revoked")
DEFAULT_IDENTITIES_PATH = Path(".polisyos/keys/identities.json")


class SigningError(RuntimeError):
    """Base signing subsystem error."""


class KeyLoadingError(SigningError):
    """Raised when signing key cannot be loaded."""


class SignatureVerificationStatus(str, Enum):
    """Signature verification status public type."""
    VALID = "valid"
    UNSIGNED = "unsigned"
    INVALID = "invalid"
    UNTRUSTED = "untrusted"
    REVOKED = "revoked"
    ERROR = "error"


class SignatureStatement(BaseModel):
    """Canonical statement that is actually signed."""

    model_config = ConfigDict(extra="forbid")

    type: str = SIGNATURE_STATEMENT_TYPE
    version: str = SIGNATURE_FORMAT_VERSION
    algorithm: str = SIGNATURE_ALGORITHM
    artifact_id: str
    blob_sha256: str = Field(..., min_length=64, max_length=64)
    manifest_sha256: str = Field(..., min_length=64, max_length=64)
    key_id: str


class DetachedSignature(BaseModel):
    """Detached signature sidecar model (<artifact>.sig)."""

    model_config = ConfigDict(extra="forbid")

    version: str = SIGNATURE_FORMAT_VERSION
    algorithm: str = SIGNATURE_ALGORITHM
    artifact_id: str
    key_id: str
    statement: SignatureStatement
    signature_hex: str = Field(..., min_length=128, max_length=128)
    signed_at: datetime
    signer_identity: str | None = None

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "DetachedSignature":
        if self.statement.artifact_id != self.artifact_id:
            raise ValueError("signature statement artifact_id mismatch")
        if self.statement.key_id != self.key_id:
            raise ValueError("signature statement key_id mismatch")
        return self


class SignatureVerificationResult(BaseModel):
    """Detailed verification result for one artifact."""

    model_config = ConfigDict(extra="forbid")

    status: SignatureVerificationStatus
    artifact_id: str
    key_id: str | None = None
    signer_identity: str | None = None
    expected_identity: str | None = None
    message: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def ok(self) -> bool:
        return self.status == SignatureVerificationStatus.VALID


class BulkVerificationReport(BaseModel):
    """Batch verification report for CAS bulk checks."""

    model_config = ConfigDict(extra="forbid")

    total: int
    valid: int
    unsigned: int
    invalid: int
    untrusted: int
    revoked: int
    errors: int
    details: list[SignatureVerificationResult] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def ok(self) -> bool:
        return self.invalid == 0 and self.revoked == 0 and self.errors == 0


class ArtifactSigningResult(BaseModel):
    """Result of signing one artifact in bulk mode."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    status: str
    key_id: str | None = None
    message: str | None = None


class BulkSigningReport(BaseModel):
    """Batch signing report for CAS artifacts."""

    model_config = ConfigDict(extra="forbid")

    total: int
    signed: int
    skipped: int
    errors: int
    details: list[ArtifactSigningResult] = Field(default_factory=list)
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SigningConfig(BaseModel):
    """Configuration for artifact signing integration in CAS."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    sign_on_put: bool = False
    sign_on_put_policy: str = "fail"

    private_key_env: str = DEFAULT_PRIVATE_KEY_ENV
    private_key_file_env: str = DEFAULT_PRIVATE_KEY_FILE_ENV
    private_key_file: Path = DEFAULT_PRIVATE_KEY_PATH

    trust_dir: Path = DEFAULT_TRUST_DIR
    revoked_dir: Path = DEFAULT_REVOKED_DIR
    identities_path: Path = DEFAULT_IDENTITIES_PATH

    default_identity: str | None = None
    strict_identity: bool = False
    verify_workers: int = 8
    sign_workers: int = 8

    @classmethod
    def from_env(cls) -> "SigningConfig":
        def _env_bool(name: str, default: bool) -> bool:
            raw = os.environ.get(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        def _env_int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None:
                return default
            try:
                value = int(raw)
                return max(1, value)
            except ValueError:
                return default

        return cls(
            enabled=_env_bool("POLISYOS_SIGNING_ENABLED", False),
            sign_on_put=_env_bool("POLISYOS_SIGN_ON_PUT", False),
            sign_on_put_policy=os.environ.get("POLISYOS_SIGN_ON_PUT_POLICY", "fail"),
            private_key_env=os.environ.get("POLISYOS_SIGNING_KEY_ENV", DEFAULT_PRIVATE_KEY_ENV),
            private_key_file_env=os.environ.get(
                "POLISYOS_SIGNING_KEY_FILE_ENV",
                DEFAULT_PRIVATE_KEY_FILE_ENV,
            ),
            private_key_file=Path(
                os.environ.get(
                    "POLISYOS_SIGNING_KEY_DEFAULT_PATH",
                    str(DEFAULT_PRIVATE_KEY_PATH),
                )
            ).expanduser(),
            trust_dir=Path(
                os.environ.get("POLISYOS_SIGN_TRUST_DIR", str(DEFAULT_TRUST_DIR))
            ),
            revoked_dir=Path(
                os.environ.get("POLISYOS_SIGN_REVOKED_DIR", str(DEFAULT_REVOKED_DIR))
            ),
            identities_path=Path(
                os.environ.get("POLISYOS_SIGN_IDENTITIES", str(DEFAULT_IDENTITIES_PATH))
            ),
            default_identity=os.environ.get("POLISYOS_SIGNING_IDENTITY"),
            strict_identity=_env_bool("POLISYOS_STRICT_IDENTITY", False),
            verify_workers=_env_int("POLISYOS_SIGN_VERIFY_WORKERS", 8),
            sign_workers=_env_int("POLISYOS_SIGN_WORKERS", 8),
        )


@dataclass(frozen=True)
class KeyPair:
    """Ed25519 key pair utilities."""

    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @staticmethod
    def generate() -> "KeyPair":
        private = Ed25519PrivateKey.generate()
        return KeyPair(private_key=private, public_key=private.public_key())

    @staticmethod
    def from_private_pem(data: bytes, password: bytes | None = None) -> "KeyPair":
        key = load_pem_private_key(data, password=password)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("Expected Ed25519 private key")
        return KeyPair(private_key=key, public_key=key.public_key())

    @property
    def key_id(self) -> str:
        return compute_key_id(self.public_key)

    def private_pem(self, password: bytes | None = None) -> bytes:
        encryption = NoEncryption() if password is None else BestAvailableEncryption(password)
        return self.private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )

    def public_pem(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )


def compute_key_id(public_key: Ed25519PublicKey) -> str:
    """Stable key id: sha256:<64hex> over raw public key bytes."""

    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return content_hash(raw, prefix=True)


def hash_bytes(data: bytes) -> str:
    """Hash bytes helper."""
    return content_hash(data)


def canonical_statement_bytes(statement: SignatureStatement) -> bytes:
    """Canonical statement bytes helper."""
    return to_canonical_bytes(statement.model_dump(mode="python", by_alias=True, exclude_none=True))


def safe_short_key_id(key_id: str | None) -> str:
    """Safe short key ID helper."""
    if key_id is None:
        return "<none>"
    if len(key_id) <= 18:
        return key_id
    return f"{key_id[:18]}..."


class ArtifactSigner(Protocol):
    """Protocol for artifact signing implementations."""

    def sign(
        self,
        artifact_id: ArtifactID,
        blob_data: bytes,
        manifest_data: bytes,
        *,
        signer_identity: str | None = None,
    ) -> DetachedSignature:
        ...


class ArtifactVerifier(Protocol):
    """Protocol for artifact verifier implementations."""

    def verify(
        self,
        artifact_id: ArtifactID,
        blob_data: bytes,
        manifest_data: bytes,
        signature: DetachedSignature,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        ...


class Ed25519Signer:
    """Ed25519 detached signature producer."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key
        self._public_key = private_key.public_key()
        self._key_id = compute_key_id(self._public_key)

    @property
    def key_id(self) -> str:
        return self._key_id

    @classmethod
    def from_pem(cls, pem_data: bytes, password: bytes | None = None) -> "Ed25519Signer":
        key = load_pem_private_key(pem_data, password=password)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("Expected Ed25519 private key in PEM")
        return cls(key)

    @classmethod
    def from_path(cls, path: Path, password: bytes | None = None) -> "Ed25519Signer":
        return cls.from_pem(path.read_bytes(), password=password)

    @classmethod
    def from_env_or_file(
        cls,
        *,
        private_key_env: str = DEFAULT_PRIVATE_KEY_ENV,
        private_key_file_env: str = DEFAULT_PRIVATE_KEY_FILE_ENV,
        default_private_key_file: Path = DEFAULT_PRIVATE_KEY_PATH,
        password: bytes | None = None,
    ) -> "Ed25519Signer":
        env_data = os.environ.get(private_key_env)
        if env_data:
            pem_data = _normalize_multiline_pem(env_data).encode("utf-8")
            return cls.from_pem(pem_data, password=password)

        env_file = os.environ.get(private_key_file_env)
        if env_file:
            return cls.from_path(Path(env_file).expanduser(), password=password)

        default_path = default_private_key_file.expanduser()
        if default_path.exists():
            return cls.from_path(default_path, password=password)

        raise KeyLoadingError(
            "Signing private key not found. Checked "
            f"${private_key_env}, ${private_key_file_env}, and {default_path}."
        )

    def build_statement(
        self,
        artifact_id: ArtifactID,
        blob_data: bytes,
        manifest_data: bytes,
    ) -> SignatureStatement:
        blob_sha = hash_bytes(blob_data)
        if blob_sha != artifact_id.hex:
            expected = artifact_id.hex
            raise SigningError(
                f"Artifact content hash mismatch for {artifact_id}: "
                f"expected {expected}, got {blob_sha}"
            )

        return SignatureStatement(
            artifact_id=str(artifact_id),
            blob_sha256=blob_sha,
            manifest_sha256=hash_bytes(manifest_data),
            key_id=self._key_id,
        )

    def sign(
        self,
        artifact_id: ArtifactID,
        blob_data: bytes,
        manifest_data: bytes,
        *,
        signer_identity: str | None = None,
    ) -> DetachedSignature:
        statement = self.build_statement(artifact_id, blob_data, manifest_data)
        payload = canonical_statement_bytes(statement)
        signature_bytes = self._private_key.sign(payload)
        return DetachedSignature(
            artifact_id=str(artifact_id),
            key_id=self._key_id,
            statement=statement,
            signature_hex=signature_bytes.hex(),
            signed_at=datetime.now(timezone.utc),
            signer_identity=signer_identity,
        )


class Ed25519Verifier:
    """Ed25519 signature verifier with trust + revocation + identity binding."""

    def __init__(self, *, strict_identity: bool = False) -> None:
        self._strict_identity = strict_identity
        self._trusted_keys: dict[str, Ed25519PublicKey] = {}
        self._revoked_key_ids: set[str] = set()
        self._identity_bindings: dict[str, str] = {}

    def add_trusted_key(
        self,
        public_key: Ed25519PublicKey,
        *,
        key_id: str | None = None,
        identity: str | None = None,
    ) -> str:
        kid = key_id or compute_key_id(public_key)
        self._trusted_keys[kid] = public_key
        if identity:
            self._identity_bindings[kid] = identity
        return kid

    def load_trusted_key_pem(self, pem_data: bytes, *, identity: str | None = None) -> str:
        key = load_pem_public_key(pem_data)
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("Expected Ed25519 public key in PEM")
        return self.add_trusted_key(key, identity=identity)

    def load_trusted_key_file(self, path: Path, *, identity: str | None = None) -> str:
        return self.load_trusted_key_pem(path.read_bytes(), identity=identity)

    def load_trust_dir(self, trust_dir: Path) -> list[str]:
        loaded: list[str] = []
        if not trust_dir.exists() or not trust_dir.is_dir():
            return loaded
        for path in sorted(trust_dir.glob("*.pub")):
            try:
                loaded.append(self.load_trusted_key_file(path))
            except Exception:
                continue
        return loaded

    def add_revoked_key_id(self, key_id: str) -> None:
        self._revoked_key_ids.add(key_id)

    def load_revoked_dir(self, revoked_dir: Path) -> list[str]:
        loaded: list[str] = []
        if not revoked_dir.exists() or not revoked_dir.is_dir():
            return loaded
        for path in sorted(revoked_dir.glob("*.pub")):
            try:
                key = load_pem_public_key(path.read_bytes())
                if not isinstance(key, Ed25519PublicKey):
                    continue
                kid = compute_key_id(key)
                self._revoked_key_ids.add(kid)
                loaded.append(kid)
            except Exception:
                continue
        return loaded

    def load_identity_bindings(self, identities_path: Path) -> dict[str, str]:
        if not identities_path.exists() or not identities_path.is_file():
            return {}

        raw = json.loads(identities_path.read_text("utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("identity bindings file must contain object mapping")

        out: dict[str, str] = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, str):
                out[key] = value
        self._identity_bindings.update(out)
        return out

    def expected_identity(self, key_id: str) -> str | None:
        return self._identity_bindings.get(key_id)

    @property
    def trusted_key_ids(self) -> list[str]:
        return sorted(self._trusted_keys.keys())

    @property
    def revoked_key_ids(self) -> list[str]:
        return sorted(self._revoked_key_ids)

    def verify(
        self,
        artifact_id: ArtifactID,
        blob_data: bytes,
        manifest_data: bytes,
        signature: DetachedSignature,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        strict = self._strict_identity if strict_identity is None else strict_identity

        if signature.version != SIGNATURE_FORMAT_VERSION:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message=f"Unsupported signature version: {signature.version}",
            )
        if signature.algorithm != SIGNATURE_ALGORITHM:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message=f"Unsupported signature algorithm: {signature.algorithm}",
            )

        statement = signature.statement
        if statement.type != SIGNATURE_STATEMENT_TYPE:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message=f"Unsupported signature statement type: {statement.type}",
            )

        if statement.artifact_id != str(artifact_id):
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message=(
                    "Artifact ID mismatch in signature statement: "
                    f"{statement.artifact_id} != {artifact_id}"
                ),
            )

        blob_sha = hash_bytes(blob_data)
        if blob_sha != statement.blob_sha256:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message="Blob SHA-256 mismatch against signature statement",
            )

        manifest_sha = hash_bytes(manifest_data)
        if manifest_sha != statement.manifest_sha256:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message="Manifest SHA-256 mismatch against signature statement",
            )

        key_id = signature.key_id
        expected_identity = self._identity_bindings.get(key_id)

        if key_id in self._revoked_key_ids:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.REVOKED,
                artifact_id=str(artifact_id),
                key_id=key_id,
                signer_identity=signature.signer_identity,
                expected_identity=expected_identity,
                message="Signing key has been revoked",
            )

        trusted_key = self._trusted_keys.get(key_id)
        if trusted_key is None:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.UNTRUSTED,
                artifact_id=str(artifact_id),
                key_id=key_id,
                signer_identity=signature.signer_identity,
                expected_identity=expected_identity,
                message="Signing key is not in trust store",
            )

        identity_mismatch = (
            expected_identity
            and signature.signer_identity
            and signature.signer_identity != expected_identity
        )
        if identity_mismatch:
            if strict:
                return SignatureVerificationResult(
                    status=SignatureVerificationStatus.INVALID,
                    artifact_id=str(artifact_id),
                    key_id=key_id,
                    signer_identity=signature.signer_identity,
                    expected_identity=expected_identity,
                    message=(
                        "Signer identity mismatch: "
                        f"expected '{expected_identity}', got '{signature.signer_identity}'"
                    ),
                )

        payload = canonical_statement_bytes(statement)
        try:
            signature_bytes = bytes.fromhex(signature.signature_hex)
            trusted_key.verify(signature_bytes, payload)
        except InvalidSignature:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.INVALID,
                artifact_id=str(artifact_id),
                key_id=key_id,
                signer_identity=signature.signer_identity,
                expected_identity=expected_identity,
                message="Ed25519 verification failed",
            )
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                key_id=key_id,
                signer_identity=signature.signer_identity,
                expected_identity=expected_identity,
                message=f"Verification error: {exc}",
            )

        message: str | None = None
        if identity_mismatch:
            message = (
                "Identity hint mismatch (non-strict mode): "
                f"expected '{expected_identity}', got '{signature.signer_identity}'"
            )

        return SignatureVerificationResult(
            status=SignatureVerificationStatus.VALID,
            artifact_id=str(artifact_id),
            key_id=key_id,
            signer_identity=signature.signer_identity,
            expected_identity=expected_identity,
            message=message,
        )


def load_signer_from_config(
    config: SigningConfig,
    *,
    password: bytes | None = None,
) -> Ed25519Signer:
    """Load signer from config."""
    return Ed25519Signer.from_env_or_file(
        private_key_env=config.private_key_env,
        private_key_file_env=config.private_key_file_env,
        default_private_key_file=config.private_key_file,
        password=password,
    )


def build_verifier_from_config(config: SigningConfig) -> Ed25519Verifier:
    """Build verifier from config."""
    verifier = Ed25519Verifier(strict_identity=config.strict_identity)
    verifier.load_trust_dir(config.trust_dir)
    verifier.load_revoked_dir(config.revoked_dir)
    try:
        verifier.load_identity_bindings(config.identities_path)
    except Exception as exc:
        logger.debug("Ignored exception: %s", exc)
    return verifier


def ensure_private_key_permissions(path: Path) -> tuple[bool, str | None]:
    """Return (ok, warning_message)."""

    if not path.exists():
        return False, f"Private key file does not exist: {path}"

    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        return False, f"Private key permissions should be 0600, got {oct(mode)}"

    return True, None


def _normalize_multiline_pem(raw: str) -> str:
    if "\\n" in raw and "\n" not in raw:
        return raw.replace("\\n", "\n")
    return raw


__all__ = [
    "ArtifactSigningResult",
    "ArtifactSigner",
    "ArtifactVerifier",
    "BulkSigningReport",
    "BulkVerificationReport",
    "DetachedSignature",
    "Ed25519Signer",
    "Ed25519Verifier",
    "KeyLoadingError",
    "KeyPair",
    "SIGNATURE_ALGORITHM",
    "SIGNATURE_FORMAT_VERSION",
    "SIGNATURE_STATEMENT_TYPE",
    "SigningConfig",
    "SigningError",
    "SignatureStatement",
    "SignatureVerificationResult",
    "SignatureVerificationStatus",
    "build_verifier_from_config",
    "canonical_statement_bytes",
    "compute_key_id",
    "ensure_private_key_permissions",
    "hash_bytes",
    "load_signer_from_config",
    "safe_short_key_id",
]
