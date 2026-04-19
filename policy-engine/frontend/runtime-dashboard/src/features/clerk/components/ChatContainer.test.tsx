import { render, screen } from "@testing-library/react";

import { buildFeatureFlags } from "@/test/featureFlags";

const {
  useChatStoreMock,
  useClerkNlRunMock,
  useConversationContextMock,
  useFeatureFlagsMock,
} = vi.hoisted(() => ({
  useChatStoreMock: vi.fn(),
  useClerkNlRunMock: vi.fn(),
  useConversationContextMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: (...args: unknown[]) => useFeatureFlagsMock(...args),
}));

vi.mock("@/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("../state/useChatStore", () => ({
  useChatStore: (...args: unknown[]) => useChatStoreMock(...args),
}));

vi.mock("../hooks/useClerkNlRun", () => ({
  useClerkNlRun: (...args: unknown[]) => useClerkNlRunMock(...args),
}));

vi.mock("../hooks/useConversationContext", () => ({
  useConversationContext: (...args: unknown[]) =>
    useConversationContextMock(...args),
}));

vi.mock("./ChatInput", () => ({
  ChatInput: ({ disabled }: { disabled?: boolean }) => (
    <div data-testid="chat-input">{String(disabled)}</div>
  ),
}));

vi.mock("./ChatMessage", () => ({
  ChatMessage: ({ message }: { message: { id: string } }) => (
    <div data-testid={`chat-message-${message.id}`}>{message.id}</div>
  ),
}));

vi.mock("./ClerkFollowUpBar", () => ({
  ClerkFollowUpBar: () => <div data-testid="clerk-follow-up-bar" />,
}));

vi.mock("./ExportConversation", () => ({
  ExportConversation: () => <div data-testid="export-conversation" />,
}));

vi.mock("./ConversationHistorySearch", () => ({
  ConversationHistorySearch: () => <div data-testid="conversation-history" />,
}));

import { ChatContainer } from "./ChatContainer";

describe("ChatContainer", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    useFeatureFlagsMock.mockReturnValue({
      flags: buildFeatureFlags({ enableAtlasV2: true }),
    });
    useChatStoreMock.mockReturnValue({
      isStreaming: false,
      messages: [],
    });
    useClerkNlRunMock.mockReturnValue({
      isLoading: false,
      submit: vi.fn(),
    });
    useConversationContextMock.mockReturnValue({
      contextualSuggestions: ["Follow up on transport readiness"],
    });
  });

  it("renders the Atlas shell-lite brand treatment when Atlas v2 is enabled", () => {
    render(<ChatContainer />);

    expect(screen.getByTestId("atlas-logo-mark-32")).toBeInTheDocument();
    expect(screen.getByTestId("atlas-logo-mark-48")).toBeInTheDocument();
    expect(screen.getByText("shell.header.shellLite")).toBeInTheDocument();
    expect(screen.getByText("clerk.newAnalysis")).toBeInTheDocument();
    expect(screen.getByText("clerk.welcomeTitle")).toBeInTheDocument();
  });
});
