import {createContext, useContext, useEffect, useMemo, useState, type ReactNode} from "react";

import {enCatalog, zhCatalog, type MessageCatalog} from "./catalog";
import {languageName, resolveUiLanguage} from "./locale";
import {createMemoryLanguagePort, type UiLanguagePort} from "./port";
import {translate, type MessageParams} from "./translate";
import type {LeafPaths} from "./keys";
import type {Locale, UiLanguagePreference, UiLanguageSnapshot} from "./types";

export type MessageKey = LeafPaths<MessageCatalog>;

interface I18nContextValue {
  preference: UiLanguagePreference;
  systemLocale: string | null;
  resolved: Locale;
  ready: boolean;
  t: (key: MessageKey, params?: MessageParams) => string;
  setPreference: (preference: UiLanguagePreference) => Promise<void>;
  languageName: typeof languageName;
}

const catalogs = {zh: zhCatalog, en: enCatalog};

const defaultSnapshot: UiLanguageSnapshot = {
  preference: "system",
  systemLocale: null,
  resolved: "en",
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({
  children,
  port,
  initial,
}: {
  children: ReactNode;
  port?: UiLanguagePort;
  initial?: UiLanguageSnapshot;
}) {
  const languagePort = useMemo(() => port ?? createMemoryLanguagePort(), [port]);
  const [snapshot, setSnapshot] = useState<UiLanguageSnapshot | null>(initial ?? null);

  useEffect(() => {
    if (initial) return;
    let active = true;
    void languagePort
      .load()
      .then((loaded) => {
        if (!active) return;
        setSnapshot(loaded);
        void languagePort.setEngineLocale(loaded.resolved);
      })
      .catch(() => {
        if (active) setSnapshot(defaultSnapshot);
      });
    return () => {
      active = false;
    };
  }, [initial, languagePort]);

  const value = useMemo<I18nContextValue>(() => {
    const current = snapshot ?? defaultSnapshot;
    return {
      preference: current.preference,
      systemLocale: current.systemLocale,
      resolved: current.resolved,
      ready: snapshot !== null,
      languageName,
      t: (key, params) => translate(current.resolved, key, params, catalogs),
      setPreference: async (next) => {
        const systemLocale =
          next === "system" ? await languagePort.readSystemLocale() : current.systemLocale;
        const optimistic: UiLanguageSnapshot = {
          preference: next,
          systemLocale,
          resolved: resolveUiLanguage(next, systemLocale),
        };
        setSnapshot(optimistic);
        void languagePort.setEngineLocale(optimistic.resolved);
        const saved = await languagePort.save(next);
        setSnapshot(saved);
        if (saved.resolved !== optimistic.resolved) {
          void languagePort.setEngineLocale(saved.resolved);
        }
      },
    };
  }, [languagePort, snapshot]);

  if (!snapshot) return null;
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (value) return value;
  return {
    preference: defaultSnapshot.preference,
    systemLocale: defaultSnapshot.systemLocale,
    resolved: defaultSnapshot.resolved,
    ready: true,
    languageName,
    t: (key, params) => translate(defaultSnapshot.resolved, key, params, catalogs),
    setPreference: async () => undefined,
  };
}
