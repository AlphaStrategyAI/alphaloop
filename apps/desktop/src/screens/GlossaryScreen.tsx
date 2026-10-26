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

export function GlossaryScreen({view}: {view: Extract<DesktopView, {kind: "glossary"}>}) {
  const {t, resolved} = useI18n();
  const copyText = (text: string | null | undefined) => (text ? localizeKnownCopy(text, t) : "");
  return (
    <div className="glossary-page" data-testid="glossary-page">
      <p className="confirm-lead">{copyText(view.intro)}</p>
      {view.entries.map((entry) => {
        const bodyKey = GLOSSARY_BODY[entry.id];
        const body = bodyKey && resolved === "en" ? t(bodyKey) : entry.body;
        return (
          <details key={entry.id} className="tech-pulse-card glossary-entry" open>
            <summary>{copyText(entry.term)}</summary>
            <p>{body}</p>
          </details>
        );
      })}
    </div>
  );
}

