import type { Meta, StoryObj } from "@storybook/react-vite";

import { AuthoredText } from "./AuthoredText";
import { AuthorshipProvider, AuthorshipTimeline } from "./AuthorshipProvider";

const meta = {
  title: "Shared UI/AuthoredText",
  component: AuthoredText,
  tags: ["autodocs"],
  args: {
    author: "drafter",
    children:
      "Drafter synthesized the current policy narrative for operator review.",
  },
  decorators: [
    (Story) => (
      <AuthorshipProvider highlightMode="subtle">
        <div className="max-w-3xl space-y-4">
          <Story />
        </div>
      </AuthorshipProvider>
    ),
  ],
} satisfies Meta<typeof AuthoredText>;

export default meta;

type Story = StoryObj<typeof meta>;

const CITATION_EXAMPLES = [
  "Section 12 requires the baseline threshold to be published.",
  "Article 4 prohibits retroactive enforcement without notice.",
  "The evidence bundle confirms the denominator changed in 2025.",
  "The statutory ceiling is indexed to the annual reference wage.",
  "The consultation note requires a public impact memorandum.",
];

const HUMAN_EXAMPLES = [
  "Operator validated the implementation window after legal review.",
  "The deployment memo is scoped to the Kyiv pilot first.",
  "We should keep the phased rollout until the audit closes.",
  "A manual override is acceptable only for the emergency lane.",
  "Escalation remains necessary if the transport guard trips.",
];

const DRAFTER_EXAMPLES = [
  "Drafter summarized the packet into a short decision-ready narrative.",
  "Drafter connected the evidence bundle to the current recommendation.",
  "Drafter collapsed redundant caveats into one working paragraph.",
  "Drafter highlighted the likely distributional winners and losers.",
  "Drafter proposed a narrower scope for the first approval window.",
];

const FORMALIZER_EXAMPLES = [
  "Formalizer aligned the prose with the ratification template.",
  "Formalizer normalized the clause ordering for legal review.",
  "Formalizer converted the draft into one normative statement.",
  "Formalizer reduced ambiguity in the implementation conditions.",
  "Formalizer reconciled the packet wording with the audit record.",
];

const CRITIC_EXAMPLES = [
  "Critic flagged the unresolved uncertainty envelope around costs.",
  "Critic found a mismatch between the simulation and the statute.",
  "Critic marked the review as blocked pending additional evidence.",
  "Critic highlighted the vulnerable cohort with the largest downside.",
  "Critic surfaced a conflict between transport and governance posture.",
];

function RegisterGallery({
  author,
  examples,
  highlightMode = "subtle",
}: {
  author: "citation" | "human" | "drafter" | "formalizer" | "critic";
  examples: string[];
  highlightMode?: "off" | "subtle" | "prominent";
}) {
  return (
    <AuthorshipProvider highlightMode={highlightMode}>
      <div className="space-y-4">
        {examples.map((example, index) => (
          <AuthoredText
            key={`${author}-${index}`}
            author={author}
            sourceHref={
              author === "citation"
                ? `/evidence?focus=artifact&artifactId=eb_${index + 1}&runId=run-42`
                : undefined
            }
            sourceRef={
              author === "citation"
                ? `Evidence bundle EB-${index + 1}`
                : undefined
            }
            timestamp={`2026-04-22T1${index}:00:00Z`}
          >
            {example}
          </AuthoredText>
        ))}
      </div>
    </AuthorshipProvider>
  );
}

export const CitationRegister: Story = {
  render: () => (
    <RegisterGallery author="citation" examples={CITATION_EXAMPLES} />
  ),
};

export const HumanRegister: Story = {
  render: () => <RegisterGallery author="human" examples={HUMAN_EXAMPLES} />,
};

export const DrafterRegister: Story = {
  render: () => (
    <RegisterGallery author="drafter" examples={DRAFTER_EXAMPLES} />
  ),
};

export const FormalizerRegister: Story = {
  render: () => (
    <RegisterGallery author="formalizer" examples={FORMALIZER_EXAMPLES} />
  ),
};

export const CriticRegister: Story = {
  render: () => <RegisterGallery author="critic" examples={CRITIC_EXAMPLES} />,
};

export const ProminentAuditRail: Story = {
  render: () => (
    <AuthorshipProvider highlightMode="prominent">
      <div className="gap-4 xl:grid xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          <AuthoredText author="drafter" timestamp="2026-04-22T10:30:00Z">
            Drafter synthesized the current decision packet summary.
          </AuthoredText>
          <AuthoredText author="formalizer" timestamp="2026-04-22T10:32:00Z">
            Formalizer aligned the approval condition with the legal template.
          </AuthoredText>
          <AuthoredText
            author="citation"
            sourceHref="/evidence?focus=artifact&artifactId=eb_17&runId=run-42"
            sourceRef="Evidence bundle EB-17"
            timestamp="2026-04-22T10:34:00Z"
          >
            Section 12 requires the baseline threshold to be published.
          </AuthoredText>
          <AuthoredText author="critic" timestamp="2026-04-22T10:36:00Z">
            Critic flagged the remaining uncertainty envelope for escalation.
          </AuthoredText>
        </div>
        <AuthorshipTimeline />
      </div>
    </AuthorshipProvider>
  ),
};
