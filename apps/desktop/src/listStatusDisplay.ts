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
