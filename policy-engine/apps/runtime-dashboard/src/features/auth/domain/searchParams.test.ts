import { parseLoginSearchParams } from "@/features/auth/domain/searchParams";

describe("parseLoginSearchParams", () => {
  it("keeps safe relative next targets", () => {
    expect(parseLoginSearchParams("/login?next=/runs/run-1/overview")).toEqual({
      next: "/runs/run-1/overview",
    });
  });

  it("falls back to home for unsafe targets", () => {
    expect(parseLoginSearchParams("/login?next=https://evil.example")).toEqual({
      next: "/",
    });
    expect(parseLoginSearchParams("/login?next=//evil.example")).toEqual({
      next: "/",
    });
  });
});
