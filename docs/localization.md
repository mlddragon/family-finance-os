# Localization

Family Finance OS uses an i18n-first approach. The maintained locale is `en-US`; future localization contributors can add locale bundles without changing product logic.

## Principles

- Stable API codes, database keys, setting keys, category keys, validation codes, and audit values are not translated.
- User-facing UI labels, helper text, report titles, and display labels should resolve through locale resources or install settings.
- Install-specific text belongs in SQLite-backed settings, not in source defaults.
- New locale contributions should be reviewed with screenshots or a QA script because longer translated strings can affect layout.

## Current Locale

The initial maintained locale lives in `apps/web/src/locales/en-US.ts`.

The default install settings are:

- App display name: `Family Finance OS`
- Household display name: `Household`
- Default locale: `en-US`
- Currency code: `USD`
- Default actor: `owner`
