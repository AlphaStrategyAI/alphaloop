import {useEffect} from "react";

export interface InAppConfirmRequest {
  title: string;
  body: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
}

export function InAppConfirmOverlay({
  request,
  onClose,
}: {
  request: InAppConfirmRequest | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!request) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [request, onClose]);

  if (!request) return null;

  return (
    <div className="in-app-confirm-backdrop" data-testid="in-app-confirm">
      <div className="in-app-confirm-card" role="dialog" aria-modal="true" aria-labelledby="in-app-confirm-title">
        <h2 id="in-app-confirm-title">{request.title}</h2>
        <p className="in-app-confirm-body">{request.body}</p>
        <div className="in-app-confirm-actions">
          <button type="button" onClick={onClose}>
            {request.cancelLabel ?? "取消"}
          </button>
          <button
            type="button"
            className="cyan-button"
            onClick={() => request.onConfirm()}
          >
            {request.confirmLabel ?? "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}
