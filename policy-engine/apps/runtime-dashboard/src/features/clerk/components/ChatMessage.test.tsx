import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import { ChatMessage } from "./ChatMessage";
import type { ChatMessage as ChatMessageType } from "../state/useChatStore";

function renderMessage(message: ChatMessageType) {
  return render(
    <MemoryRouter>
      <ChatMessage isStreaming={false} message={message} />
    </MemoryRouter>,
  );
}

function systemMessage(
  overrides: Partial<ChatMessageType> = {},
): ChatMessageType {
  return {
    content: "Producer response",
    id: "message-1",
    role: "system",
    timestamp: Date.now(),
    ...overrides,
  };
}

describe("ChatMessage run facts", () => {
  it("renders an unseen producer label verbatim with neutral clothing", () => {
    renderMessage(
      systemMessage({ runStatus: "awaiting_external_attestation" }),
    );

    const ownerLabel = screen.getByText("awaiting_external_attestation");
    expect(ownerLabel).toHaveClass("bg-white/65", "text-muted");
    expect(screen.queryByText("clerk.statusPlanning")).not.toBeInTheDocument();
  });

  it("does not unlock full-analysis action from completed-looking text without finished_at", () => {
    const view = renderMessage(
      systemMessage({ runId: "run-opaque", runStatus: "completed" }),
    );

    expect(
      screen.queryByRole("link", { name: "clerk.viewFullAnalysis" }),
    ).not.toBeInTheDocument();

    view.rerender(
      <MemoryRouter>
        <ChatMessage
          isStreaming={false}
          message={systemMessage({
            runFinishedAt: "2026-03-10T10:05:00Z",
            runId: "run-opaque",
            runStatus: "awaiting_external_attestation",
          })}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: "clerk.viewFullAnalysis" }),
    ).toHaveAttribute("href", "/runs/run-opaque");
  });

  it("does not unlock full-analysis action from whitespace-only finished_at", () => {
    renderMessage(
      systemMessage({
        runFinishedAt: "   ",
        runId: "run-opaque",
        runStatus: "completed_future",
      }),
    );

    expect(
      screen.queryByRole("link", { name: "clerk.viewFullAnalysis" }),
    ).not.toBeInTheDocument();
  });
});
