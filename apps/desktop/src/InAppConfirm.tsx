import {useEffect, useRef} from "react";

import {useFocusTrap} from "./dialogFocus";
import {useI18n} from "./i18n/I18nProvider";

export interface InAppConfirmRequest {
  title: string;
  body: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Destructive confirms use a solid stop button. Enter does not activate it. */
  tone?: "danger" | "primary";
  onConfirm: () => void;
}

export function InAppConfirmOverlay({
  request,
  onClose,
}: {
  request: InAppConfirmRequest | null;
  onClose: () => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  useFocusTrap(request != null, cardRef);

  useEffect(() => {
    if (!request) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [request, onClose]);

  const {t} = useI18n();
  if (!request) return null;
  const danger = request.tone === "danger";

  return (
    <div
      className="in-app-confirm-backdrop"
      data-testid="in-app-confirm"
      data-dim="0.5"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={cardRef}
        className="in-app-confirm-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="in-app-confirm-title"
        onKeyDown={(event) => {
          if (!danger || event.key !== "Enter") return;
          const dangerButton = event.currentTarget.querySelector("[data-dialog-danger]");
          if (document.activeElement === dangerButton) {
            event.preventDefault();
            event.stopPropagation();
          }
        }}
      >
        <h2 id="in-app-confirm-title">{request.title}</h2>
        <p className="in-app-confirm-body">{request.body}</p>
        <div className="in-app-confirm-actions">
          <button type="button" data-dialog-cancel="" onClick={onClose}>
            {request.cancelLabel ?? t("ui.common.cancel")}
          </button>
          <button
            type="button"
            className={danger ? "danger-button" : "cyan-button"}
            data-testid="in-app-confirm-accept"
            data-dialog-danger={danger ? "" : undefined}
            onClick={() => request.onConfirm()}
          >
            {request.confirmLabel ?? t("ui.common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
