import { render, screen } from "@testing-library/react";

const { useI18nMock } = vi.hoisted(() => ({
  useI18nMock: vi.fn(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => useI18nMock(),
}));

import ErrorsPanel from "@/features/runs/components/debug/ErrorsPanel";

describe("ErrorsPanel", () => {
  beforeEach(() => {
    useI18nMock.mockReset();
    useI18nMock.mockReturnValue({
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    });
  });

  it("renders the empty state when no errors are available", () => {
    render(<ErrorsPanel errors={[]} />);

    expect(screen.getByText("panels.errors.empty")).toBeInTheDocument();
    expect(
      screen.getByText('panels.errors.total:{"count":0}'),
    ).toBeInTheDocument();
  });

  it("groups errors by source and renders details payloads", () => {
    render(
      <ErrorsPanel
        errors={[
          {
            code: "WF-1",
            details: { attempt: 1 },
            message: "Workflow report missing a verdict.",
            node_alias: "governance",
            source: "workflow_report",
            timestamp: "2026-03-10T10:00:00Z",
          },
          {
            code: "TRACE-2",
            details: { retry: true },
            message: "Trace span timed out.",
            node_alias: null,
            source: "trace",
            timestamp: "2026-03-10T10:05:00Z",
          },
          {
            code: "MANIFEST-3",
            details: {},
            message: "Manifest schema mismatch.",
            node_alias: null,
            source: "manifest",
            timestamp: null,
          },
          {
            code: "RUNTIME-4",
            details: { severity: "high" },
            message: "Runtime worker crashed.",
            node_alias: null,
            source: "runtime",
            timestamp: null,
          },
        ]}
      />,
    );

    expect(screen.getByText("workflow_report: 1")).toBeInTheDocument();
    expect(screen.getByText("trace: 1")).toBeInTheDocument();
    expect(screen.getByText("manifest: 1")).toBeInTheDocument();
    expect(screen.getByText("runtime: 1")).toBeInTheDocument();
    expect(
      screen.getByText('panels.errors.node:{"alias":"governance"}'),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Workflow report missing a verdict."),
    ).toBeInTheDocument();
    expect(screen.getByText("Trace span timed out.")).toBeInTheDocument();
    expect(screen.getByText(/"attempt": 1/)).toBeInTheDocument();
    expect(screen.getByText(/"retry": true/)).toBeInTheDocument();
    expect(screen.getByText(/"severity": "high"/)).toBeInTheDocument();
  });
});
