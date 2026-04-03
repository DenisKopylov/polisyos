"""Dataset catalog and batch ETL package for external statistical source discovery.

The package groups batch harvest/normalization/QC stages and the read-side catalog graph used to
search DCAT-like dataset metadata. Helper functions under ``datasets.batch`` are primarily ETL and
benchmark-preparation utilities, while ``datasets.knowledge`` exposes the user-facing catalog API.
"""
