# Tutorials

English edition: 2026-10-14 (translation only; not a source-freshness or execution claim).

Related pages: [Contributor Start Here](../reference/contributor-start-here.md),
[How-to Guides](../how-to/index.md), and the [Reference Index](../reference/index.md).

Review basis: product source reviewed at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
`src/polisyos/` production implementation is unchanged at that pin. Examples and tests were not
executed for this documentation refresh. Historical receipts remain tied to their recorded dates.

Tutorials introduce the product through practical scenarios. To change an
existing surface, use the task-specific how-to guide and the nearest package
README. For decisions about boundaries and authority, start with the
architecture documents linked from Contributor Start Here.

## Learning path

| Step | Tutorial | Outcome |
| --- | --- | --- |
| Set up the environment and see a first run | [Getting Started](getting-started.md) | Contributor setup, import surface, and a short compile → execute smoke |
| Explore a first policy question | [First Policy Analysis](first-policy-analysis.md) | Candidate framing, optional raw-data demo, separate synthetic Foundry smoke, and draft-handoff boundaries |
| Extend Fabric with a data source | [Writing a Connector](writing-a-connector.md) | Connector class, built-in profile, mock-path test, and local-check commands |
| Add a Scientist governance pass | [Creating a Governance Pass](creating-governance-pass.md) | Pass registration and a unit-test example for a blocker case |

These tutorials introduce separate surfaces. They do not promise a working
end-to-end path from a policy question through observations and causal analysis
to an admissible or publishable recommendation.

Before adding a new developer process, check whether a [how-to
guide](../how-to/index.md) already covers it. To install only documentation
dependencies and check authored Markdown, use the documentation-only path in
[Contributor Start Here](../reference/contributor-start-here.md). Tutorial
receipts and local runs apply only to the environment and date in which they
were obtained.
