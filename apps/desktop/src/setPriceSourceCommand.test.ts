import {describe, expect, it} from "vitest";

import {setPriceSourceEnginePayload, setPriceSourceInvokeArgs} from "./setPriceSourceCommand";

describe("set_price_source bindings", () => {
  it("mirrors the invoke arguments in the engine payload", () => {
    const args = setPriceSourceInvokeArgs("r-1", "yahoo_daily", true);
    expect(args).toEqual({
      researchId: "r-1",
      dataSourceId: "yahoo_daily",
      unlicensedAcknowledged: true,
    });
    expect(setPriceSourceEnginePayload(args.researchId, args.dataSourceId, args.unlicensedAcknowledged)).toEqual({
      type: "set_price_source",
      research_id: "r-1",
      data_source_id: "yahoo_daily",
      unlicensed_acknowledged: true,
    });
  });

  it("omits the acknowledgement flag when the card only stores the source", () => {
    const args = setPriceSourceInvokeArgs("r-1", "yahoo_daily");
    expect(args.unlicensedAcknowledged).toBeUndefined();
    expect(setPriceSourceEnginePayload(args.researchId, args.dataSourceId)).toEqual({
      type: "set_price_source",
      research_id: "r-1",
      data_source_id: "yahoo_daily",
    });
  });

  it("keeps an empty id so the card can clear a choice", () => {
    expect(setPriceSourceEnginePayload("r-1", "")).toEqual({
      type: "set_price_source",
      research_id: "r-1",
      data_source_id: "",
    });
  });
});
