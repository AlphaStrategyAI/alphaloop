/**
 * Desktop ↔ Tauri binding for Settings → LLM.
 *
 * `set_llm_settings(base_url, model, privacy_acknowledged)` writes settings.json.
 * The API key is `secret_set` / `secret_delete` / `secret_is_set` with id `llm-api-key`.
 * The key is not a field of `set_llm_settings`.
 */

export const LLM_SETTINGS_LOAD_COMMAND = "get_llm_settings";
export const LLM_SETTINGS_SAVE_COMMAND = "set_llm_settings";
export const LLM_API_KEY_SECRET_ID = "llm-api-key";

export type LlmSettingsSnapshot = {
  baseUrl: string;
  model: string;
  privacyAcknowledged: boolean;
  local: boolean;
};

export type LlmSettingsSaveInput = {
  baseUrl: string;
  model: string;
  privacyAcknowledged: boolean;
};

/** Arguments for the Tauri `set_llm_settings` command. Camel case matches the invoke bridge. */
export function setLlmSettingsInvokeArgs(input: LlmSettingsSaveInput) {
  return {
    baseUrl: input.baseUrl.trim(),
    model: input.model.trim(),
    privacyAcknowledged: input.privacyAcknowledged,
  };
}

/** Arguments for `secret_set` / `secret_delete` / `secret_is_set`. */
export function llmApiKeyInvokeArgs(value?: string) {
  return value === undefined
    ? {id: LLM_API_KEY_SECRET_ID}
    : {id: LLM_API_KEY_SECRET_ID, value};
}

export function isLoopbackBaseUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return false;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return false;
  const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (host === "localhost" || host === "::1") return true;
  const parts = host.split(".");
  if (parts.length !== 4 || parts[0] !== "127") return false;
  return parts.every((part) => /^\d+$/.test(part) && Number(part) <= 255);
}

/** Host written into the implementation-change sentence. Empty input uses the frame example. */
export function llmHostLabel(baseUrl: string): string {
  const trimmed = baseUrl.trim();
  if (!trimmed) return "api.openai.com";
  try {
    const url = new URL(trimmed);
    if (!url.hostname) return "api.openai.com";
    const host = url.hostname.replace(/^\[|\]$/g, "");
    return url.port ? `${host}:${url.port}` : host;
  } catch {
    return "api.openai.com";
  }
}

export function llmRecordLabel(baseUrl: string, model: string): string {
  const name = model.trim() || "gpt-4.1";
  return `${name} @ ${llmHostLabel(baseUrl)}`;
}

export function baseUrlIsAcceptable(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 500) return false;
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return false;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return false;
  if (!url.hostname) return false;
  if (url.username || url.password || url.search) return false;
  return true;
}
