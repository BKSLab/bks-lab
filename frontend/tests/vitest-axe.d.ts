import "vitest";
import type { AxeMatchers } from "vitest-axe/matchers";

// vitest-axe 0.1 targets the old global Vi namespace; Vitest 3 uses this module.
declare module "vitest" {
  interface Assertion {
    toHaveNoViolations: AxeMatchers["toHaveNoViolations"];
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations: AxeMatchers["toHaveNoViolations"];
  }
}
