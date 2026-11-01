import {describe, expect, it} from "vitest";

import {
  beginCreateGesture,
  holdCommand,
  revisionAfterSourceWrite,
  revisionFromSourceWrite,
  sendHeldDialogue,
} from "./commandGesture";
import {confirmRunEnginePayload} from "./confirmRunCommand";
import {sendDialogueEnginePayload} from "./dialogueCommand";

describe("command gesture", () => {
  it("reuses one command id until the payload or revision changes", () => {
    const first = holdCommand(null, 3, "继续");
    const retry = holdCommand(first, 3, "继续");
    expect(retry.commandId).toBe(first.commandId);
    const edited = holdCommand(retry, 3, "改口");
    expect(edited.commandId).not.toBe(first.commandId);
    const bumped = holdCommand(edited, 4, "改口");
    expect(bumped.commandId).not.toBe(edited.commandId);
  });

  it("keeps the preallocated create ids across a lost response", () => {
    const first = beginCreateGesture(null);
    const retry = beginCreateGesture(first);
    expect(retry).toEqual(first);
    expect(retry.researchId).not.toBe(retry.commandId);
  });

  it("omits the envelope for a legacy confirm and threads it when the gesture has one", () => {
    expect(confirmRunEnginePayload("r-1")).toEqual({
      type: "confirm_run",
      research_id: "r-1",
    });
    expect(confirmRunEnginePayload("r-1", {
      dataSourceId: "yahoo_daily",
      unlicensedAcknowledged: true,
      command: {commandId: "c-1", expectedRevision: 4, replyTo: "p-1", authorizeRebill: true},
    })).toEqual({
      type: "confirm_run",
      research_id: "r-1",
      data_source_id: "yahoo_daily",
      unlicensed_acknowledged: true,
      command_id: "c-1",
      expected_revision: 4,
      reply_to: "p-1",
      authorize_rebill: true,
    });
  });

  it("keeps a dialogue retry on the same id and sends the envelope only for a revisioned view", async () => {
    expect(sendDialogueEnginePayload("r-1", "继续")).toEqual({
      type: "send_dialogue",
      research_id: "r-1",
      message: "继续",
    });
    const sent: ReturnType<typeof sendDialogueEnginePayload>[] = [];
    const held: {current: {commandId: string; expectedRevision: number; payloadKey: string} | null} = {
      current: null,
    };
    let failed = false;
    const api = {
      async sendDialogue(
        researchId: string,
        message: string,
        envelope?: {commandId: string; expectedRevision: number},
      ) {
        if (envelope && !failed) {
          failed = true;
          throw new Error("timeout");
        }
        sent.push(sendDialogueEnginePayload(researchId, message, envelope));
      },
    };
    await sendHeldDialogue(api, held, "r-1", "继续", undefined);
    await expect(sendHeldDialogue(api, held, "r-1", "继续", 2)).rejects.toThrow("timeout");
    const retried = held.current?.commandId;
    await sendHeldDialogue(api, held, "r-1", "继续", 2);
    expect(sent[0]).toEqual({type: "send_dialogue", research_id: "r-1", message: "继续"});
    expect(sent[1]?.command_id).toBe(retried);
    expect(sent[1]?.expected_revision).toBe(2);
  });

  it("adopts the source-ack revision when the confirm card is still older", () => {
    expect(revisionFromSourceWrite(6)).toBe(6);
    expect(revisionFromSourceWrite(6.5)).toBeUndefined();
    expect(revisionFromSourceWrite(null)).toBeUndefined();
    expect(revisionAfterSourceWrite(4, 6)).toBe(6);
    expect(revisionAfterSourceWrite(7, 6)).toBe(7);
    expect(revisionAfterSourceWrite(4, undefined)).toBe(4);
    expect(revisionAfterSourceWrite(undefined, 6)).toBe(6);
  });
});
