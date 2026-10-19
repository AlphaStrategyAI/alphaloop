import {localizeError, type ErrorInput} from "./errors";
import {useI18n} from "./I18nProvider";
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

export function EngineFailureText({raw}: {raw: string}) {
  const {resolved, t} = useI18n();
  const localized = localizeError(resolved, parseEngineFailure(raw));
  return (
    <span className="engine-failure" data-testid="engine-failure">
      <span data-testid="engine-failure-summary">{localized.summary}</span>
      {localized.next ? <span> {localized.next}</span> : null}
      {localized.detail ? (
        <details>
          <summary>{t("glossary.technicalDetails")}</summary>
          <pre data-testid="engine-failure-detail">{localized.detail}</pre>
        </details>
      ) : null}
    </span>
  );
}

export function DialogueTurnBody({turn}: {turn: DialogueTurnView}) {
  const {resolved, t} = useI18n();
  if (!turn.errorCode) {
    return (
      <p className={`message ${turn.role}`} data-testid="dialogue-turn">
        {turn.text}
      </p>
    );
  }
  const localized = localizeError(resolved, {
    code: turn.errorCode,
    params: turn.errorParams,
    detail: turn.errorDetail,
  });
  return (
    <div
      className={`message ${turn.role} error-notice`}
      data-testid="dialogue-turn"
      data-error-code={turn.errorCode}
    >
      <p data-testid="dialogue-error-summary">{localized.summary}</p>
      {localized.next ? <p>{localized.next}</p> : null}
      {localized.detail ? (
        <details>
          <summary>{t("glossary.technicalDetails")}</summary>
          <pre data-testid="dialogue-error-detail">{localized.detail}</pre>
        </details>
      ) : null}
    </div>
  );
}
