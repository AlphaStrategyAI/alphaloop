import {useCallback, useEffect, useMemo, useRef, useState} from "react";

import {bindDesktopApi} from "./api-bind";
import type {DesktopApi, DesktopView, SidecarUiState} from "./contracts";
import {EngineFailureText} from "./i18n/engineFailure";
import {useI18n} from "./i18n/I18nProvider";
import {readBrowserRoute, viewMatchesRoute} from "./routing";
import {SettingsPage} from "./settings/SettingsPage";
import "./night.css";
import "./tech-pulse.css";
import {useRunStartRitual} from "./useRunStartRitual";
import {AwaitingConfirmCard} from "./screens/AwaitingConfirmScreen";
import {CompletedScreen} from "./screens/CompletedScreen";
import {ConfirmRunCard, ConfirmRunScreen, DraftScreen} from "./screens/ConfirmRunScreen";
import {GlossaryScreen} from "./screens/GlossaryScreen";
import {MethodDetail, MethodsScreen} from "./screens/MethodsScreen";
import {ResearchList} from "./screens/ResearchListScreen";
import {RouteLoading} from "./screens/RouteLoading";
import {RunningScreen} from "./screens/RunningScreen";
import {isSettingsRoute, NightShell, routeFailureMessage} from "./screens/shell";
import {routeFor} from "./screens/routes";

export {AwaitingConfirmCard, ConfirmRunCard, ConfirmRunScreen, MethodDetail, routeFor};

export interface AppProps {
  api: DesktopApi;
  initialView: DesktopView;
  /** Hash route for first paint; defaults to browser location. */
  initialRoute?: string;
  /** Test hook: poll Tauri sidecar supervision state. */
  pollSidecar?: () => Promise<SidecarUiState | null>;
  /** Test hook: manual engine restart from the shell. */
  restartSidecar?: () => Promise<void>;
}

type ScreenProps = AppProps & {
  pausedModificationByResearch: Record<string, string>;
  onPausedModificationChange: (researchId: string, text: string) => void;
};

function Screen({
  api,
  initialView: view,
  pausedModificationByResearch,
  onPausedModificationChange,
  runStartRitual,
}: ScreenProps & {runStartRitual?: boolean}) {
  switch (view.kind) {
    case "research_list": return <ResearchList api={api} view={view} />;
    case "draft": return <DraftScreen api={api} view={view} />;
    case "confirm_run": return <ConfirmRunScreen api={api} view={view} />;
    case "running":
      return (
        <RunningScreen
          api={api}
          view={view}
          modification={pausedModificationByResearch[view.researchId] ?? ""}
          onModificationChange={(text) => onPausedModificationChange(view.researchId, text)}
          runStartRitual={runStartRitual}
        />
      );
    case "awaiting_confirm": return <div className="focus"><AwaitingConfirmCard api={api} view={view} /></div>;
    case "completed": return <CompletedScreen api={api} view={view} />;
    case "methods": return <MethodsScreen api={api} view={view} />;
    case "glossary": return <GlossaryScreen view={view} />;
  }
}

