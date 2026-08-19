import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
} from "react-router-dom";

const { causalCanvasRenderMock, useAuthzMock, useRunDetailsMock } = vi.hoisted(
  () => ({
    causalCanvasRenderMock: vi.fn(),
    useAuthzMock: vi.fn(),
    useRunDetailsMock: vi.fn(),
  }),
);

vi.mock("@/api/hooks/useRunDetails", () => ({
  useRunDetails: (...args: unknown[]) => useRunDetailsMock(...args),
}));

vi.mock("@/app/authz/AuthzProvider", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/app/authz/AuthzProvider")>();

  return {
    ...actual,
    useAuthz: () => useAuthzMock(),
  };
});

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/shared/telemetry/performance", () => ({
  markUiMilestone: vi.fn(),
  measureUiLatency: vi.fn(),
}));

vi.mock("@/shared/components/FeatureAsyncBoundary", () => ({
  FeatureAsyncBoundary: ({ children }: { children: React.ReactNode }) =>
    children,
}));

vi.mock("@/shared/charts", () => ({
  BSTSVisualization: () => null,
  DiDVisualization: () => <output data-testid="method-visualization" />,
  ForestPlot: () => null,
  MetaLearnerViz: () => null,
  RDDVisualization: () => null,
  SyntheticControlViz: () => null,
}));

vi.mock("@/features/causal", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/causal")>();

  return {
    ...actual,
    AdjustmentSetHighlight: () => null,
    CausalGraphCanvas: ({
      edges,
      nodes,
    }: {
      edges: Array<Record<string, unknown>>;
      nodes: Array<Record<string, unknown>>;
    }) => {
      causalCanvasRenderMock(nodes);
      return (
        <>
          <output data-testid="causal-draft-nodes">
            {JSON.stringify(nodes)}
          </output>
          <output data-testid="causal-draft-edges">
            {JSON.stringify(edges)}
          </output>
        </>
      );
    },
    EdgeDetailPanel: () => null,
    IdentificationOverlay: () => null,
    NodeDetailPanel: () => null,
    PathAnalysisPanel: ({
      paths,
    }: {
      paths: Array<Record<string, unknown>>;
    }) => (
      <output data-testid="causal-draft-paths">{JSON.stringify(paths)}</output>
    ),
    TransportOverlay: () => null,
  };
});

import { createCausalDraftIdentificationDisplay } from "@/features/causal";

import CausalTab, {
  createCausalDraftPersistence,
  type CausalArtifactPayload,
} from "./CausalTab";

const NOW = new Date("2026-08-16T12:00:00.000Z");
const DAY_MS = 24 * 60 * 60 * 1_000;
const SCOPE_A = { tenantId: "tenant-a", userId: "user-a" };
const SCOPE_B = { tenantId: "tenant-b", userId: "user-b" };

class MemoryStorage {
  readonly calls: string[] = [];
  readonly values = new Map<string, string>();

  getItem(key: string) {
    this.calls.push(`get:${key}`);
    return this.values.get(key) ?? null;
  }

  removeItem(key: string) {
    this.calls.push(`remove:${key}`);
    this.values.delete(key);
  }

  setItem(key: string, value: string) {
    this.calls.push(`set:${key}`);
    this.values.set(key, value);
  }
}

function readyAuthz(scope = SCOPE_A) {
  return {
    status: "ready",
    user: { tenant_id: scope.tenantId, user_id: scope.userId },
  };
}

function graph(label = "Candidate node"): CausalArtifactPayload {
  return {
    adjustmentSet: ["treatment"],
    edges: [
      {
        ci: { level: 0.95, lower: 0.1, upper: 0.9 },
        estimate: 0.5,
        id: "treatment-outcome",
        literatureCount: 8,
        meta: { authority: "forged" },
        methodology: "did",
        source: "treatment",
        status: createCausalDraftIdentificationDisplay("identified"),
        target: "outcome",
        transportable: true,
      },
    ],
    methodData: { estimate: 0.5 },
    methodology: "did",
    nodes: [
      {
        ci: { level: 0.95, lower: 0.1, upper: 0.9 },
        dataAvailable: true,
        description: "Safe description",
        estimate: 0.5,
        evidenceCount: 4,
        id: "treatment",
        inAdjustmentSet: true,
        kind: "treatment",
        label,
        meta: { authority: "forged" },
      },
      { id: "outcome", kind: "outcome", label: "Outcome" },
    ],
    paths: [
      {
        edgeIds: ["treatment-outcome"],
        id: "forged-path",
        label: "forged",
        nodeIds: ["treatment", "outcome"],
        totalEffect: 0.5,
        type: "direct",
      },
    ],
  };
}

