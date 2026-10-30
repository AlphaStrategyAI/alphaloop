import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import {localizeKnownCopy} from "../i18n/productCopy";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";

const GLOSSARY_BODY: Record<string, MessageKey> = {
  "pit.consistency": "ui.glossaryBody.pit",
  trial_counts: "ui.glossaryBody.trials",
  "overfit.walk": "ui.glossaryBody.walk",
  "stability.oos": "ui.glossaryBody.stability",
  "crowding.load": "ui.glossaryBody.crowding",
  frozen_methods: "ui.glossaryBody.frozen",
  benchmark: "ui.glossaryBody.benchmark",
  cost_bp: "ui.glossaryBody.cost",
};

function formerName(body: string): string | null {
  const quoted = body.match(/旧称「([^」]+)」/);
  if (quoted) return quoted[1] ?? null;
  const labeled = body.match(/曾用名[:：]\s*([^。]+)/);
  return labeled?.[1]?.trim() || null;
}

export function GlossaryScreen({view}: {view: Extract<DesktopView, {kind: "glossary"}>}) {
  const {t, resolved} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  const [query, setQuery] = useState("");
  const [openIds, setOpenIds] = useState<ReadonlySet<string>>(
    () => new Set(view.entries[0] ? [view.entries[0].id] : []),
  );
  const normalized = query.trim().toLowerCase();
  const rows = view.entries.map((entry) => {
    const bodyKey = GLOSSARY_BODY[entry.id];
    const body = bodyKey && resolved === "en" ? t(bodyKey) : entry.body;
    const term = copyText(entry.term);
    return {entry, body, term, former: formerName(body)};
  });
  const visible = rows.filter((row) => {
    if (!normalized) return true;
    return `${row.term} ${row.body} ${row.former ?? ""}`.toLowerCase().includes(normalized);
  });
  return (
    <div className="glossary-page" data-testid="glossary-page" data-column-max="720" data-has-aside="false">
      <header className="glossary-chrome" data-testid="glossary-chrome">
        <h1>{t("nav.glossary")}</h1>
        <input
          className="glossary-search"
          data-testid="glossary-search"
          type="search"
          value={query}
          placeholder={t("ui.glossary.search")}
          onChange={(event) => setQuery(event.target.value)}
        />
      </header>
      <p className="confirm-lead">{copyText(view.intro)}</p>
      {visible.map((row) => {
        const searching = normalized.length > 0;
        const open = searching || openIds.has(row.entry.id);
        return (
          <details
            key={row.entry.id}
            className="tech-pulse-card glossary-entry"
            open={open}
            onToggle={(event) => {
              if (searching) return;
              const nextOpen = event.currentTarget.open;
              setOpenIds((prev) => {
                const next = new Set(prev);
                if (nextOpen) next.add(row.entry.id);
                else next.delete(row.entry.id);
                return next;
              });
            }}
          >
            <summary>{row.term}</summary>
            <p>{row.body}</p>
            {row.former ? (
              <p className="glossary-former" data-testid="glossary-former">{t("ui.glossary.former", {name: row.former})}</p>
            ) : null}
          </details>
        );
      })}
      {normalized && visible.length === 0 ? (
        <p data-testid="glossary-empty">{t("ui.glossary.noMatch")}</p>
      ) : null}
    </div>
  );
}

