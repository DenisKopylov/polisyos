import type { Plugin } from "vite";
import type {
  Reporter,
  SerializedError,
  TestCase,
  TestModule,
} from "vitest/node";

/** Keep the error's actual cause when a reporter prefers its captured stack. */
function preserveCause(error: SerializedError): void {
  if (error.message && !error.stack?.includes(error.message)) {
    error.stack = `${error.name || "Error"}: ${error.message}\n${error.stack || ""}`;
  }
}

class PreserveErrorCauseReporter implements Reporter {
  onTestCaseResult(testCase: TestCase): void {
    for (const error of testCase.result().errors ?? []) preserveCause(error);
  }

  onTestRunEnd(
    modules: readonly TestModule[],
    unhandledErrors: readonly SerializedError[],
  ): void {
    for (const module of modules) {
      for (const error of module.errors()) preserveCause(error);
      for (const suite of module.children.allSuites()) {
        for (const error of suite.errors()) preserveCause(error);
      }
      for (const testCase of module.children.allTests()) {
        this.onTestCaseResult(testCase);
      }
    }
    for (const error of unhandledErrors) preserveCause(error);
  }
}

/** Enroll after CLI selection, so explicit JSON reporters retain real causes. */
export function preserveVitestErrorCause(): Plugin {
  return {
    name: "polisyos-preserve-vitest-error-cause",
    configureVitest({ vitest }) {
      if (
        !vitest.config.reporters.some(
          (reporter) => reporter instanceof PreserveErrorCauseReporter,
        )
      ) {
        vitest.config.reporters.unshift(new PreserveErrorCauseReporter());
      }
    },
  };
}
