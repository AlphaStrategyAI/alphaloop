import type {DesktopApi, ExportKind} from "./contracts";

export type RuntimeCommand =
  | {type: "pause"}
  | {type: "resume"}
  | {type: "reverify"}
  | {type: "export_artifact"; kind: ExportKind}
  | {type: "continue_iterate"}
  | {type: "send_dialogue"; message: string};

/** Free text and the original buttons name the same command. */
export function commandForUtterance(text: string): RuntimeCommand {
  const normalized = text.trim().toLowerCase();
  if (normalized === "暂停" || normalized === "pause") return {type: "pause"};
  if (normalized === "恢复" || normalized === "resume") return {type: "resume"};
  if (normalized === "重验" || normalized === "reverify") return {type: "reverify"};
  if (normalized === "导出策略包" || normalized === "export strategy pack") {
    return {type: "export_artifact", kind: "strategy_pack"};
  }
  if (normalized === "导出研究记录" || normalized === "export research record") {
    return {type: "export_artifact", kind: "research_record"};
  }
  if (normalized === "继续迭代" || normalized === "continue iterating") {
    return {type: "continue_iterate"};
  }
  return {type: "send_dialogue", message: text.trim()};
}

export async function dispatchRuntimeCommand(
  api: DesktopApi,
  researchId: string,
  command: RuntimeCommand,
  ctx: {
    roundId?: string;
    methodId?: string;
    highSuspicion?: boolean;
    revision?: number;
  } = {},
): Promise<void> {
  switch (command.type) {
    case "pause":
      await api.pauseResearch(researchId);
      return;
    case "resume":
      await api.resumeResearch(researchId);
      return;
    case "reverify":
      if (ctx.roundId && ctx.methodId) await api.reverify(researchId, ctx.roundId, ctx.methodId);
      return;
    case "export_artifact":
      await api.exportArtifact(researchId, command.kind);
      return;
    case "continue_iterate":
      await api.continueIterate(researchId, {
        userConfirmed: true,
        highSuspicionAcknowledged: ctx.highSuspicion ?? false,
      });
      return;
    case "send_dialogue":
      await api.sendDialogue(researchId, command.message);
  }
}
