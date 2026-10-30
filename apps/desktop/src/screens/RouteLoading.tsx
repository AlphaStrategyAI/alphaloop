import {useI18n} from "../i18n/I18nProvider";

function skeletonKind(route: string): "detail" | "list" {
  if (route.startsWith("#/research/") || route.startsWith("#/methods/")) return "detail";
  return "list";
}

/** Glass skeletons for list and detail routes while a view is in flight. */
export function RouteLoading({route}: {route: string}) {
  const {t} = useI18n();
  const kind = skeletonKind(route);
  return (
    <div className="route-loading" data-testid="route-loading" data-skeleton={kind} role="status" aria-live="polite">
      <p className="route-loading-label">{t("ui.shell.loading")}</p>
      <div className="skeleton-stack" data-pulse="1.2s" aria-hidden="true">
        {kind === "detail" ? (
          <>
            <span className="skeleton-bar skeleton-bar--title" />
            <span className="skeleton-bar skeleton-bar--wide" />
            <span className="skeleton-bar" />
            <span className="skeleton-bar skeleton-bar--card" />
          </>
        ) : (
          <>
            <span className="skeleton-bar skeleton-bar--title" />
            <span className="skeleton-bar skeleton-bar--row" />
            <span className="skeleton-bar skeleton-bar--row" />
            <span className="skeleton-bar skeleton-bar--row" />
          </>
        )}
      </div>
    </div>
  );
}
