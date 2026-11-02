import type {DesktopApi, ExportKind} from "./contracts";
import {matchRuntimeUtterance} from "./i18n/runtimeCommandUtterances";

export type RuntimeCommand =
  | {type: "pause"}
  | {type: "resume"}
  | {type: "reverify"}
  | {type: "export_artifact"; kind: ExportKind}
  | {type: "continue_iterate"}
  | {type: "send_dialogue"; message: string};

/** Free text and the original buttons name the same command. */
export function commandForUtterance(text: string): RuntimeCommand {
  return matchRuntimeUtterance(text) ?? {type: "send_dialogue", message: text.trim()};
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
