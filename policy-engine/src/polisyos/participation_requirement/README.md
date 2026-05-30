# Participation Requirement

- Last updated: 2026-05-23

`polisyos.participation_requirement` owns the W7.E participation provenance
requirement compiler for the universal Policy Design Case path.

The module turns claim-use intent into typed
`ParticipationProvenanceRequirementSpec` records and evaluates participation
records against those specs before any preference, legitimacy, prevalence, or
public projection surface can treat participation as support. The compiler is
authoritative only for the requirement it emits; evaluated records remain
bounded by `claim_use_allowed`, downgrade reasons, privacy constraints, and
projection limitations.

Threshold values are deliberately not hardcoded as structural truth. The spec
carries governed configuration owner/version fields so deployment-specific
sample-size, response-rate, weighting, coverage, and subgroup thresholds remain
methodology/governance-owned tuned parameters under ADR-0167.
