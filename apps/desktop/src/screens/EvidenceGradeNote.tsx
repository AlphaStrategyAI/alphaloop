import type {EvidenceGradeView} from "../contracts";
import {I18nText} from "../i18n/I18nText";
import type {MessageKey} from "../i18n/I18nProvider";

const GRADE_KEY: Record<string, MessageKey> = {
  legacy: "ui.evidence.legacy",
  exploratory: "ui.evidence.exploratory",
  final: "ui.evidence.final",
};

/** Same grade the engine view already computed. Direct API and this line stay aligned. */
export function EvidenceGradeNote({grade}: {grade?: EvidenceGradeView | null}) {
  if (!grade?.grade) return null;
  const key = GRADE_KEY[grade.grade] ?? "ui.evidence.exploratory";
  return (
    <p data-testid="evidence-grade" data-grade={grade.grade}>
      <I18nText k={key} />
      {grade.reason ? <span data-testid="evidence-grade-reason">{` — ${grade.reason}`}</span> : null}
    </p>
  );
}
