import {localizeError, type ErrorInput} from "./errors";
import {useI18n} from "./I18nProvider";
import {localizeKnownCopy} from "./productCopy";
import type {DialogueTurnView} from "../contracts";

export function parseEngineFailure(raw: string): ErrorInput {
  try {
    const parsed = JSON.parse(raw) as {
      error?: unknown;
      code?: unknown;
      params?: ErrorInput["params"];
      detail?: unknown;
    };
    if (parsed && typeof parsed === "object" && typeof parsed.code === "string" && parsed.code) {
      return {
        code: parsed.code,
        message: typeof parsed.error === "string" ? parsed.error : "",
        params: parsed.params ?? undefined,
        detail: typeof parsed.detail === "string" ? parsed.detail : null,
      };
    }
  } catch {
    /* plain engine string */
  }
  return {message: raw};
}

function technicalText(
  detail: string | null,
  params?: Record<string, string | number> | null,
): string {
  const lines: string[] = [];
  if (detail && detail.trim()) lines.push(detail.trim());
  const entries = Object.entries(params ?? {}).filter(([, value]) => value !== undefined && value !== "");
  if (entries.length) {
    lines.push(entries.map(([key, value]) => `${key}: ${value}`).join("\n"));
  }
  return lines.join("\n");
}

export function EngineFailureText({raw}: {raw: string}) {
  const {resolved, t} = useI18n();
  const parsed = parseEngineFailure(raw);
  const localized = localizeError(resolved, parsed);
  const technical = technicalText(localized.detail, parsed.params);
  return (
    <span className="engine-failure" data-testid="engine-failure">
      <span data-testid="engine-failure-summary">{localized.summary}</span>
      {localized.next ? <span> {localized.next}</span> : null}
      {technical ? (
        <details>
          <summary>{t("glossary.technicalDetails")}</summary>
          <pre data-testid="engine-failure-detail">{technical}</pre>
        </details>
      ) : null}
    </span>
  );
}

export function DialogueTurnBody({turn}: {turn: DialogueTurnView}) {
  const {resolved, t} = useI18n();
  if (!turn.errorCode) {
    const text = turn.role === "assistant" ? localizeKnownCopy(turn.text, t) : turn.text;
    return (
      <p className={`message ${turn.role}`} data-testid="dialogue-turn">
        {text}
      </p>
    );
  }
  const localized = localizeError(resolved, {
    code: turn.errorCode,
    params: turn.errorParams,
    detail: turn.errorDetail,
  });
  const technical = technicalText(localized.detail, turn.errorParams);
  return (
    <div
      className={`message ${turn.role} error-notice`}
      data-testid="dialogue-turn"
      data-error-code={turn.errorCode}
    >
      <p data-testid="dialogue-error-summary">{localized.summary}</p>
      {localized.next ? <p>{localized.next}</p> : null}
      {technical ? (
        <details>
          <summary>{t("glossary.technicalDetails")}</summary>
          <pre data-testid="dialogue-error-detail">{technical}</pre>
        </details>
      ) : null}
    </div>
  );
}
