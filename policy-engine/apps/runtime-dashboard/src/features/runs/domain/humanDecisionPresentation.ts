import type {
  HumanDecisionGate,
  HumanDecisionMutationRequest,
} from "@/features/runs/api/useHumanDecisions";

export type HumanDecisionFact = Readonly<{
  path: string;
  value: string;
}>;

function collectFacts(
  value: unknown,
  path: string,
  facts: HumanDecisionFact[],
) {
  if (Array.isArray(value)) {
    value.forEach((item, index) =>
      collectFacts(item, `${path}/${index}`, facts),
    );
    if (value.length === 0) facts.push({ path, value: "[]" });
    return;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value);
    entries.forEach(([key, nested]) =>
      collectFacts(nested, `${path}/${key}`, facts),
    );
    if (entries.length === 0) facts.push({ path, value: "{}" });
    return;
  }
  facts.push({
    path: path || "/",
    value: value === null ? "null" : String(value),
  });
}

/** Return a complete, ordered projection of the server packet for DOM parity. */
export function buildHumanDecisionFacts(gate: HumanDecisionGate) {
  const facts: HumanDecisionFact[] = [];
  collectFacts(gate, "", facts);
  return Object.freeze(facts);
}

/** Admit an appeal link only when its route, case, and source are mutually bound. */
export function resolveHumanDecisionAppealHref(
  gate: HumanDecisionGate,
): string | null {
  const contestability = gate.contestability;
  const request = gate.decision_request;
  if (
    !contestability ||
    !request ||
    !gate.source_ref ||
    contestability.case_id !== request.case_id ||
    contestability.source_ref !== gate.source_ref
  ) {
    return null;
  }
  try {
    const origin =
      typeof window === "undefined"
        ? "http://localhost"
        : window.location.origin;
    const href = new URL(contestability.href, origin);
    if (
      href.pathname !== `/runs/${encodeURIComponent(gate.run_id)}/case` ||
      href.searchParams.get("appeal_case_id") !== contestability.case_id ||
      href.searchParams.get("source_kind") !== gate.source_kind ||
      href.searchParams.get("source_ref") !== contestability.source_ref
    ) {
      return null;
    }
    return `${href.pathname}${href.search}${href.hash}`;
  } catch {
    return null;
  }
}

export type HumanDecisionFormInput = Readonly<{
  accountabilityStatement: string;
  action: HumanDecisionMutationRequest["action"];
  blockingReason: string;
  decisionMode: HumanDecisionMutationRequest["decision_mode"];
  dissentStatement: string;
  overrideReason: string;
}>;

/** Copy only the concrete server submission selector into a caller-authored mutation. */
export function buildHumanDecisionMutation(
  gate: HumanDecisionGate,
  input: HumanDecisionFormInput,
): HumanDecisionMutationRequest {
  const submission = gate.submission;
  if (gate.status !== "available" || !submission) {
    throw new TypeError("human-decision gate has no live submission surface");
  }
  const offered = submission.allowed_decisions.find(
    (candidate) => candidate.action === input.action,
  );
  if (!offered || !offered.decision_modes.includes(input.decisionMode)) {
    throw new TypeError(
      "human-decision action or mode was not offered by the server",
    );
  }
  const accountabilityStatement = input.accountabilityStatement.trim();
  const dissentStatement = input.dissentStatement.trim();
  if (!accountabilityStatement || !dissentStatement) {
    throw new TypeError("DS9-ACCOUNTABILITY-AND-DISSENT-REQUIRED");
  }
  const selector = submission.selector;
  const common = {
    accountability_statement: accountabilityStatement,
    action: input.action,
    basis_digest: selector.basis_digest,
    basis_ref: selector.basis_ref,
    blocking_reason:
      input.decisionMode === "blocking"
        ? input.blockingReason.trim() || null
        : null,
    decision_mode: input.decisionMode,
    decision_request_digest: selector.decision_request_digest,
    decision_request_ref: selector.decision_request_ref,
    dissent_statement: dissentStatement,
    override_reason:
      input.decisionMode === "override"
        ? input.overrideReason.trim() || null
        : null,
    presentation_contract_ref: selector.presentation_contract_ref,
    principal_binding_ref: selector.principal_binding_ref,
    reviewer_separation_ref: selector.reviewer_separation_ref,
    source_kind: selector.source_kind,
    source_ref: selector.source_ref,
  } satisfies HumanDecisionMutationRequest;
  if (input.decisionMode === "override" && !common.override_reason) {
    throw new TypeError("DS9-OVERRIDE-REASON-REQUIRED");
  }
  if (input.decisionMode === "blocking" && !common.blocking_reason) {
    throw new TypeError("DS9-BLOCKING-REASON-REQUIRED");
  }
  return selector.source_kind === "agent_action_authority"
    ? { ...common, action_kind: selector.action_kind }
    : common;
}
