from polisyos.scientist.agent.vector_memory import VectorMemoryStore
VectorMemoryStore._admit_native_vectors = staticmethod(lambda index, dim, count: None)
