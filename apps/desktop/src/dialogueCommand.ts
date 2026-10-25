/** JSON body the engine receives for a dialogue reply. Mirrors the Tauri command. */

export function sendDialogueEnginePayload(researchId: string, message: string) {
  return {
    type: "send_dialogue" as const,
    research_id: researchId,
    message,
  };
}
