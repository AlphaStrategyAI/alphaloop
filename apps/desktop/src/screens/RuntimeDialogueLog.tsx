import {DialogueTurnBody} from "../i18n/engineFailure";
import type {DialogueTurnView} from "../contracts";

export function RuntimeDialogueLog({turns}: {turns?: readonly DialogueTurnView[]}) {
  if (!turns || turns.length === 0) return null;
  return (
    <div className="runtime-dialogue-log" data-testid="runtime-dialogue-log">
      {turns.map((turn, index) => (
        <DialogueTurnBody key={`${turn.role}-${index}-${turn.text}`} turn={turn} />
      ))}
    </div>
  );
}
