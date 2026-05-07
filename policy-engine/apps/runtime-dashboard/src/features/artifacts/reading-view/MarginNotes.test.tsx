import { render, screen } from "@testing-library/react";

import { MarginNotes } from "./MarginNotes";

const notes = [
  {
    anchorId: "intro",
    body: "First note in the right rail.",
    id: "note-1",
    label: "Packet",
  },
  {
    anchorId: "evidence",
    body: "Second note should stack below the first.",
    id: "note-2",
    label: "Evidence",
  },
];

describe("MarginNotes", () => {
  it("renders inline note cards for compact layouts", () => {
    render(<MarginNotes inline notes={notes} />);

    expect(
      screen.getByText(/first note in the right rail/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/second note should stack below the first/i),
    ).toBeInTheDocument();
  });

  it("stacks absolutely-positioned notes without overlap", () => {
    render(
      <MarginNotes
        notes={notes}
        positions={{
          evidence: 20,
          intro: 10,
        }}
      />,
    );

    const rendered = screen.getByLabelText(/margin notes/i);
    expect(rendered).toBeInTheDocument();
    const packetNote = screen.getByTestId("margin-note-note-1");
    const evidenceNote = screen.getByTestId("margin-note-note-2");

    expect(packetNote).toHaveStyle({ top: "10px" });
    expect(evidenceNote).toHaveStyle({ top: "94px" });
  });
});
