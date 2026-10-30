import type {DesktopView} from "./contracts";
import {completedShowsFailedTone} from "./completedFailedTone";
import type {MessageKey} from "./i18n/I18nProvider";

export type RailStatusKey = MessageKey;

/** Research-detail rail tones from frames 19/20/21: run / hold / ok|stop. */
export type RailTone = "run" | "hold" | "ok" | "stop";

/** Short sidebar status key (设计小迪 Tech Pulse). */
export function railStatusKey(view: DesktopView): RailStatusKey | null {
  switch (view.kind) {
    case "confirm_run":
      return "ui.status.confirmRun";
    case "awaiting_confirm":
      return "ui.status.awaitingShort";
    case "running":
      return view.status === "paused" ? "ui.status.railHold" : "ui.status.railRun";
    case "completed":
      return completedShowsFailedTone(view) ? "ui.status.railStop" : "ui.status.railOk";
    case "research_list": {
      if (view.awaiting) return "ui.status.awaitingShort";
      if (view.rows.some((row) => row.status === "confirm_run")) return "ui.status.confirmRun";
      if (view.rows.some((row) => row.status === "running")) return "ui.status.railRun";
      if (view.rows.some((row) => row.status === "paused")) return "ui.status.railHold";
      if (view.rows.some((row) => row.status === "awaiting_confirm")) return "ui.status.awaitingShort";
      if (view.rows.some((row) => row.status === "ended")) return "ui.status.railStop";
      if (view.rows.some((row) => row.status === "completed")) return "ui.status.railOk";
      return null;
    }
    default:
      return null;
  }
}

export function railStatusTone(key: RailStatusKey | null): RailTone | null {
  switch (key) {
    case "ui.status.railRun":
      return "run";
    case "ui.status.railHold":
      return "hold";
    case "ui.status.railOk":
      return "ok";
    case "ui.status.railStop":
      return "stop";
    default:
      return null;
  }
}
