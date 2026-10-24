/** Arguments the desktop passes to the Tauri `confirm_run` command. */

export type ConfirmRunOptions = {
  dataSourceId?: string;
  unlicensedAcknowledged?: boolean;
};

export function confirmRunInvokeArgs(researchId: string, options?: ConfirmRunOptions) {
  return {
    researchId,
    dataSourceId: options?.dataSourceId,
    unlicensedAcknowledged: options?.unlicensedAcknowledged,
  };
}

/** JSON body the engine receives. Mirrors the Tauri command's request object. */
export function confirmRunEnginePayload(researchId: string, options?: ConfirmRunOptions) {
  const args = confirmRunInvokeArgs(researchId, options);
  const body: {
    type: "confirm_run";
    research_id: string;
    data_source_id?: string;
    unlicensed_acknowledged?: boolean;
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
  return body;
}
