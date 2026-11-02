import {DialogueTurnBody} from "../i18n/engineFailure";
import {useI18n} from "../i18n/I18nProvider";
import {localizeKnownCopy} from "../i18n/productCopy";
import type {DialogueTurnView} from "../contracts";

const CJK = /[\u3400-\u9fff]/;

export function RuntimeDialogueLog({turns}: {turns?: readonly DialogueTurnView[]}) {
  const {t, resolved} = useI18n();
  if (!turns || turns.length === 0) return null;
  const visible = turns.flatMap((turn) => {
    if (turn.errorCode) return [turn];
    const text = localizeKnownCopy(turn.text, t);
    if (resolved === "en" && CJK.test(text)) return [];
    return [{...turn, text}];
  });
  if (visible.length === 0) return null;
  return (
    <div className="runtime-dialogue-log" data-testid="runtime-dialogue-log">
      {visible.map((turn, index) => (
        <DialogueTurnBody key={`${turn.role}-${index}-${turn.text}`} turn={turn} />
      ))}
    </div>
  );
}
