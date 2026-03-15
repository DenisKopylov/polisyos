import type { ReactNode } from "react";

vi.mock("@/shared/ui/VirtualList", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/VirtualList")>(
    "@/shared/ui/VirtualList",
  );

  return {
    ...actual,
    VirtualList: ({
      items,
      renderItem,
    }: {
      items: unknown[];
      renderItem: (item: unknown, index: number) => ReactNode;
    }) => (
      <div>
        {items.map((item, index) => (
          <div key={index}>{renderItem(item, index)}</div>
        ))}
      </div>
    ),
  };
});

import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import { DecisionCard } from "@/shared/ui/compounds/DecisionCard";
import { EvidenceChain } from "@/shared/ui/compounds/EvidenceChain";
import { StatusTimeline } from "@/shared/ui/compounds/StatusTimeline";

describe("compound widgets", () => {
  it("renders DecisionCard with optional sections", () => {
    renderWithProviders(
      <DecisionCard
        title="Decision"
        subtitle="Policy recommendation"
        verdict="Approved"
        verdictKind="ok"
        confidence="0.91"
        confidenceKind="info"
        summary="Summary block"
        diagnostics={[
          { kind: "warn", label: "Needs monitoring" },
          { label: "Fallback ready" },
        ]}
        meta={[
          { label: "Owner", value: "Atlas" },
          { label: "Region", value: "UA" },
        ]}
      >
        <div>Child content</div>
      </DecisionCard>,
    );

    expect(screen.getByText("Decision")).toBeInTheDocument();
    expect(screen.getByText("Policy recommendation")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("0.91")).toBeInTheDocument();
    expect(screen.getByText("Summary block")).toBeInTheDocument();
    expect(screen.getByText("Needs monitoring")).toBeInTheDocument();
    expect(screen.getByText("Fallback ready")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  it("renders EvidenceChain items and the empty state", () => {
    const { rerender } = renderWithProviders(
      <EvidenceChain
        title="Evidence chain"
        emptyTitle="No evidence"
        emptyBody="Nothing linked yet."
        items={[]}
      />,
    );

    expect(screen.getByText("No evidence")).toBeInTheDocument();
    expect(screen.getByText("Nothing linked yet.")).toBeInTheDocument();

    rerender(
      <EvidenceChain
        title="Evidence chain"
        emptyTitle="No evidence"
        emptyBody="Nothing linked yet."
        items={[
          {
            artifactId: "artifact-1",
            label: "Input bundle",
            meta: <span>primary source</span>,
            badge: <span>trusted</span>,
            href: "/artifacts/artifact-1",
          },
        ]}
      />,
    );

    expect(screen.getByText("Input bundle")).toBeInTheDocument();
    expect(screen.getByText("artifact-1")).toBeInTheDocument();
    expect(screen.getByText("primary source")).toBeInTheDocument();
    expect(screen.getByText("trusted")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/artifacts/artifact-1",
    );
  });

  it("renders StatusTimeline in regular and virtualized modes", () => {
    const { rerender } = renderWithProviders(
      <StatusTimeline
        emptyTitle="No events"
        emptyBody="Timeline is empty."
        items={[]}
      />,
    );

    expect(screen.getByText("No events")).toBeInTheDocument();

    rerender(
      <StatusTimeline
        emptyTitle="No events"
        emptyBody="Timeline is empty."
        items={[
          {
            id: "status-1",
            title: "Started",
            body: "Execution entered the queue.",
            timestamp: "2026-03-10T10:00:00Z",
            tone: "info",
            meta: <span>queued</span>,
          },
        ]}
      />,
    );

    expect(screen.getByText("Started")).toBeInTheDocument();
    expect(screen.getByText("Execution entered the queue.")).toBeInTheDocument();
    expect(screen.getByText("queued")).toBeInTheDocument();
    expect(screen.getByText("2026-03-10T10:00:00Z")).toBeInTheDocument();

    rerender(
      <StatusTimeline
        emptyTitle="No events"
        emptyBody="Timeline is empty."
        items={Array.from({ length: 31 }, (_, index) => ({
          id: `status-${index}`,
          title: `Event ${index}`,
          tone: index % 2 === 0 ? "ok" : "warn",
        }))}
      />,
    );

    expect(screen.getByText("Event 0")).toBeInTheDocument();
  });
});
