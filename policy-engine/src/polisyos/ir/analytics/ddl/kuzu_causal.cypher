CREATE NODE TABLE IF NOT EXISTS CausalVar(
    name STRING,
    PRIMARY KEY(name)
);

CREATE REL TABLE IF NOT EXISTS CausalEdge(
    FROM CausalVar TO CausalVar,
    mark_src STRING,
    mark_dst STRING,
    lag INT64,
    combined_confidence DOUBLE,
    graph_type STRING,
    sources STRING,
    evidence_refs STRING,
    metadata_json STRING
);
