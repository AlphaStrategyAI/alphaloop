import type {CommandEnvelope} from "./contracts";

/** Arguments the desktop passes to the Tauri `confirm_run` command. */

export type ConfirmRunOptions = {
  dataSourceId?: string;
  unlicensedAcknowledged?: boolean;
  command?: CommandEnvelope;
};

export function confirmRunInvokeArgs(researchId: string, options?: ConfirmRunOptions) {
  const args: {
    researchId: string;
    dataSourceId?: string;
    unlicensedAcknowledged?: boolean;
    commandId?: string;
    expectedRevision?: number;
    replyTo?: string;
    authorizeRebill?: boolean;
  } = {
    researchId,
    dataSourceId: options?.dataSourceId,
    unlicensedAcknowledged: options?.unlicensedAcknowledged,
  };
  if (options?.command) {
    args.commandId = options.command.commandId;
    args.expectedRevision = options.command.expectedRevision;
    if (options.command.replyTo) args.replyTo = options.command.replyTo;
    if (typeof options.command.authorizeRebill === "boolean") {
      args.authorizeRebill = options.command.authorizeRebill;
    }
  }
  return args;
}

/** JSON body the engine receives. Mirrors the Tauri command's request object. */
export function confirmRunEnginePayload(researchId: string, options?: ConfirmRunOptions) {
  const args = confirmRunInvokeArgs(researchId, options);
  const body: {
    type: "confirm_run";
    research_id: string;
    data_source_id?: string;
    unlicensed_acknowledged?: boolean;
    command_id?: string;
    expected_revision?: number;
    reply_to?: string;
    authorize_rebill?: boolean;
  } = {
    type: "confirm_run",
    research_id: args.researchId,
  };
  if (args.dataSourceId) {
    body.data_source_id = args.dataSourceId;
  }
  if (typeof args.unlicensedAcknowledged === "boolean") {
    body.unlicensed_acknowledged = args.unlicensedAcknowledged;
  }
  if (args.commandId) {
    body.command_id = args.commandId;
    body.expected_revision = args.expectedRevision;
  }
  if (args.replyTo) body.reply_to = args.replyTo;
  if (typeof args.authorizeRebill === "boolean") body.authorize_rebill = args.authorizeRebill;
  return body;
}
