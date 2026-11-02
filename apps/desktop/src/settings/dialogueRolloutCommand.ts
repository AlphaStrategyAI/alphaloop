/**
 * Settings → General → dialogue-driven research.
 *
 * The boolean lives in settings.json. The write gate is a sidecar file the
 * engine publishes next to the database. Packages leave the boolean off.
 */

export const DIALOGUE_ROLLOUT_LOAD_COMMAND = "get_dialogue_rollout";
export const DIALOGUE_ROLLOUT_SAVE_COMMAND = "set_dialogue_rollout";
export const DIALOGUE_ROLLOUT_SETTINGS_KEY = "dialogueDrivenResearchEnabled";

export type DialogueRolloutSnapshot = {
  enabled: boolean;
  gateClosed: boolean;
  gateReason: string;
  gateDetail: string;
};

export const DISABLED_DIALOGUE_ROLLOUT: DialogueRolloutSnapshot = {
  enabled: false,
  gateClosed: false,
  gateReason: "",
  gateDetail: "",
};
