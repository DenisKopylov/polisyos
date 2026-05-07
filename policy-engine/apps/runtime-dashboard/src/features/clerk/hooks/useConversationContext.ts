import { useMemo } from "react";

import {
  useChatStore,
  type ChatMessage,
  type StructuredResponseData,
} from "../state/useChatStore";

/** Domain ontology concepts for governed NL context. */
const DOMAIN_CONCEPTS = [
  { pattern: /trinity\s*bundle/i, formal: "TrinityBundle", domain: "core" },
  {
    pattern: /governance\s*pass/i,
    formal: "GovernancePass",
    domain: "governance",
  },
  {
    pattern: /uncertainty\s*envelope/i,
    formal: "UncertaintyEnvelope",
    domain: "uncertainty",
  },
  {
    pattern: /causal\s*(graph|model|dag)/i,
    formal: "CausalDAG",
    domain: "causal",
  },
  {
    pattern: /treatment\s*effect/i,
    formal: "TreatmentEffect",
    domain: "causal",
  },
  {
    pattern: /confidence\s*interval/i,
    formal: "ConfidenceInterval",
    domain: "statistics",
  },
  { pattern: /decision\s*packet/i, formal: "DecisionPacket", domain: "output" },
  { pattern: /evidence\s*source/i, formal: "EvidenceSource", domain: "data" },
  { pattern: /policy\s*spec/i, formal: "PolicySpec", domain: "input" },
  { pattern: /run\s*config/i, formal: "RunConfiguration", domain: "execution" },
] as const;

export type ConversationContext = {
  /** Number of messages in current conversation. */
  messageCount: number;
  /** Latest system message's structured data. */
  latestStructured: StructuredResponseData | undefined;
  /** Active run ID if any. */
  activeRunId: string | null;
  /** Domain concepts mentioned in conversation. */
  mentionedConcepts: string[];
  /** Detected policy domain from conversation. */
  detectedDomain: string | undefined;
  /** Summary of the conversation topic. */
  topicSummary: string;
  /** Suggested follow-up actions based on context. */
  contextualSuggestions: string[];
};

function extractMentionedConcepts(messages: ChatMessage[]): string[] {
  const text = messages.map((m) => m.content).join(" ");
  const found = new Set<string>();
  for (const concept of DOMAIN_CONCEPTS) {
    if (concept.pattern.test(text)) {
      found.add(concept.formal);
    }
  }
  return [...found];
}

function detectDomain(messages: ChatMessage[]): string | undefined {
  const lastSystem = [...messages]
    .reverse()
    .find((m) => m.role === "system" && m.structured?.policyDomain);
  return lastSystem?.structured?.policyDomain;
}

function buildTopicSummary(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "";
  return firstUser.content.length > 100
    ? firstUser.content.slice(0, 100) + "..."
    : firstUser.content;
}

function generateContextualSuggestions(
  messages: ChatMessage[],
  concepts: string[],
): string[] {
  const suggestions: string[] = [];
  const lastSystem = [...messages].reverse().find((m) => m.role === "system");

  if (lastSystem?.structured?.suggestions) {
    return lastSystem.structured.suggestions;
  }

  // Generate based on conversation state
  if (lastSystem?.runStatus === "completed") {
    suggestions.push("What are the key uncertainties in this analysis?");
    suggestions.push("How robust are these findings to different assumptions?");
    if (!concepts.includes("GovernancePass")) {
      suggestions.push("What governance checks were applied?");
    }
  }

  if (concepts.includes("CausalDAG")) {
    suggestions.push("Can you explain the causal identification strategy?");
  }

  if (messages.length <= 2) {
    suggestions.push("What data sources will be used?");
    suggestions.push("Can you explain the methodology?");
  }

  return suggestions.slice(0, 4);
}

/**
 * Tracks conversation context for follow-ups and governed NL.
 * Provides contextual suggestions and domain concept grounding.
 */
export function useConversationContext(): ConversationContext {
  const { messages, currentRunId } = useChatStore();

  return useMemo(() => {
    const latestSystem = [...messages]
      .reverse()
      .find((m) => m.role === "system");
    const concepts = extractMentionedConcepts(messages);

    return {
      messageCount: messages.length,
      latestStructured: latestSystem?.structured,
      activeRunId: currentRunId,
      mentionedConcepts: concepts,
      detectedDomain: detectDomain(messages),
      topicSummary: buildTopicSummary(messages),
      contextualSuggestions: generateContextualSuggestions(messages, concepts),
    };
  }, [messages, currentRunId]);
}

export { DOMAIN_CONCEPTS };
