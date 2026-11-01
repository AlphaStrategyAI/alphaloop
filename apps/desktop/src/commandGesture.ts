import type {CommandEnvelope, DesktopApi} from "./contracts";

export type HeldCommand = {
  commandId: string;
  expectedRevision: number;
  payloadKey: string;
};

export type CreateGesture = {
  researchId: string;
  commandId: string;
};

export function allocateCommandId(): string {
  return crypto.randomUUID();
}

export function allocateResearchId(): string {
  return crypto.randomUUID();
}

/** One user gesture. A retry of the same payload keeps the id; a new payload or revision allocates another. */
export function holdCommand(
  current: HeldCommand | null,
  expectedRevision: number,
  payloadKey: string,
): HeldCommand {
  if (
    current
    && current.payloadKey === payloadKey
    && current.expectedRevision === expectedRevision
  ) {
    return current;
  }
  return {
    commandId: allocateCommandId(),
    expectedRevision,
    payloadKey,
  };
}

export function beginCreateGesture(current: CreateGesture | null): CreateGesture {
  if (current) return current;
  return {researchId: allocateResearchId(), commandId: allocateCommandId()};
}

export function isRevisionConflict(error: unknown): boolean {
  const text = error instanceof Error ? error.message : String(error);
  return text.includes("REVISION_CONFLICT");
}

/** Integer revision from a `set_price_source` result. Anything else is ignored. */
export function revisionFromSourceWrite(result: unknown): number | undefined {
  if (typeof result !== "number" || !Number.isInteger(result) || result < 0) return undefined;
  return result;
}

/**
 * The source acknowledgement is its own write and bumps the research revision.
 * Confirm has to expect that revision when the card is still showing the older one.
 * A newer card revision is the research currently on screen, so it wins.
 */
export function revisionAfterSourceWrite(
  viewRevision: number | undefined,
  sourceRevision: number | undefined,
): number | undefined {
  if (typeof viewRevision === "number" && typeof sourceRevision === "number") {
    return Math.max(viewRevision, sourceRevision);
  }
  if (typeof sourceRevision === "number") return sourceRevision;
  return viewRevision;
}

export async function sendHeldDialogue(
  api: Pick<DesktopApi, "sendDialogue">,
  held: {current: HeldCommand | null},
  researchId: string,
  message: string,
  revision: number | undefined,
  replyTo?: string,
): Promise<void> {
  if (typeof revision !== "number") {
    await api.sendDialogue(researchId, message);
    return;
  }
  const next = holdCommand(held.current, revision, `${replyTo ?? ""}\n${message}`);
  held.current = next;
  const envelope: CommandEnvelope = {
    commandId: next.commandId,
    expectedRevision: next.expectedRevision,
  };
  if (replyTo) envelope.replyTo = replyTo;
  try {
    await api.sendDialogue(researchId, message, envelope);
    held.current = null;
  } catch (error) {
    if (isRevisionConflict(error)) held.current = null;
    throw error;
  }
}
