import {describe, expect, it, vi} from "vitest";

import {createTauriDesktopApi, type DesktopInvoke} from "./desktopApi";
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

  it("returns the revision from set_price_source so confirm can follow the ack", async () => {
    const invoke = vi.fn(async (_command: string, _args?: Record<string, unknown>) => 6 as number | null);
    const api = createTauriDesktopApi(invoke as unknown as DesktopInvoke);
    await expect(api.setPriceSource("r-1", "yahoo_daily", true)).resolves.toBe(6);
    expect(invoke).toHaveBeenCalledWith("set_price_source", {
      researchId: "r-1",
      dataSourceId: "yahoo_daily",
      unlicensedAcknowledged: true,
    });
    invoke.mockResolvedValueOnce(null);
    await expect(api.setPriceSource("r-1", "yahoo_daily")).resolves.toBeUndefined();
  });
});
