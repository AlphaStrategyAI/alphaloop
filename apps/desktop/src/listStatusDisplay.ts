import type {ResearchListDisplayStatus} from "./contracts";
import type {MessageKey} from "./i18n/I18nProvider";

const BASE: Record<ResearchListDisplayStatus, MessageKey> = {
  draft: "ui.status.draft",
  running: "ui.status.running",
  awaiting_confirm: "ui.status.awaiting",
  paused: "ui.status.paused",
  completed: "ui.status.completed",
  ended: "ui.status.endedShort",
  confirm_run: "ui.status.confirmRun",
};

export function listRowStatusKey(status: ResearchListDisplayStatus): MessageKey {
  return BASE[status];
}

/** List chips from frame 17. Pending covers both confirm surfaces. */
export type ResearchListFilter = "all" | "pending" | "running" | "paused" | "done" | "draft";

export const RESEARCH_LIST_FILTERS: readonly ResearchListFilter[] = [
  "all",
  "pending",
  "running",
  "paused",
  "done",
  "draft",
];

export function researchListFilterKey(filter: ResearchListFilter): MessageKey {
  switch (filter) {
    case "all":
      return "ui.list.filterAll";
    case "pending":
      return "ui.list.filterPending";
    case "running":
      return "ui.list.filterRunning";
    case "paused":
      return "ui.list.filterPaused";
    case "done":
      return "ui.list.filterDone";
    case "draft":
      return "ui.list.filterDraft";
  }
}

export function matchesResearchListFilter(
  status: ResearchListDisplayStatus,
  filter: ResearchListFilter,
): boolean {
  switch (filter) {
    case "all":
      return true;
    case "pending":
      return status === "awaiting_confirm" || status === "confirm_run";
    case "done":
      return status === "completed" || status === "ended";
    case "running":
    case "paused":
    case "draft":
      return status === filter;
  }
}
