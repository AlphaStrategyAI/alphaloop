import type {DesktopView} from "./contracts";
import type {MessageKey} from "./i18n/I18nProvider";

export type RailStatusKey = MessageKey;

/** Short sidebar status key (设计小迪 Tech Pulse). */
export function railStatusKey(view: DesktopView): RailStatusKey | null {
  switch (view.kind) {
    case "confirm_run":
      return "ui.status.confirmRun";
    case "awaiting_confirm":
      return "ui.status.awaitingShort";
    case "running":
      return view.status === "paused" ? "ui.status.paused" : "ui.status.running";
    case "completed":
      return "ui.status.completed";
    case "research_list": {
      if (view.awaiting) return "ui.status.awaitingShort";
      if (view.rows.some((row) => row.status === "confirm_run")) return "ui.status.confirmRun";
      if (view.rows.some((row) => row.status === "running")) return "ui.status.running";
      if (view.rows.some((row) => row.status === "awaiting_confirm")) return "ui.status.awaitingShort";
      return null;
    }
    default:
      return null;
  }
}
