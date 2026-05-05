import type { CapabilityManifestPayload } from "@/api/validators";

export const FALLBACK_CAPABILITY_MANIFEST: CapabilityManifestPayload = {
  meta: {
    request_id: "fallback-capability-manifest",
    generated_at: new Date("2026-03-08T00:00:00Z").toISOString(),
    source_kinds: ["core_run"],
  },
  runtime_api_version: "1.0.0",
  shell_flavor: "atlas",
  default_execution_profile: "dev",
  default_locale: "en",
  supported_execution_profiles: ["dev", "research", "governed", "production"],
  supported_locales: ["en", "uk"],
  state_store_backend: "sqlite",
  worker_backend: "embedded",
  workspaces: [
    "command_center",
    "scenario_composer",
    "runs_decisions",
    "evidence_fabric",
    "lex_knowledge",
    "platform_health",
  ],
  features: [
    {
      key: "workflow_runs",
      label: "Workflow runs",
      description:
        "Launch workflow-backed runs from explicit artifact bindings.",
      category: "runs",
      enabled: true,
      stage: "active",
    },
    {
      key: "natural_language_runs",
      label: "Natural-language runs",
      description:
        "Use the agent circuit to transform NL requests into executable policy runs.",
      category: "runs",
      enabled: true,
      stage: "active",
    },
    {
      key: "multimodel_nl",
      label: "Multi-model NL execution",
      description: "Evaluate multiple LLM variants for a single NL request.",
      category: "runs",
      enabled: true,
      stage: "active",
    },
    {
      key: "required_preflight",
      label: "Required preflight",
      description: "Run execution-plan preflight diagnostics before execution.",
      category: "governance",
      enabled: true,
      stage: "active",
    },
    {
      key: "evaluator_reports",
      label: "Evaluator reports",
      description: "Persist evaluator verdicts, scores, and replanning hints.",
      category: "governance",
      enabled: true,
      stage: "active",
    },
    {
      key: "reproducibility_manifests",
      label: "Reproducibility manifests",
      description:
        "Expose replay, hash, and determinism metadata for completed runs.",
      category: "governance",
      enabled: true,
      stage: "active",
    },
    {
      key: "transport_summary",
      label: "Transport summary",
      description:
        "Expose transportability summaries on governance and decision surfaces.",
      category: "governance",
      enabled: true,
      stage: "active",
    },
    {
      key: "promotion_lane",
      label: "Promotion lane",
      description:
        "Review and approve ExploreLane candidates into reusable bindings.",
      category: "evidence",
      enabled: true,
      stage: "active",
    },
    {
      key: "auto_materialization",
      label: "Auto materialization",
      description:
        "Materialize retrieval results into snapshots or bindings during NL execution.",
      category: "evidence",
      enabled: true,
      stage: "active",
    },
    {
      key: "binding_profiles",
      label: "Binding profiles",
      description:
        "List reusable binding-profile strategies for structured inputs.",
      category: "evidence",
      enabled: true,
      stage: "active",
    },
    {
      key: "source_profiles",
      label: "Source profiles",
      description:
        "List curated connector/source profiles for ingestion and retrieval.",
      category: "evidence",
      enabled: true,
      stage: "active",
    },
    {
      key: "lex_pipeline",
      label: "Lex knowledge pipeline",
      description:
        "Trigger, inspect, and search the legal knowledge graph pipeline.",
      category: "knowledge",
      enabled: true,
      stage: "active",
    },
    {
      key: "unified_dag",
      label: "Unified DAG",
      description:
        "Expose unified method DAG execution in NL and workflow paths.",
      category: "runtime",
      enabled: true,
      stage: "active",
    },
    {
      key: "security_admin_layer",
      label: "Security / admin layer",
      description: "Dedicated tenant/authz/audit admin surfaces.",
      category: "platform",
      enabled: false,
      stage: "deferred",
    },
  ],
  constraints: {
    max_parallel_models: 16,
    max_nl_iterations: 10,
    artifact_preview_max_bytes: 2_000_000,
    task_runner: "in_process_thread_pool",
    default_locale: "en",
    supported_locales: ["en", "uk"],
  },
};

export function isCapabilityEnabled(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
): boolean {
  return (
    manifest?.features?.some(
      (feature) => feature.key === key && feature.enabled,
    ) ?? false
  );
}

export function getCapability(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
) {
  return manifest?.features?.find((feature) => feature.key === key) ?? null;
}

export function readNumericConstraint(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
  fallback: number,
): number {
  const raw = manifest?.constraints?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : fallback;
}
