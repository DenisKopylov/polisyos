import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";
import { evidenceArtifactRefKey } from "@/shared/lib/domain/evidence";

import LineageGraph from "./LineageGraph";

describe("LineageGraph", () => {
  it("renders the empty state when there are no nodes", () => {
    renderWithProviders(<LineageGraph nodes={[]} edges={[]} />);

    expect(screen.getByText("Lineage graph is empty.")).toBeInTheDocument();
  });

  it("renders the threshold fallback when the graph exceeds the configured size", () => {
    renderWithProviders(
      <LineageGraph
        nodes={Array.from({ length: 3 }, (_, index) => ({
          artifact_id: `artifact-${index}`,
          depth: index,
          status: "ok",
        }))}
        edges={[]}
        maxNodesForGraph={2}
      />,
    );

    expect(
      screen.getByText("Graph nodes: 3; render threshold: 2."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Narrow the lineage scope (`max_depth`/`max_nodes`) for interactive rendering.",
      ),
    ).toBeInTheDocument();
  });

  it("renders lineage cards and artifact inspection links", () => {
    renderWithProviders(
      <LineageGraph
        nodes={[
          {
            artifact_id: "artifact-root",
            depth: 0,
            kind: "decision_packet",
            status: "ok",
          },
          {
            artifact_id: "artifact-child",
            depth: 1,
            kind: "evidence_bundle",
            status: "error",
          },
        ]}
        edges={[
          {
            parent_artifact_id: "artifact-root",
            child_artifact_id: "artifact-child",
            role: "derived_from",
          },
        ]}
        rootArtifactIds={["artifact-root"]}
      />,
    );

    expect(screen.getByText("artifact-root")).toBeInTheDocument();
    expect(screen.getByText("artifact-child")).toBeInTheDocument();
    expect(screen.getByText("decision_packet")).toBeInTheDocument();
    expect(screen.getByText("evidence_bundle")).toBeInTheDocument();
    const rootInspectLink = screen.getAllByRole("link", { name: "Inspect" })[0];
    const rootHref = new URL(
      rootInspectLink?.getAttribute("href") ?? "",
      "http://localhost",
    );
    expect(rootHref.pathname).toBe("/artifacts/artifact-root");
    expect(rootHref.searchParams.get("tab")).toBe("content");
    expect(
      JSON.parse(rootHref.searchParams.get("artifactRefKey") ?? "null"),
    ).toEqual(["artifact-root", "decision_packet", null, null]);
  });

  it("keeps novel producer statuses opaque instead of guessing authority colors", () => {
    renderWithProviders(
      <LineageGraph
        nodes={[
          { artifact_id: "artifact-ok", depth: 0, status: "ok" },
          { artifact_id: "artifact-partial", depth: 0, status: "partial" },
          {
            artifact_id: "artifact-novel",
            depth: 0,
            status: "awaiting_external_attestation",
          },
        ]}
        edges={[]}
      />,
    );

    const renderedColors = [
      screen.getByText("ok"),
      screen.getByText("partial"),
      screen.getByText("awaiting_external_attestation"),
    ].map((status) => status.style.color);

    expect(new Set(renderedColors).size).toBe(1);
  });

  it("keeps same-content nodes and links keyed by their selected manifest profiles", () => {
    const firstProfile = `sha256:${"a".repeat(64)}`;
    const secondProfile = `sha256:${"b".repeat(64)}`;
    renderWithProviders(
      <LineageGraph
        nodes={[
          {
            artifact_id: "artifact-shared",
            manifest_profile_sha256: firstProfile,
            depth: 0,
            kind: "profile.first",
            status: "present",
          },
          {
            artifact_id: "artifact-shared",
            manifest_profile_sha256: secondProfile,
            depth: 1,
            kind: "profile.second",
            status: "present",
          },
        ]}
        edges={[
          {
            parent_artifact_id: "artifact-shared",
            parent_manifest_profile_sha256: firstProfile,
            child_artifact_id: "artifact-shared",
            child_manifest_profile_sha256: secondProfile,
            role: "selected-input",
          },
        ]}
        rootArtifactRefs={[
          {
            artifact_id: "artifact-shared",
            manifest_profile_sha256: firstProfile,
          },
        ]}
      />,
    );

    expect(screen.getAllByText("artifact-shared")).toHaveLength(2);
    expect(screen.getByText("profile.first")).toBeInTheDocument();
    expect(screen.getByText("profile.second")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Artifact lineage graph" }),
    ).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "Inspect" });
    expect(links).toHaveLength(2);
    expect(
      new URL(
        links[0]?.getAttribute("href") ?? "",
        "http://localhost",
      ).searchParams.get("artifactRefKey"),
    ).toBe(
      evidenceArtifactRefKey({
        artifact_id: "artifact-shared",
        kind: "profile.first",
        media_type: null,
        manifest_profile_sha256: firstProfile,
      }),
    );
    expect(
      new URL(
        links[1]?.getAttribute("href") ?? "",
        "http://localhost",
      ).searchParams.get("artifactRefKey"),
    ).toBe(
      evidenceArtifactRefKey({
        artifact_id: "artifact-shared",
        kind: "profile.second",
        media_type: null,
        manifest_profile_sha256: secondProfile,
      }),
    );
  });

  it("does not collapse nodes with the same ID and profile but different ref metadata", () => {
    const profile = `sha256:${"a".repeat(64)}`;
    const firstRef = {
      artifact_id: "artifact-shared",
      kind: "profile.json",
      media_type: "application/json",
      manifest_profile_sha256: profile,
    };
    const secondRef = {
      ...firstRef,
      kind: "profile.text",
      media_type: "text/plain",
    };
    renderWithProviders(
      <LineageGraph
        nodes={[
          { ...firstRef, depth: 0, status: "present" },
          { ...secondRef, depth: 0, status: "present" },
        ]}
        edges={[]}
        rootArtifactRefs={[firstRef, secondRef]}
      />,
    );

    expect(screen.getByText("profile.json")).toBeInTheDocument();
    expect(screen.getByText("profile.text")).toBeInTheDocument();
    const urls = screen
      .getAllByRole("link", { name: "Inspect" })
      .map(
        (link) => new URL(link.getAttribute("href") ?? "", "http://localhost"),
      );
    expect(urls).toHaveLength(2);
    expect(urls[0]?.searchParams.get("artifactRefKey")).not.toBe(
      urls[1]?.searchParams.get("artifactRefKey"),
    );
  });
});
