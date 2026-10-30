# Academic Data Forge domain

The academic domain owns literature ingestion, the staged graph and embedding
producer, and read-only Scholar knowledge consumers. `embedding_projection.py`
is the shared title/abstract projection and rule identity for the work embedding
producer and selected-source reader. See the [batch](batch/README.md) and
[knowledge](knowledge/README.md) package notes for their boundaries.
