import type {ReactNode} from "react";

import {ASIDE_WIDTH} from "../layoutShell";

/** Detail and draft reading column plus a 320 aside. */
export function DetailFrame({aside, children}: {aside: ReactNode; children: ReactNode}) {
  return (
    <div className="detail-layout" data-testid="detail-layout" data-aside-width={ASIDE_WIDTH}>
      <div className="detail-main">{children}</div>
      <aside className="detail-aside" data-testid="detail-aside">
        {aside}
      </aside>
    </div>
  );
}
