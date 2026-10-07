"""In-memory negative: preserve exact CAS resolve/native markers, discard intake distinctions."""
from polisyos.core import canon
from polisyos.scientist.methods.search.strategies.transfer import TransferLearningManager

def pytest_configure(config):
    def collapsed(self, ref):
        payload = canon.from_canonical_bytes(self._resolved(ref))
        payload["schema_version"] = "2.0"
        payload["evaluations"] = []
        return payload
    TransferLearningManager._history = collapsed
