const sourcePath = "^src/";

export default {
  forbidden: [
    {
      name: "no-circular",
      comment: "Keep the feature-sliced graph acyclic.",
      severity: "error",
      from: {},
      to: {
        circular: true,
      },
    },
    {
      name: "no-legacy-pages",
      comment: "Legacy src/pages modules must not be reintroduced.",
      severity: "error",
      from: {
        path: sourcePath,
      },
      to: {
        path: "^src/pages/",
      },
    },
    {
      name: "no-legacy-components",
      comment: "Legacy src/components modules must not be reintroduced.",
      severity: "error",
      from: {
        path: sourcePath,
      },
      to: {
        path: "^src/components/",
      },
    },
    {
      name: "shared-no-app-or-features",
      comment: "Shared code cannot depend on app or feature layers.",
      severity: "error",
      from: {
        path: "^src/shared/",
      },
      to: {
        path: "^src/(app|features)/",
      },
    },
    {
      name: "lib-no-ui-layers",
      comment:
        "lib must stay framework-agnostic and cannot depend on UI layers.",
      severity: "error",
      from: {
        path: "^src/lib/",
      },
      to: {
        path: "^src/(app|features|shared)/",
      },
    },
    {
      name: "app-no-feature-internals",
      comment:
        "app may depend only on feature public APIs, never feature internals.",
      severity: "error",
      from: {
        path: "^src/app/",
      },
      to: {
        path: "^src/features/.+/(?!index\\.ts$|index\\.tsx$).*",
      },
    },
  ],
  options: {
    doNotFollow: {
      path: "node_modules",
    },
    exclude: {
      path: "^(dist|storybook-static|test-results|coverage|node_modules)",
    },
    tsConfig: {
      fileName: "tsconfig.app.json",
    },
  },
};
