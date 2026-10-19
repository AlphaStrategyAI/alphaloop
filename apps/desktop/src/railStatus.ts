import type {DesktopView} from "./contracts";

/** Short sidebar status copy (设计小迪 Tech Pulse). */
export function railStatusLabel(view: DesktopView): string | null {
  switch (view.kind) {
    case "confirm_run":
      return "确认开跑";
    case "awaiting_confirm":
      return "等确认";
    case "running":
      return view.status === "paused" ? "已暂停" : "运行中";
    case "completed":
      return "已完成";
    case "research_list": {
      if (view.awaiting) {
        return "等确认";
      }
      if (view.rows.some((row) => row.status === "confirm_run")) {
        return "确认开跑";
      }
      if (view.rows.some((row) => row.status === "running")) {
        return "运行中";
      }
      if (view.rows.some((row) => row.status === "awaiting_confirm")) {
        return "等确认";
      }
      return null;
    }
    default:
      return null;
  }
}
