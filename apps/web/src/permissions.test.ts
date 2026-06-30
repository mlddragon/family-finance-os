import { describe, expect, it } from "vitest";

import { UI_PERMISSION_CHECKS } from "./permissions";

function permissionCheck(id: string) {
  const check = UI_PERMISSION_CHECKS.find((entry) => entry.id === id);
  expect(check).toBeDefined();
  return check!;
}

describe("UI permission checks", () => {
  it("maps source profile confirmation to import settings configure", () => {
    expect(permissionCheck("importSettings")).toMatchObject({
      action_key: "imports.settings.configure",
      data_scope_key: "source_profiles_import_config",
    });
  });

  it("maps editable runtime settings to runtime settings manage", () => {
    expect(permissionCheck("settings")).toMatchObject({
      action_key: "runtime.settings.manage",
      data_scope_key: "runtime_settings",
    });
  });

  it("keeps import and runtime settings permissions distinct", () => {
    const importSettings = permissionCheck("importSettings");
    const runtimeSettings = permissionCheck("settings");

    expect(importSettings.action_key).not.toBe(runtimeSettings.action_key);
    expect(importSettings.data_scope_key).not.toBe(runtimeSettings.data_scope_key);
  });
});
