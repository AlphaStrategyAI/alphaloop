import {invoke} from "@tauri-apps/api/core";

import {
  DIALOGUE_ROLLOUT_LOAD_COMMAND,
  DIALOGUE_ROLLOUT_SAVE_COMMAND,
  DISABLED_DIALOGUE_ROLLOUT,
  type DialogueRolloutSnapshot,
} from "./dialogueRolloutCommand";

export interface DialogueRolloutPort {
  load(): Promise<DialogueRolloutSnapshot>;
  save(enabled: boolean): Promise<DialogueRolloutSnapshot>;
}

export const tauriDialogueRolloutPort: DialogueRolloutPort = {
  async load() {
    try {
      return await invoke<DialogueRolloutSnapshot>(DIALOGUE_ROLLOUT_LOAD_COMMAND);
    } catch {
      return DISABLED_DIALOGUE_ROLLOUT;
    }
  },
  save: (enabled) =>
    invoke<DialogueRolloutSnapshot>(DIALOGUE_ROLLOUT_SAVE_COMMAND, {enabled}),
};

export function createMemoryDialogueRolloutPort(
  initial?: Partial<DialogueRolloutSnapshot>,
): {port: DialogueRolloutPort; state: {snapshot: DialogueRolloutSnapshot; saves: boolean[]}} {
  const state = {
    snapshot: {...DISABLED_DIALOGUE_ROLLOUT, ...initial},
    saves: [] as boolean[],
  };
  const port: DialogueRolloutPort = {
    async load() {
      return state.snapshot;
    },
    async save(enabled) {
      state.saves.push(enabled);
      state.snapshot = {...state.snapshot, enabled};
      return state.snapshot;
    },
  };
  return {port, state};
}