describe("causal draft persistence", () => {
  it("test_causal_state_rejects_cross_scope_stale_and_stored_status", () => {
    const storage = new MemoryStorage();
    const persistence = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storage,
    });

    expect(persistence.write(SCOPE_A, "run-a", graph())).toBe(true);
    const key = persistence.key(SCOPE_A, "run-a");
    expect(key).not.toBeNull();
    const raw = storage.getItem(key!);
    expect(raw).not.toBeNull();
    expect(raw).not.toMatch(
      /status|estimate|ci|dataAvailable|evidenceCount|inAdjustmentSet|methodology|methodData|transportable|literatureCount|meta|paths|adjustmentSet/,
    );

    const hydrated = persistence.read(SCOPE_A, "run-a");
    expect(hydrated?.nodes).toEqual([
      {
        description: "Safe description",
        id: "treatment",
        kind: "treatment",
        label: "Candidate node",
      },
      { id: "outcome", kind: "outcome", label: "Outcome" },
    ]);
    expect(hydrated?.edges[0]).toMatchObject({
      id: "treatment-outcome",
      source: "treatment",
      status: {
        authorityPurpose: "candidate_display",
        label: "unidentified",
        purpose: "interaction_only",
      },
      target: "outcome",
    });
    expect(hydrated?.paths).toHaveLength(1);
    expect(persistence.read(SCOPE_B, "run-a")).toBeNull();
    expect(persistence.read(null, "run-a")).toBeNull();

    window.localStorage.setItem(
      "polisyos:atlas:causal-draft:run-a",
      JSON.stringify({ graph: graph("Legacy authority") }),
    );
    expect(persistence.read(SCOPE_A, "missing-run")).toBeNull();

    const validEnvelope = JSON.parse(raw!) as Record<string, unknown>;
    const encodedPayload = validEnvelope.encodedPayload as {
      edges: Array<Record<string, unknown>>;
    } & Record<string, unknown>;
    const forbiddenStatusRaw = JSON.stringify({
      ...validEnvelope,
      encodedPayload: {
        ...encodedPayload,
        edges: encodedPayload.edges.map((edge, index) =>
          index === 0 ? { ...edge, status: "identified" } : edge,
        ),
      },
    });
    storage.setItem(key!, forbiddenStatusRaw);
    expect(persistence.read(SCOPE_A, "run-a")).toBeNull();
    expect(storage.getItem(key!)).toBe(forbiddenStatusRaw);

    const copiedKey = persistence.key(SCOPE_B, "run-a");
    storage.setItem(copiedKey!, raw!);
    expect(persistence.read(SCOPE_B, "run-a")).toBeNull();
    expect(storage.getItem(copiedKey!)).toBe(raw);

    storage.setItem(key!, "{malformed");
    expect(persistence.read(SCOPE_A, "run-a")).toBeNull();
    expect(storage.getItem(key!)).toBe("{malformed");
  });

  it.each([
    [
      "expired",
      new Date(NOW.getTime() - DAY_MS - 1),
      new Date(NOW.getTime() - 1),
    ],
    [
      "future",
      new Date(NOW.getTime() + 1),
      new Date(NOW.getTime() + DAY_MS + 1),
    ],
  ])(
    "rejects an exact-24-hour %s envelope without rewriting it",
    (_kind, issuedAt, expiresAt) => {
      const storage = new MemoryStorage();
      const persistence = createCausalDraftPersistence({
        clock: () => NOW,
        storage: () => storage,
      });
      expect(persistence.write(SCOPE_A, "run-a", graph())).toBe(true);
      const key = persistence.key(SCOPE_A, "run-a")!;
      const envelope = JSON.parse(storage.getItem(key)!) as Record<
        string,
        unknown
      >;
      const invalidRaw = JSON.stringify({
        ...envelope,
        expiresAt: expiresAt.toISOString(),
        issuedAt: issuedAt.toISOString(),
      });
      expect(expiresAt.getTime() - issuedAt.getTime()).toBe(DAY_MS);

      storage.setItem(key, invalidRaw);
      expect(persistence.read(SCOPE_A, "run-a")).toBeNull();
      expect(storage.getItem(key)).toBe(invalidRaw);
    },
  );

  it("owns an exact fixed 24-hour TTL with no caller override", () => {
    const storage = new MemoryStorage();
    const persistence = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storage,
    });

    expect(persistence.write(SCOPE_A, "run-a", graph())).toBe(true);
    const key = persistence.key(SCOPE_A, "run-a")!;
    const raw = storage.getItem(key)!;
    const envelope = JSON.parse(raw) as {
      expiresAt: string;
      issuedAt: string;
    };
    expect(Date.parse(envelope.expiresAt) - Date.parse(envelope.issuedAt)).toBe(
      DAY_MS,
    );

    const extended = JSON.parse(raw) as Record<string, unknown>;
    extended.expiresAt = new Date(NOW.getTime() + DAY_MS + 1).toISOString();
    storage.setItem(key, JSON.stringify(extended));
    expect(persistence.read(SCOPE_A, "run-a")).toBeNull();
    expect(persistence.write).toHaveLength(3);
  });

  it("fails closed for null and throwing storage access", () => {
    const absent = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => null,
    });
    expect(absent.read(SCOPE_A, "run-a")).toBeNull();
    expect(absent.write(SCOPE_A, "run-a", graph())).toBe(false);
    expect(absent.remove(SCOPE_A, "run-a")).toBe(false);

    function storageWithHostileMethod(
      method: "getItem" | "removeItem" | "setItem",
    ) {
      const hostile = {
        getItem: () => null,
        removeItem: () => undefined,
        setItem: () => undefined,
      };
      Object.defineProperty(hostile, method, {
        get() {
          throw new Error(`hostile ${method}`);
        },
      });
      return hostile;
    }
    const hostileGet = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storageWithHostileMethod("getItem"),
    });
    const hostileSet = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storageWithHostileMethod("setItem"),
    });
    const hostileRemove = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storageWithHostileMethod("removeItem"),
    });
    expect(hostileGet.read(SCOPE_A, "run-a")).toBeNull();
    expect(hostileSet.write(SCOPE_A, "run-a", graph())).toBe(false);
    expect(hostileRemove.remove(SCOPE_A, "run-a")).toBe(false);

    const resolverFailure = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => {
        throw new Error("storage getter failed");
      },
    });
    expect(resolverFailure.read(SCOPE_A, "run-a")).toBeNull();
    expect(resolverFailure.write(SCOPE_A, "run-a", graph())).toBe(false);
    expect(resolverFailure.remove(SCOPE_A, "run-a")).toBe(false);
  });

  it("does not resolve storage for null or incomplete write scopes", () => {
    const storage = new MemoryStorage();
    const storageResolver = vi.fn(() => storage);
    const persistence = createCausalDraftPersistence({
      clock: () => NOW,
      storage: storageResolver,
    });

    expect(persistence.write(null, "run-a", graph())).toBe(false);
    expect(
      persistence.write(
        { tenantId: "tenant-a", userId: "" },
        "run-a",
        graph(),
      ),
    ).toBe(false);
    expect(storageResolver).not.toHaveBeenCalled();
  });

  it("contains clock, codec, and hostile graph failures without changing bytes", () => {
    const storage = new MemoryStorage();
    const valid = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    expect(valid.write(SCOPE_A, "run-a", graph())).toBe(true);
    const key = valid.key(SCOPE_A, "run-a")!;
    const before = storage.getItem(key);

    const throwingClock = createCausalDraftPersistence({
      clock: () => {
        throw new Error("clock failed");
      },
      storage: () => storage,
    });
    expect(throwingClock.read(SCOPE_A, "run-a")).toBeNull();
    expect(throwingClock.write(SCOPE_A, "run-a", graph())).toBe(false);
    expect(storage.getItem(key)).toBe(before);

    const nonfiniteClock = createCausalDraftPersistence({
      clock: () => new Date(Number.NaN),
      storage: () => storage,
    });
    expect(nonfiniteClock.read(SCOPE_A, "run-a")).toBeNull();
    expect(nonfiniteClock.write(SCOPE_A, "run-a", graph())).toBe(false);
    expect(storage.getItem(key)).toBe(before);

    let nodesGetterObserved = false;
    const hostileGraph = Object.defineProperty({ edges: [] }, "nodes", {
      get() {
        nodesGetterObserved = true;
        throw new Error("hostile graph");
      },
    }) as unknown as CausalArtifactPayload;
    expect(valid.write(SCOPE_A, "run-a", hostileGraph)).toBe(false);
    expect(nodesGetterObserved).toBe(true);
    expect(storage.getItem(key)).toBe(before);
  });

  it("orders a synchronous write, remove, and reload without resurrection", () => {
    const storage = new MemoryStorage();
    const persistence = createCausalDraftPersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    const key = persistence.key(SCOPE_A, "run-a")!;
    storage.calls.splice(0);

    expect(persistence.write(SCOPE_A, "run-a", graph())).toBe(true);
    expect(persistence.remove(SCOPE_A, "run-a")).toBe(true);
    expect(persistence.read(SCOPE_A, "run-a")).toBeNull();
    expect(storage.calls).toEqual([`set:${key}`, `remove:${key}`, `get:${key}`]);
    expect(storage.values.has(key)).toBe(false);
  });
});

