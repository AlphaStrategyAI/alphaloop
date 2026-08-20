from __future__ import annotations

from alphaloop.runtime.preflight import HOST_CONSTRAINT

SOAK_PLAN = f"""alphaloop overnight soak — release checklist

This checklist is not CI.
This soak does not claim alpha or future profitability.

{HOST_CONSTRAINT}

Fixed suite (two independent jobs, never one mixed ranking):
1. us-equity-daily with a real dataset snapshot hash
2. crypto-daily with a real dataset snapshot hash

For each job:
- Leave the host awake for the overnight budget.
- Submit with alphaloop submit or the morning console (preview, then freeze).
- Record the research conclusion: FOUND, NO_EVIDENCE, or INCONCLUSIVE.
  Job status is not the conclusion.
- In the morning, name the conclusion, primary evidence, and stop reason
  from the packaged console in five minutes.
- Optional fault: kill -9 the worker after a complete checkpoint, resume,
  and confirm trial_id values stay unique.

Do not treat FOUND as a promise of alpha. Do not mix the two profiles
into one default ranking. AlphaStrategy consumer tests stay in that repo.

Operator metric (not computed by this command): at least 95% of jobs in
this fixed suite complete without operator intervention on each platform
the release explicitly supports.
"""


def emit_soak_plan() -> str:
    return SOAK_PLAN
