import {useEffect, useRef, useState} from "react";

import type {DesktopView} from "./contracts";
import {
  prefersReducedMotion,
  RUN_START_RITUAL_MS,
  shouldTriggerRunStartRitual,
} from "./runStartRitual";

/** Brief visual polish when confirm_run transitions to running (no fake metrics). */
export function useRunStartRitual(view: DesktopView): boolean {
  const previousRef = useRef<DesktopView>(view);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const previous = previousRef.current;
    if (shouldTriggerRunStartRitual(previous, view) && !prefersReducedMotion()) {
      setActive(true);
      const timer = window.setTimeout(() => setActive(false), RUN_START_RITUAL_MS);
      previousRef.current = view;
      return () => {
        window.clearTimeout(timer);
        setActive(false);
      };
    }
    previousRef.current = view;
    return undefined;
  }, [view]);

  return active;
}