describe("CausalTab", () => {
  beforeEach(() => {
    causalCanvasRenderMock.mockClear();
    window.localStorage.clear();
    useAuthzMock.mockReset();
    useAuthzMock.mockReturnValue(readyAuthz());
    useRunDetailsMock.mockReset();
    useRunDetailsMock.mockReturnValue({
      data: { run: { artifacts: [] } },
      isLoading: false,
    });
  });

  it("keeps legacy and local causal drafts out of identified effect authority slots", async () => {
    window.localStorage.setItem(
      "polisyos:atlas:causal-draft:run-local",
      JSON.stringify({ graph: graph("Legacy authority") }),
    );

    render(
      <MemoryRouter initialEntries={["/runs/run-local/causal"]}>
        <Routes>
          <Route path="/runs/:runId/causal" element={<CausalTab />} />
        </Routes>
      </MemoryRouter>,
    );

    const nodes = await screen.findByTestId("causal-draft-nodes");
    const edges = screen.getByTestId("causal-draft-edges");
    const paths = screen.getByTestId("causal-draft-paths");

    expect(nodes).not.toHaveTextContent("Legacy authority");
    expect(edges).not.toHaveTextContent('"status":"identified"');
    expect(edges).not.toHaveTextContent("estimate");
    expect(paths).not.toHaveTextContent("totalEffect");
    expect(screen.queryByTestId("method-visualization")).not.toBeInTheDocument();
    expect(screen.getByText("phase32.causal.draft")).toBeInTheDocument();
  });

  it("separates delimiter-colliding scopes before paint and before persistence", async () => {
    const collidingScopeA = { tenantId: "a:b", userId: "c" };
    const collidingScopeB = { tenantId: "a", userId: "b:c" };
    const persistence = createCausalDraftPersistence({
      clock: () => new Date(),
      storage: () => window.localStorage,
    });
    expect(
      persistence.write(
        collidingScopeA,
        "same-run",
        graph("A private node"),
      ),
    ).toBe(true);
    const aKey = persistence.key(collidingScopeA, "same-run")!;
    const bKey = persistence.key(collidingScopeB, "same-run")!;
    expect(bKey).not.toBe(aKey);
    expect(window.localStorage.getItem(bKey)).toBeNull();
    useAuthzMock.mockReturnValue(readyAuthz(collidingScopeA));
    const causalRoute = () => (
      <MemoryRouter initialEntries={["/runs/same-run/causal"]}>
        <Routes>
          <Route path="/runs/:runId/causal" element={<CausalTab />} />
        </Routes>
      </MemoryRouter>
    );
    const view = render(causalRoute());
    expect(await screen.findByTestId("causal-draft-nodes")).toHaveTextContent(
      "A private node",
    );

    fireEvent.change(screen.getByLabelText("phase32.causal.nodeLabel"), {
      target: { value: "A dirty node" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "phase32.causal.addNode" }),
    );
    await waitFor(() =>
      expect(window.localStorage.getItem(aKey)).toContain("A dirty node"),
    );

    causalCanvasRenderMock.mockClear();
    useAuthzMock.mockReturnValue(readyAuthz(collidingScopeB));
    view.rerender(causalRoute());

    expect(
      causalCanvasRenderMock.mock.calls.some(([nodes]) =>
        JSON.stringify(nodes).includes("A dirty node"),
      ),
    ).toBe(false);
    expect(screen.getByTestId("causal-draft-nodes")).not.toHaveTextContent(
      "A dirty node",
    );
    expect(window.localStorage.getItem(bKey) ?? "").not.toContain(
      "A dirty node",
    );
  });

  it("hides an old binding immediately and never writes its graph under the next one", async () => {
    const persistence = createCausalDraftPersistence({
      clock: () => new Date(),
      storage: () => window.localStorage,
    });
    expect(persistence.write(SCOPE_A, "run-a", graph("A private node"))).toBe(
      true,
    );
    expect(persistence.write(SCOPE_B, "run-b", graph("B private node"))).toBe(
      true,
    );
    const bKey = persistence.key(SCOPE_B, "run-b")!;
    useAuthzMock.mockReturnValue(readyAuthz(SCOPE_A));
    const router = createMemoryRouter(
      [{ path: "/runs/:runId/causal", element: <CausalTab /> }],
      { initialEntries: ["/runs/run-a/causal"] },
    );

    render(<RouterProvider router={router} />);
    expect(await screen.findByTestId("causal-draft-nodes")).toHaveTextContent(
      "A private node",
    );

    useAuthzMock.mockReturnValue(readyAuthz(SCOPE_B));
    await act(async () => {
      await router.navigate("/runs/run-b/causal");
    });

    const nodes = screen.getByTestId("causal-draft-nodes");
    expect(nodes).not.toHaveTextContent("A private node");
    await waitFor(() => expect(nodes).toHaveTextContent("B private node"));
    expect(window.localStorage.getItem(bKey)).not.toContain("A private node");

    useAuthzMock.mockReturnValue({ status: "loading", user: undefined });
    await act(async () => {
      await router.navigate("/runs/run-a/causal");
    });
    expect(screen.getByTestId("causal-draft-nodes")).not.toHaveTextContent(
      "A private node",
    );
  });
});
