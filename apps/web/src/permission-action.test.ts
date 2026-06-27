import { describe, expect, it } from "vitest";

import { reviewDecideActionState } from "./permission-action";

describe("reviewDecideActionState", () => {
  const labels = {
    denied: "Current persona cannot perform this action.",
    elevated: "Action disabled while elevated mode is active.",
  };

  it("allows when review permission is granted and elevated mode is off", () => {
    expect(reviewDecideActionState(true, false, labels)).toEqual({
      allowed: true,
      disabledTitle: undefined,
      blockedNotice: null,
    });
  });

  it("blocks when review permission is denied", () => {
    expect(reviewDecideActionState(false, false, labels)).toEqual({
      allowed: false,
      disabledTitle: labels.denied,
      blockedNotice: labels.denied,
    });
  });

  it("blocks when elevated mode is active", () => {
    expect(reviewDecideActionState(true, true, labels)).toEqual({
      allowed: false,
      disabledTitle: labels.elevated,
      blockedNotice: labels.elevated,
    });
  });
});
