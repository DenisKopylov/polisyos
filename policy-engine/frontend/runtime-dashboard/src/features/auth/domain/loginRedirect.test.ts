import { describe, expect, it } from "vitest";

import { buildLoginNavigationTarget } from "./loginRedirect";

describe("buildLoginNavigationTarget", () => {
  it("uses SPA navigation for the internal login route", () => {
    expect(
      buildLoginNavigationTarget("/runs?status=running", "/login", "/login"),
    ).toEqual({
      href: "/login?next=%2Fruns%3Fstatus%3Drunning",
      mode: "spa",
      usesDedicatedLogin: false,
    });
  });

  it("uses full-page navigation for relative server-owned auth endpoints", () => {
    expect(
      buildLoginNavigationTarget("/runs", "/auth/login", "/login"),
    ).toEqual({
      href: "/auth/login?next=%2Fruns",
      mode: "document",
      usesDedicatedLogin: true,
    });
  });

  it("preserves absolute login URLs and appends next", () => {
    expect(
      buildLoginNavigationTarget(
        "/runs/123",
        "https://auth.example.com/login",
        "/login",
      ),
    ).toEqual({
      href: "https://auth.example.com/login?next=%2Fruns%2F123",
      mode: "document",
      usesDedicatedLogin: true,
    });
  });
});
