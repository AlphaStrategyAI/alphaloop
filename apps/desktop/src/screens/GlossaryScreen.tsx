import {FormEvent, useEffect, useRef, useState, type ReactNode} from "react";

import type {DesktopApi, DesktopView, BriefSlotName, HostStatus, PitDetail, ResearchListDisplayStatus, SidecarUiState, ValidationMethod, AnomalyPresentation} from "../contracts";
import {formatResearchTimestamp} from "../format";
import {LocalizedRunError} from "../i18n/LocalizedRunError";
import {useI18n, type MessageKey} from "../i18n/I18nProvider";
import type {MessageParams} from "../i18n/translate";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "../InAppConfirm";
import {parseEffectiveQuotaFromView} from "../effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "../completedFailedTone";
import {listRowStatusKey} from "../listStatusDisplay";
import {railStatusKey} from "../railStatus";
import {BrandMark} from "../BrandMark";
import type {Translate} from "./shared";
import {AnomalyChecklist, renderSettingsProse} from "./shared";

export function GlossaryScreen({view}: {view: Extract<DesktopView, {kind: "glossary"}>}) {
  return (
    <div className="glossary-page" data-testid="glossary-page">
      <p className="confirm-lead">{view.intro}</p>
      {view.entries.map((entry) => (
        <details key={entry.id} className="tech-pulse-card glossary-entry" open>
          <summary>{entry.term}</summary>
          <p>{entry.body}</p>
        </details>
      ))}
    </div>
  );
}

