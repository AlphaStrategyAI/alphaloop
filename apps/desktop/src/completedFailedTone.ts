import type {DesktopView} from "./contracts";

/** Failed completed / gate-blocked presentation (coral export, red atmosphere). */
export function completedShowsFailedTone(
  view: Extract<DesktopView, {kind: "completed"}>,
): boolean {
  const eligible =
    view.eligibility.allMethodsPassed &&
    view.eligibility.noPendingConfirm &&
    view.eligibility.reverifiesPassed &&
    view.eligibility.pitExecutedAndPassed;
  return (
    view.status === "ended" ||
    view.exportKind === "research_record_only" ||
    !eligible
  );
}

export function viewContentFailedTone(view: DesktopView): boolean {
  return view.kind === "completed" && completedShowsFailedTone(view);
}
