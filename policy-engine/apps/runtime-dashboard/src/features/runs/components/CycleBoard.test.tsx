import { render, screen, within } from "@testing-library/react";

import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

import { CycleBoard } from "./CycleBoard";

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe("CycleBoard honest hero rendering", () => {
  it("renders all known rows and the board's own two typed absences", () => {
    const packet = cycleBoardProjectionPacketFixture();

    render(<CycleBoard projection={{ packet, payload: packet.payload }} />);

    const board = screen.getByTestId("cycle-board");
    expect(board).toHaveAttribute("data-audiences", "REVIEWER,EXPERT");
    expect(board).not.toHaveAttribute(
      "data-audiences",
      expect.stringContaining("PUBLIC"),
    );
    const rows = screen.getAllByTestId("cycle-board-row");
    expect(rows).toHaveLength(16);
    expect(rows.slice(0, 3).map((row) => row.dataset.rowId)).toEqual([
      "n10:first_vertical",
      "n10:education",
      "n10:unseen",
    ]);
    expect(rows.slice(3).map((row) => row.dataset.rowId)).toEqual(
      Array.from(
        { length: 13 },
        (_, index) => `legacy:case-${String(index + 1).padStart(2, "0")}`,
      ),
    );

    const coverage = screen.getByTestId("cycle-board-coverage-gap");
    expect(coverage).toHaveTextContent(
      "production_recursive_cycle_run_enumeration",
    );
    expect(coverage).toHaveTextContent("not_established");
    expect(coverage).toHaveTextContent("GY-GAP5 -> runtime/quality GY-N12");
    expect(coverage).toHaveAttribute("data-exhaustive", "false");
    expect(coverage).toHaveAttribute("data-known-row-count", "16");

    const movement = screen.getByTestId("cycle-board-movement-gap");
    expect(movement).toHaveTextContent(
      "acquisition_reentry_deeper_terminal_binding",
    );
    expect(movement).toHaveTextContent("not_established");
    expect(movement).toHaveTextContent("GY-GAP6 -> GY-N13b");
    expect(screen.queryAllByTestId("cycle-board-movement")).toHaveLength(0);
  });

  it("renders owner route references and separately resolved economics", () => {
    const packet = cycleBoardProjectionPacketFixture();

    render(<CycleBoard projection={{ packet, payload: packet.payload }} />);

    const firstRow = screen.getAllByTestId("cycle-board-row")[0];
    const educationRow = screen.getAllByTestId("cycle-board-row")[1];
    if (!firstRow || !educationRow) {
      throw new Error("fixture must render the ordered capstone cohort");
    }
    const route = within(firstRow).getByTestId("cycle-board-acquisition-route");
    const economics = within(firstRow).getByTestId(
      "cycle-board-acquisition-economics",
    );
    expect(route).toHaveTextContent("sha256:owner-first_vertical");
    expect(route).toHaveTextContent("gap-first_vertical");
    expect(economics).toHaveTextContent("production_snapshot_build");
    expect(economics).toHaveTextContent("1250");
    expect(economics).toHaveTextContent("0.41");
    expect(economics).toHaveTextContent("not_established");

    expect(
      within(educationRow).getByTestId("cycle-board-acquisition-route"),
    ).toHaveAttribute("data-availability", "not_established");
    expect(
      within(educationRow).getByTestId("cycle-board-acquisition-economics"),
    ).toHaveTextContent("production_snapshot_build");
  });

  it("renders absent lifecycle terminality as absent, never false", () => {
    const packet = cycleBoardProjectionPacketFixture();

    render(<CycleBoard projection={{ packet, payload: packet.payload }} />);

    const firstRow = screen.getAllByTestId("cycle-board-row")[0];
    if (!firstRow) {
      throw new Error("fixture must render its first capstone row");
    }
    const lifecycle = within(firstRow).getByTestId(
      "cycle-board-lifecycle-terminality",
    );
    const searchTerminal = within(firstRow).getByTestId(
      "cycle-board-search-terminal",
    );
    expect(lifecycle).toHaveAttribute("data-availability", "not_established");
    expect(lifecycle).not.toHaveTextContent(/false|non.?terminal/iu);
    expect(searchTerminal).toHaveTextContent("acquisition_required");
    expect(searchTerminal).not.toHaveTextContent("not_established");
  });

  it("renders every source's own state and never invents board-global freshness", () => {
    const packet = cycleBoardProjectionPacketFixture();

    render(<CycleBoard projection={{ packet, payload: packet.payload }} />);

    const sources = screen.getAllByTestId("cycle-board-source");
    expect(sources).toHaveLength(packet.composition_manifest.length);
    expect(sources.map((source) => source.dataset.sourceId)).toEqual(
      packet.composition_manifest.map((source) => source.source_id),
    );
    expect(sources[0]).toHaveTextContent("2026-07-29T10:00:00Z");
    expect(sources[0]).toHaveTextContent("source_timestamp");
    expect(sources[0]).toHaveTextContent("observed");
    expect(sources[1]).toHaveAttribute("data-availability", "invalid_source");
    expect(sources[4]).toHaveAttribute("data-availability", "artifact_missing");
    expect(
      screen.queryByTestId("cycle-board-global-freshness"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /^(?:current|fresh|up[- ]to[- ]date|board (?:is )?(?:current|fresh|up[- ]to[- ]date))$/iu,
      ),
    ).not.toBeInTheDocument();
  });
});
