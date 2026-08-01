import { render, screen } from "@testing-library/react";
import { Search } from "lucide-react";
import { createRef } from "react";
import { MemoryRouter } from "react-router-dom";
import * as atlasUi from "../src/index";

describe("foundation primitives", () => {
  it("preserves state, polymorphism, presentation, and skeleton behavior", () => {
    expect(Object.keys(atlasUi)).toContain("AsyncSection");

    render(
      <MemoryRouter>
        <atlasUi.TextPresentationProvider
          locale="uk"
          transform={(node) =>
            typeof node === "string"
              ? node.replace("PolicyOS", "Policy OS")
              : node
          }
        >
          <atlasUi.Card>
            <atlasUi.CardHeader>
              <atlasUi.CardTitle>Runtime</atlasUi.CardTitle>
              <atlasUi.CardDescription>Evidence view</atlasUi.CardDescription>
            </atlasUi.CardHeader>
            <atlasUi.CardContent>
              <atlasUi.AsyncSection
                query={{ isError: false, isLoading: false }}
                renderError={({ title }) => <div>{title}</div>}
              >
                <atlasUi.Badge kind="ok">Healthy</atlasUi.Badge>
                <atlasUi.Button to="/runs">Open runs</atlasUi.Button>
                <atlasUi.Button href="/export">Export</atlasUi.Button>
                <atlasUi.Button type="button">Inspect</atlasUi.Button>
                <atlasUi.EmptyState title="Empty" body="No evidence" />
                <atlasUi.Icon icon={Search} label="Search" />
                <atlasUi.Spinner data-testid="spinner" />
                <atlasUi.Text>PolicyOS evidence</atlasUi.Text>
                <atlasUi.SkeletonText lines={2} />
                <atlasUi.SkeletonChart />
                <atlasUi.SkeletonCard />
                <atlasUi.SkeletonTable rows={2} cols={2} />
                <atlasUi.PageSkeleton />
                <atlasUi.PanelSkeleton rows={2} />
                <atlasUi.MetricsSkeleton count={2} />
              </atlasUi.AsyncSection>
            </atlasUi.CardContent>
          </atlasUi.Card>
        </atlasUi.TextPresentationProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Open runs" })).toHaveAttribute(
      "href",
      "/runs",
    );
    expect(screen.getByRole("link", { name: "Export" })).toHaveAttribute(
      "href",
      "/export",
    );
    expect(screen.getByRole("button", { name: "Inspect" })).toBeInTheDocument();
    expect(screen.getByLabelText("Search")).toBeInTheDocument();
    const transformedText = screen.getByText(
      (_, element) => element?.textContent === "Policy OS evidence",
    );
    expect(transformedText).toHaveAttribute("lang", "uk");
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
    expect(screen.getAllByTestId("skeleton-block")).toHaveLength(37);
  });

  it("uses the typed dashboard-owned error presentation slot", () => {
    render(
      <atlasUi.AsyncSection
        query={{ isError: true, error: new Error("unavailable") }}
        errorTitle="Runtime failed"
        renderError={({ error, title }) => (
          <div>{`${title}: ${String(error)}`}</div>
        )}
      >
        resolved
      </atlasUi.AsyncSection>,
    );

    expect(
      screen.getByText("Runtime failed: Error: unavailable"),
    ).toBeInTheDocument();
  });

  it("preserves Button asChild props, styling, and ref forwarding", () => {
    const linkRef = createRef<HTMLAnchorElement>();

    render(
      <atlasUi.Button asChild ref={linkRef}>
        <a href="/wrapped-action" data-presentation="child">
          Wrapped action
        </a>
      </atlasUi.Button>,
    );

    const link = screen.getByRole("link", { name: "Wrapped action" });
    expect(link).toHaveAttribute("href", "/wrapped-action");
    expect(link).toHaveAttribute("data-presentation", "child");
    expect(link).toHaveClass("inline-flex");
    expect(linkRef.current).toBe(link);
  });
});
