import { render, screen } from "@testing-library/react";

const { useAuthMeMock } = vi.hoisted(() => ({
  useAuthMeMock: vi.fn(),
}));

vi.mock("@/api/hooks/useAuthMe", () => ({
  useAuthMe: () => useAuthMeMock(),
}));

import {
  AuthzProvider,
  useAuthz,
  useReviewCollaborationEnabled,
} from "@/app/authz/AuthzProvider";

const authenticatedPrincipal = {
  meta: {
    generated_at: "2026-08-09T00:00:00Z",
    request_id: "authz-provider-test",
    source_kinds: [],
  },
  user_id: "analyst-a",
  display_name: "Analyst A",
  tenant_id: "tenant-a",
  principal_type: "user" as const,
  cell_id: "cell-a",
  roles: ["analyst"],
  permissions: ["runs.launch", "dashboard.view"],
  mfa_verified: true,
  feature_overrides: { enableReviewCollaboration: true },
};

function AuthorityProbe() {
  const authz = useAuthz();
  const collaborationEnabled = useReviewCollaborationEnabled();

  return (
    <output>
      {JSON.stringify({
        canLaunch: authz.can("runs.launch"),
        workspaceAllowed: authz.isWorkspaceAllowed("scenarioComposer"),
        mfaVerified: authz.user?.mfa_verified === true,
        collaborationEnabled,
        status: authz.status,
        userId: authz.user?.user_id ?? null,
      })}
    </output>
  );
}

function renderAuthz() {
  const view = render(
    <AuthzProvider>
      <AuthorityProbe />
    </AuthzProvider>,
  );
  return {
    readAuthority: () =>
      JSON.parse(screen.getByRole("status").textContent ?? "{}"),
    unmount: view.unmount,
  };
}

describe("AuthzProvider", () => {
  afterEach(() => {
    useAuthMeMock.mockReset();
  });

  it("test_authz_provider_denies_loading_error_malformed_401_prior_user_and_tenant_switch_identity", () => {
    for (const { label, query, expectedStatus } of [
      {
        label: "loading without identity",
        query: {
          data: undefined,
          isError: false,
          isLoading: true,
          isFetching: true,
        },
        expectedStatus: "loading",
      },
      {
        label: "401 or malformed identity error",
        query: {
          data: authenticatedPrincipal,
          isError: true,
          isLoading: false,
          isFetching: false,
        },
        expectedStatus: "error",
      },
      {
        label: "prior user and tenant data retained during refetch",
        query: {
          data: authenticatedPrincipal,
          isError: false,
          isLoading: false,
          isFetching: true,
          isSuccess: true,
        },
        expectedStatus: "loading",
      },
    ]) {
      useAuthMeMock.mockReturnValue(query);
      const { readAuthority, unmount } = renderAuthz();

      expect({ authority: readAuthority(), label }).toMatchObject({
        authority: {
          canLaunch: false,
          workspaceAllowed: false,
          mfaVerified: false,
          collaborationEnabled: false,
          status: expectedStatus,
          userId: null,
        },
        label,
      });
      unmount();
    }
  });

  it("uses a settled validated identity for generated permissions", () => {
    useAuthMeMock.mockReturnValue({
      data: authenticatedPrincipal,
      isError: false,
      isLoading: false,
      isFetching: false,
      isSuccess: true,
    });

    const { readAuthority } = renderAuthz();

    expect(readAuthority()).toMatchObject({
      canLaunch: true,
      workspaceAllowed: true,
      mfaVerified: true,
      collaborationEnabled: true,
      status: "ready",
      userId: "analyst-a",
    });
  });
});
