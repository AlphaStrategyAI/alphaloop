"""UI language foundation (M2 I0).

Other lines:

- Add a user-facing string in ``apps/desktop/src/i18n/catalog.ts`` (both languages).
  English that is not a locked glossary term or an explicit final token must include
  the placeholder marker from ``contracts/i18n-conventions.json``.
- Raise engine failures with ``engine.i18n.errors.build_error_envelope`` and register
  the code in ``contracts/error-codes.json`` plus the desktop ``errors.codes`` catalog.
  Keep the legacy ``error`` sentence stable until I2. Do not store the UI language
  on a research record.
- Resolved request locale is ``zh`` or ``en`` on each desktop command (``locale``).
  ``system`` is only a preference, never a request locale.
"""
