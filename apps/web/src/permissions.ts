import type { EffectivePermission, UIPermissionCheck } from "./types";

export const UI_PERMISSION_CHECKS: UIPermissionCheck[] = [
  {
    id: "imports",
    label: "Run imports",
    action_key: "imports.run",
    data_scope_key: "imported_source_records",
  },
  {
    id: "review",
    label: "Review decisions",
    action_key: "review.decide",
    data_scope_key: "review_decisions",
  },
  {
    id: "reports",
    label: "Generate reports",
    action_key: "reports.generate",
    data_scope_key: "reports_dashboards",
  },
  {
    id: "monthlyClose",
    label: "Monthly close",
    action_key: "monthly_close.run",
    data_scope_key: "monthly_close",
  },
  {
    id: "exports",
    label: "Advisor exports",
    action_key: "exports.create",
    data_scope_key: "advisor_export_artifacts",
  },
  {
    id: "settings",
    label: "Manage settings",
    action_key: "runtime.settings.manage",
    data_scope_key: "runtime_settings",
  },
];

export type UIPermissionMap = Record<string, EffectivePermission>;

export function defaultUIPermissionMap(): UIPermissionMap {
  return Object.fromEntries(
    UI_PERMISSION_CHECKS.map((check) => [
      check.id,
      {
        allowed: false,
        suggestion_allowed: false,
        action_key: check.action_key,
        data_scope_key: check.data_scope_key,
        action_effect: null,
        scope_access: null,
        denied_reason: null,
      },
    ]),
  );
}

export function permissionAllows(permission: EffectivePermission | undefined): boolean {
  return Boolean(permission?.allowed);
}

export function permissionSuggests(permission: EffectivePermission | undefined): boolean {
  return Boolean(permission?.suggestion_allowed);
}

export function permissionSummaryLabel(permission: EffectivePermission): string {
  if (permission.allowed) {
    return "Allow";
  }
  if (permission.suggestion_allowed) {
    return "Suggest";
  }
  return "Deny";
}