export function App({
  api,
  initialView,
  initialRoute,
  pollSidecar,
  restartSidecar,
}: AppProps) {
  const {t} = useI18n();
  const [route, setRoute] = useState(() => initialRoute ?? readBrowserRoute());
  const [view, setView] = useState(initialView);
  const [syncedRoute, setSyncedRoute] = useState(() => initialRoute ?? readBrowserRoute());
  const routeGeneration = useRef(0);
  const seenRoute = useRef(route);
  if (seenRoute.current !== route) {
    seenRoute.current = route;
    routeGeneration.current += 1;
  }
  const [routeError, setRouteError] = useState<string | null>(null);
  const [failedRoute, setFailedRoute] = useState<string | null>(null);
  const [routeRetry, setRouteRetry] = useState(0);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [sidecarState, setSidecarState] = useState<SidecarUiState | null>(null);
  const [pausedModificationByResearch, setPausedModificationByResearch] = useState<
    Record<string, string>
  >({});
  const onPausedModificationChange = useCallback((researchId: string, text: string) => {
    setPausedModificationByResearch((prev) => ({...prev, [researchId]: text}));
  }, []);
  const engineStopped = sidecarState?.phase === "stopped";
  const settingsRoute = isSettingsRoute(route);
  const routeFailed = !settingsRoute && failedRoute === route && routeError !== null;
  const routePending = !settingsRoute && route !== syncedRoute && !routeFailed;
  const runStartRitual = useRunStartRitual(view);

  const refreshView = useCallback(async () => {
    const generation = routeGeneration.current;
    const requestedRoute = route;
    if (isSettingsRoute(requestedRoute)) return;
    const next = await api.fetchView(requestedRoute);
    if (generation !== routeGeneration.current) return;
    if (!viewMatchesRoute(next, requestedRoute)) return;
    setView(next);
    setSyncedRoute(requestedRoute);
    setRouteError(null);
    setFailedRoute((current) => (current === requestedRoute ? null : current));
  }, [api, route]);

  const clearMutationError = useCallback(() => setMutationError(null), []);

  const boundApi = useMemo(
    () =>
      bindDesktopApi(api, {
        refresh: refreshView,
        onError: setMutationError,
        onSuccess: clearMutationError,
      }),
    [api, refreshView, clearMutationError],
  );

  useEffect(() => {
    clearMutationError();
  }, [route, clearMutationError]);

  useEffect(() => {
    if (!mutationError) return;
    if (/MARKET_DATA_|DATA_SOURCE_UNAVAILABLE/.test(mutationError)) return;
    const timer = window.setTimeout(() => clearMutationError(), 12_000);
    return () => window.clearTimeout(timer);
  }, [mutationError, clearMutationError]);

  useEffect(() => {
    const onHashChange = () => setRoute(readBrowserRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (!pollSidecar) return;
    let active = true;
    const tick = () => {
      void pollSidecar()
        .then((next) => {
          if (active) setSidecarState(next);
        })
        .catch(() => {
          /* sidecar state poll failed; keep last UI state */
        });
    };
    tick();
    const timer = window.setInterval(tick, 2_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [pollSidecar]);

  useEffect(() => {
    if (engineStopped || !api.pollMarketDataProgress) return;
    let active = true;
    const tick = () => {
      void api.pollMarketDataProgress?.()
        .then((next) => {
          if (!active || !next) return;
          setView((current) => ({
            ...current,
            marketDataProgress: next.marketDataProgress,
            hostStatus: next.hostStatus ?? current.hostStatus,
          }));
        })
        .catch(() => {
          /* progress poll failed; the route poll can still refresh */
        });
    };
    tick();
    const timer = window.setInterval(tick, 400);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, engineStopped]);

  useEffect(() => {
    if (isSettingsRoute(route)) return;
    if (engineStopped) return;
    let active = true;
    const generation = routeGeneration.current;
    const requestedRoute = route;
    const refresh = () => {
      void api
        .fetchView(requestedRoute)
        .then((next) => {
          if (!active || generation !== routeGeneration.current) return;
          if (!viewMatchesRoute(next, requestedRoute)) return;
          setView(next);
          setSyncedRoute(requestedRoute);
          setRouteError(null);
          setFailedRoute((current) => (current === requestedRoute ? null : current));
        })
        .catch((error: unknown) => {
          if (!active || generation !== routeGeneration.current) return;
          setRouteError(routeFailureMessage(error, t));
          setFailedRoute(requestedRoute);
        });
    };
    refresh();
    const timer = window.setInterval(refresh, 1_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, route, engineStopped, routeRetry]);

  const handleRestartSidecar = useCallback(async () => {
    if (!restartSidecar) return;
    try {
      await restartSidecar();
      if (pollSidecar) {
        const next = await pollSidecar();
        setSidecarState(next);
      }
    } catch {
      /* restart failed; banner stays until user retries */
    }
  }, [restartSidecar, pollSidecar]);

  return (
    <NightShell view={view} route={route} sidecarState={sidecarState} runStartRitual={runStartRitual}>
      {mutationError && (
        <p className="mutation-error" data-testid="mutation-error" role="alert">
          <EngineFailureText raw={mutationError} />
          <button
            type="button"
            className="mutation-error-dismiss"
            aria-label={t("ui.shell.close")}
            data-testid="mutation-error-dismiss"
            onClick={clearMutationError}
          >
            ×
          </button>
        </p>
      )}
      {sidecarState?.phase === "stopped" && (
        <div className="sidecar-stopped" data-testid="sidecar-stopped" role="alert">
          <p>{sidecarState.message || t("ui.shell.engineStopped")}</p>
          {restartSidecar && (
            <button type="button" onClick={() => void handleRestartSidecar()}>
              {t("ui.shell.restart")}
            </button>
          )}
        </div>
      )}
      {settingsRoute ? (
        <SettingsPage route={route} />
      ) : routePending ? (
        <RouteLoading route={route} />
      ) : routeFailed ? (
        <div className="route-error" data-testid="route-error" role="alert">
          <p><EngineFailureText raw={routeError ?? ""} /></p>
          <button
            type="button"
            className="quiet-button"
            data-testid="route-retry"
            onClick={() => {
              setFailedRoute(null);
              setRouteRetry((count) => count + 1);
            }}
          >
            {t("ui.shell.retry")}
          </button>
        </div>
      ) : (
        <Screen
          api={boundApi}
          initialView={view}
          pausedModificationByResearch={pausedModificationByResearch}
          onPausedModificationChange={onPausedModificationChange}
          runStartRitual={runStartRitual}
        />
      )}
    </NightShell>
  );
}
