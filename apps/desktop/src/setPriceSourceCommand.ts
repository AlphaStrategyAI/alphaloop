/** Arguments the desktop passes to the Tauri `set_price_source` command. */

export function setPriceSourceInvokeArgs(
  researchId: string,
  dataSourceId: string,
  unlicensedAcknowledged?: boolean,
) {
  return {researchId, dataSourceId, unlicensedAcknowledged};
}

/** JSON body the engine receives. Mirrors the Tauri command's request object. */
export function setPriceSourceEnginePayload(
  researchId: string,
  dataSourceId: string,
  unlicensedAcknowledged?: boolean,
) {
  const args = setPriceSourceInvokeArgs(researchId, dataSourceId, unlicensedAcknowledged);
  const body: {
    type: "set_price_source";
    research_id: string;
    data_source_id: string;
    unlicensed_acknowledged?: boolean;
  } = {
    type: "set_price_source",
    research_id: args.researchId,
    data_source_id: args.dataSourceId,
  };
  if (typeof args.unlicensedAcknowledged === "boolean") {
    body.unlicensed_acknowledged = args.unlicensedAcknowledged;
  }
  return body;
}
