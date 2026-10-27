import {invoke} from "@tauri-apps/api/core";

import {
  LLM_SETTINGS_LOAD_COMMAND,
  LLM_SETTINGS_SAVE_COMMAND,
  llmApiKeyInvokeArgs,
  setLlmSettingsInvokeArgs,
  type LlmSettingsSaveInput,
  type LlmSettingsSnapshot,
} from "./llmSettingsCommand";

export interface LlmSettingsPort {
  load(): Promise<LlmSettingsSnapshot>;
  save(input: LlmSettingsSaveInput): Promise<LlmSettingsSnapshot>;
  apiKeyIsSet(): Promise<boolean>;
  setApiKey(value: string): Promise<void>;
  clearApiKey(): Promise<void>;
}

export const tauriLlmSettingsPort: LlmSettingsPort = {
  load: () => invoke<LlmSettingsSnapshot>(LLM_SETTINGS_LOAD_COMMAND),
  save: (input) =>
    invoke<LlmSettingsSnapshot>(LLM_SETTINGS_SAVE_COMMAND, setLlmSettingsInvokeArgs(input)),
  apiKeyIsSet: async () => Boolean(await invoke<boolean>("secret_is_set", llmApiKeyInvokeArgs())),
  setApiKey: async (value) => {
    await invoke("secret_set", llmApiKeyInvokeArgs(value));
  },
  clearApiKey: async () => {
    await invoke("secret_delete", llmApiKeyInvokeArgs());
  },
};

export type MemoryLlmState = {
  snapshot: LlmSettingsSnapshot;
  apiKey: string;
  saveCalls: LlmSettingsSaveInput[];
  secretSets: Array<{id: string; value: string}>;
  secretClears: Array<{id: string}>;
};

export function createMemoryLlmSettingsPort(
  initial?: Partial<LlmSettingsSnapshot> & {apiKey?: string},
): {port: LlmSettingsPort; state: MemoryLlmState} {
  const state: MemoryLlmState = {
    snapshot: {
      baseUrl: initial?.baseUrl ?? "",
      model: initial?.model ?? "",
      privacyAcknowledged: initial?.privacyAcknowledged ?? false,
      local: initial?.local ?? false,
    },
    apiKey: initial?.apiKey ?? "",
    saveCalls: [],
    secretSets: [],
    secretClears: [],
  };
  const port: LlmSettingsPort = {
    async load() {
      return state.snapshot;
    },
    async save(input) {
      const args = setLlmSettingsInvokeArgs(input);
      state.saveCalls.push(args);
      state.snapshot = {...state.snapshot, ...args};
      return state.snapshot;
    },
    async apiKeyIsSet() {
      return state.apiKey.length > 0;
    },
    async setApiKey(value) {
      const args = llmApiKeyInvokeArgs(value);
      state.secretSets.push({id: args.id, value: args.value ?? ""});
      state.apiKey = args.value ?? "";
    },
    async clearApiKey() {
      const args = llmApiKeyInvokeArgs();
      state.secretClears.push({id: args.id});
      state.apiKey = "";
    },
  };
  return {port, state};
}
