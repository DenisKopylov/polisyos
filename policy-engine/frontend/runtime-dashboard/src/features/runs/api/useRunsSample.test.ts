const { runsQueryOptionsMock, useRunsMock, useSuspenseRunsMock } = vi.hoisted(
  () => ({
    runsQueryOptionsMock: vi.fn(),
    useRunsMock: vi.fn(),
    useSuspenseRunsMock: vi.fn(),
  }),
);

vi.mock("@/api/hooks/useRuns", () => ({
  runsQueryOptions: (...args: unknown[]) => runsQueryOptionsMock(...args),
  useRuns: (...args: unknown[]) => useRunsMock(...args),
  useSuspenseRuns: (...args: unknown[]) => useSuspenseRunsMock(...args),
}));

import { RUNS_SAMPLE_LIMIT } from "@/lib/constants";
import {
  runsSampleQueryOptions,
  useRunsSample,
  useSuspenseRunsSample,
} from "@/features/runs/api/useRunsSample";

describe("useRunsSample wrappers", () => {
  beforeEach(() => {
    runsQueryOptionsMock.mockReset();
    useRunsMock.mockReset();
    useSuspenseRunsMock.mockReset();
  });

  it("uses the sample limit for query options and hooks", () => {
    runsQueryOptionsMock.mockReturnValue({ queryKey: ["runs", "sample"] });
    useRunsMock.mockReturnValue({ data: [] });
    useSuspenseRunsMock.mockReturnValue({ data: [{ run_id: "run-1" }] });

    expect(runsSampleQueryOptions()).toEqual({ queryKey: ["runs", "sample"] });
    expect(useRunsSample()).toEqual({ data: [] });
    expect(useSuspenseRunsSample()).toEqual({
      data: [{ run_id: "run-1" }],
    });

    expect(runsQueryOptionsMock).toHaveBeenCalledWith({
      limit: RUNS_SAMPLE_LIMIT,
    });
    expect(useRunsMock).toHaveBeenCalledWith({ limit: RUNS_SAMPLE_LIMIT });
    expect(useSuspenseRunsMock).toHaveBeenCalledWith({
      limit: RUNS_SAMPLE_LIMIT,
    });
  });
});
