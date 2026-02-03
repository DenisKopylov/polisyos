CREATE NODE TABLE IF NOT EXISTS WorldNode(
    id STRING,
    kind STRING,
    label STRING,
    artifact_id STRING,
    PRIMARY KEY(id)
);

CREATE REL TABLE IF NOT EXISTS WorldEdge(
    FROM WorldNode TO WorldNode,
    edge_id STRING,
    kind STRING,
    predicate_id STRING,
    tx_time STRING,
    valid_time STRING,
    confidence STRING,
    weight STRING,
    event_id STRING
);
