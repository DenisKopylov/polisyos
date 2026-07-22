import {
  normalizeGovernanceIssues,
  summarizeGovernanceIssues,
} from "@/shared/lib/domain/governance";

describe("governance domain", () => {
  it("normalizes issues from mixed payload shapes", () => {
    const issues = normalizeGovernanceIssues([
      {
        code: "TRANSPORT_FAIL",
        duration_ms: "10",
        message: "Transport failed",
        pass_id: "transport",
        path: ["payload", 1, "status"],
        severity: "error",
      },
      {
        issue_code: "WARN_1",
        level: "warn",
        msg: "Warning emitted",
        path: "governance.summary",
        scope: "summary",
      },
      {
        check_id: "review",
        description: "Needs review",
        type: "notice",
      },
      {
        message: "Unknown issue",
      },
      null,
    ]);

    expect(issues).toEqual([
      {
        code: "TRANSPORT_FAIL",
        durationMs: 10,
        message: "Transport failed",
        passId: "transport",
        path: "payload.1.status",
        raw: expect.any(Object),
        severity: "error",
      },
      {
        code: "WARN_1",
        durationMs: null,
        message: "Warning emitted",
        passId: "summary",
        path: "governance.summary",
        raw: expect.any(Object),
        severity: "warn",
      },
      {
        code: "issue_3",
        durationMs: null,
        message: "Needs review",
        passId: "review",
        path: null,
        raw: expect.any(Object),
        severity: "notice",
      },
      {
        code: "issue_4",
        durationMs: null,
        message: "Unknown issue",
        passId: null,
        path: null,
        raw: expect.any(Object),
        severity: null,
      },
    ]);
  });

  it("counts opaque owner labels without merging or guessing them", () => {
    const summary = summarizeGovernanceIssues(
      normalizeGovernanceIssues([
        { message: "Blocker", severity: "fail" },
        { message: "Warning", severity: "warning" },
        { message: "Info", severity: "notice" },
        { message: "Unknown" },
      ]),
    );

    expect(summary).toEqual({
      byOwnerLabel: {
        fail: 1,
        notice: 1,
        warning: 1,
      },
      total: 4,
      unlabeled: 1,
    });
  });

  it("preserves novel severity labels as distinct owner extensions", () => {
    const [issue] = normalizeGovernanceIssues([
      { message: "Future owner label", severity: "future_owner_severity" },
    ]);

    expect(issue?.severity).toBe("future_owner_severity");
    expect(summarizeGovernanceIssues(issue ? [issue] : [])).toEqual({
      byOwnerLabel: { future_owner_severity: 1 },
      total: 1,
      unlabeled: 0,
    });
  });
});
