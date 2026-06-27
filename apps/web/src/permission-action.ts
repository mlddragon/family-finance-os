/**
 * Standard permission-gated mutation affordances for operator UI buttons.
 *
 * Pair with global `button:disabled` styles in styles.css:
 * disabled actions stay grey, non-interactive, and do not highlight on hover.
 */
export type PermissionActionState = {
  allowed: boolean;
  disabledTitle: string | undefined;
  blockedNotice: string | null;
};

export function reviewDecideActionState(
  canReviewDecide: boolean,
  elevatedModeActive: boolean,
  labels: {
    denied: string;
    elevated: string;
  },
): PermissionActionState {
  if (elevatedModeActive) {
    return {
      allowed: false,
      disabledTitle: labels.elevated,
      blockedNotice: labels.elevated,
    };
  }
  if (!canReviewDecide) {
    return {
      allowed: false,
      disabledTitle: labels.denied,
      blockedNotice: labels.denied,
    };
  }
  return {
    allowed: true,
    disabledTitle: undefined,
    blockedNotice: null,
  };
}
