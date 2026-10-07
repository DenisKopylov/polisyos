from polisyos.scientist.agent.vector_memory import VectorMemoryStore
_admit = VectorMemoryStore._embedding
def removed_payload(embedding, dim):
    _admit(embedding, dim)
    return [float(value) for value in embedding]
VectorMemoryStore._embedding = staticmethod(removed_payload)
