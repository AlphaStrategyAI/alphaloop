import {localizeError} from "./errors";
import {useI18n} from "./I18nProvider";
import "../settings/settings.css";

export function LocalizedRunError({
  error,
}: {
  error: {
    message: string;
    count: number;
    code?: string;
    params?: Record<string, string | number>;
    detail?: string | null;
  };
}) {
  const {resolved, t} = useI18n();
  if (!error.code) {
    return (
      <p className="run-error" data-testid="last-run-error">
        运行错误（{error.count} 次）：{error.message}
      </p>
    );
  }
  const localized = localizeError(resolved, error);
  return (
    <div className="run-error error-notice" data-testid="last-run-error" data-unmapped={localized.unmapped ? "true" : "false"}>
      <p data-testid="last-run-error-summary">{localized.summary}</p>
      {localized.next ? <p>{localized.next}</p> : null}
      {localized.detail ? (
        <details>
          <summary>{t("glossary.technicalDetails")}</summary>
          <pre data-testid="last-run-error-detail">{localized.detail}</pre>
        </details>
      ) : null}
    </div>
  );
}
