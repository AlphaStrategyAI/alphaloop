import type {ReactNode} from "react";

import {useI18n} from "./I18nProvider";

const LOGIC = /^论点：(.+)；实际执行：截面均值回归，回看 (\d+) 天$/;

/** Engine logic line. The thesis stays user content; the template follows the UI language. */
export function LogicStatementText({text}: {text: string}): ReactNode {
  const {t} = useI18n();
  const match = LOGIC.exec(text);
  if (!match) return text;
  return (
    <>
      {t("ui.copy.logicLead")}
      <span data-user-content="true">{match[1]}</span>
      {t("ui.copy.logicTail", {days: match[2]})}
    </>
  );
}
