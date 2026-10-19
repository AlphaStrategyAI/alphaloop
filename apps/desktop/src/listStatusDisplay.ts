import type {ResearchListDisplayStatus} from "./contracts";

const BASE: Record<ResearchListDisplayStatus, string> = {
  draft: "草稿",
  running: "运行中",
  awaiting_confirm: "等待确认",
  paused: "已暂停",
  completed: "已完成",
  ended: "未通过",
  confirm_run: "确认开跑",
};

export function listRowStatusLabel(status: ResearchListDisplayStatus): string {
  return BASE[status];
}
