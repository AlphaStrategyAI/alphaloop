import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {I18nText} from "../i18n/I18nText";
import {SecretVaultButton} from "../SecretVault";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import {MAIN_MIN_WIDTH, RAIL_WIDTH, shellHasAside} from "../layoutShell";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";

function RailIcon({name}: {name: "research" | "methods" | "glossary" | "settings" | "secrets"}) {
  const paths: Record<typeof name, string> = {
    research: "M4 20V6.5L12 3l8 3.5V20H4zm4-3h8",
    methods: "M6 4h9a3 3 0 0 1 3 3v13H8a2 2 0 0 1-2-2V4zm0 14h12",
    glossary: "M5 5h6a3 3 0 0 1 3 3v11H8a3 3 0 0 1-3-3V5zm14 0h-6a3 3 0 0 0-3 3v11h6a3 3 0 0 0 3-3V5z",
    settings: "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM4 12h2.2M17.8 12H20M12 4v2.2M12 17.8V20",
    secrets: "M8 11V8a4 4 0 1 1 8 0v3M7 11h10v8H7v-8z",
  };
  return (
    <svg className="rail-icon" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path d={paths[name]} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function engineStatusLabel(sidecar: SidecarUiState | null | undefined, t: Translate): string {
  if (!sidecar) return t("ui.shell.engineChecking");
  if (sidecar.phase === "stopped") return t("ui.shell.engineStopped");
  if (sidecar.phase === "restarting") return t("ui.shell.engineRestarting");
  return t("ui.shell.engineRunning");
}

export function isSettingsRoute(route: string): boolean {
  return route === "#/settings" || route.startsWith("#/settings/") || route.startsWith("#/settings?");
}

function railSection(route: string): "research" | "methods" | "glossary" | "settings" {
  if (route.startsWith("#/glossary")) return "glossary";
  if (route.startsWith("#/methods")) return "methods";
  if (isSettingsRoute(route)) return "settings";
  return "research";
}

export function routeFailureMessage(error: unknown, t: Translate): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  if (typeof error === "string" && error.trim()) return error;
  return t("ui.shell.routeFailed");
}

export function NightShell({
  view,
  route,
  children,
  sidecarState,
  runStartRitual,
}: {
  view: DesktopView;
  route: string;
  children: React.ReactNode;
  sidecarState?: SidecarUiState | null;
  runStartRitual?: boolean;
}) {
  const section = railSection(route);
  const {t} = useI18n();
  const fetchingQuotes = Boolean(view.marketDataProgress && view.marketDataProgress.total > 0);
  const hostKey: HostStatus = fetchingQuotes
    ? "running"
    : (view.hostStatus ?? (
      view.kind === "awaiting_confirm" ? "awaiting_confirm" :
      view.kind === "running" ? "running" :
      view.kind === "completed" ? "completed" : "idle"
    ));
  const railKey = fetchingQuotes ? null : railStatusKey(view);
  const railLabel = fetchingQuotes ? t("host.running") : railKey ? t(railKey) : null;
  const engineLine = engineStatusLabel(sidecarState, t);
  const statusTitle = railLabel
    ? `${railLabel} · ${engineLine}`
    : engineLine;
  const failedTone = viewContentFailedTone(view);
  const paused = view.kind === "running" && view.status === "paused";
  const hasAside = shellHasAside(route, view.kind);
  const atmosphereTone =
    view.kind === "running"
      ? "running"
      : view.kind === "confirm_run"
        ? "confirm"
        : failedTone
          ? "failed"
          : view.kind === "completed"
            ? "success"
            : undefined;
  return (
    <main
      className="night-shell tech-pulse-shell"
      data-testid="night-shell"
      data-view={view.kind}
      data-has-aside={hasAside ? "true" : "false"}
      data-rail-width={RAIL_WIDTH}
      data-main-min={MAIN_MIN_WIDTH}
      data-engine-phase={sidecarState?.phase ?? "unknown"}
    >
      <aside className="rail" data-testid="rail" data-rail-width={RAIL_WIDTH}>
        <div className="rail-top">
          <BrandMark />
          <nav aria-label={t("ui.shell.aria")}>
            <a className={section === "research" ? "active" : ""} href="#/research"><RailIcon name="research" /><I18nText k="nav.research" /></a>
            <a className={section === "methods" ? "active" : ""} href="#/methods"><RailIcon name="methods" /><I18nText k="nav.methods" /></a>
            <a className={section === "glossary" ? "active" : ""} href="#/glossary"><RailIcon name="glossary" /><I18nText k="nav.glossary" /></a>
            <a className={section === "settings" ? "active" : ""} href="#/settings/general" data-testid="rail-settings"><RailIcon name="settings" /><I18nText k="nav.settings" /></a>
          </nav>
        </div>
        <div className="rail-bottom">
          {railLabel ? (
            <div className={`host-status rail-status ${paused ? "paused" : hostKey}`} title={statusTitle} data-testid="host-status">
              <span className="host-status-line" data-testid="rail-status-label">
                <span className="host-status-dot" aria-hidden />
                {railLabel}
              </span>
            </div>
          ) : null}
          <SecretVaultButton />
        </div>
      </aside>
      <section
        className={`content ${view.kind} tech-pulse-content${failedTone ? " tech-pulse-failed-tone" : ""}${runStartRitual ? " run-start-ritual" : ""}`}
        data-run-start-ritual={runStartRitual ? "active" : undefined}
        data-has-aside={hasAside ? "true" : "false"}
      >
        <div
          className="tech-pulse-atmosphere"
          data-testid="tech-pulse-atmosphere"
          data-atmosphere-tone={atmosphereTone}
          aria-hidden
        />
        {view.marketDataProgress && view.marketDataProgress.total > 0 ? (
          <p data-testid="market-data-progress">
            {t("research.quoteProgress", {
              done: view.marketDataProgress.done,
              total: view.marketDataProgress.total,
            })}
          </p>
        ) : null}
        {view.testData ? (
          <p className="test-data-badge" data-testid="test-data-badge" role="status">
            {t("ui.shell.testData")}
          </p>
        ) : null}
        {view.thesisChangeHint && <p className="thesis-hint">{view.thesisChangeHint}</p>}
        {children}
      </section>
    </main>
  );
}

