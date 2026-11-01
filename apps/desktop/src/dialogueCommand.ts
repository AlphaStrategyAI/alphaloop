import type {CommandEnvelope} from "./contracts";

/** JSON body the engine receives for a dialogue reply. Mirrors the Tauri command. */

export function sendDialogueEnginePayload(
  researchId: string,
  message: string,
  envelope?: CommandEnvelope,
) {
  const body: {
    type: "send_dialogue";
    research_id: string;
    message: string;
    command_id?: string;
    expected_revision?: number;
    reply_to?: string;
  } = {
    type: "send_dialogue",
    research_id: researchId,
    message,
  };
  if (envelope) {
    body.command_id = envelope.commandId;
    body.expected_revision = envelope.expectedRevision;
    if (envelope.replyTo) body.reply_to = envelope.replyTo;
  }
  return body;
}
