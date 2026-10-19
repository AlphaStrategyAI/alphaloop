import conventions from "../../../../contracts/i18n-conventions.json";
import errorCodes from "../../../../contracts/error-codes.json";

export const PLACEHOLDER_MARKER = conventions.placeholderMarker;
export const UI_LOCALES = conventions.locales;
export const UI_PREFERENCES = conventions.preferences;
export const ERROR_CODES = errorCodes;

export type ErrorCode = keyof typeof errorCodes;
